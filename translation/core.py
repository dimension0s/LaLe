"""
core.py - 翻译主流程（单轮 + RAG）
路径: /home/bina/LaLe/translation_traces/core.py

职责:
1. 调用 DeepSeek 模型翻译
2. 支持直译/意译两种模式
3. 支持 RAG 工具调用（单轮）
4. 返回 TranslationResult

不负责:
- 提示词定义（由 prompts/ 负责）
- 模型配置（由 models_config.py 负责）
- 监督/统计（由 supervision.py 负责）
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Tuple

import requests
from loguru import logger

from translation.models_config import get_translation_config
from translation.prompts import (
    DIRECT_SYSTEM_PROMPT,
    DIRECT_PROMPT_TEMPLATE,
    INDIRECT_SYSTEM_PROMPT,
    INDIRECT_PROMPT_TEMPLATE,
)
from translation.supervision import (
    create_trace,
    add_round,
    add_tool_call,
    finalize_trace,
    save_trace,
    TaskTrace,
)


# ============================================================
# 配置
# ============================================================
DEFAULT_MODE = "direct"
DEFAULT_SOURCE_LANG = "自动检测"
DEFAULT_TARGET_LANG = "中文"

# 工具结果截断长度（字符）
MAX_TOOL_RESULT_LEN = 2000


# ============================================================
# 返回结构
# ============================================================
@dataclass
class TranslationResult:
    """翻译结果"""
    original_text: str
    translated_text: str
    mode: str                  # "direct" / "indirect"
    source_lang: str
    target_lang: str
    model_name: str
    elapsed_ms: int
    rounds: int                # 实际轮数（1 或 2）

    def to_dict(self) -> Dict:
        return {
            "original_text": self.original_text,
            "translated_text": self.translated_text,
            "mode": self.mode,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "model_name": self.model_name,
            "elapsed_ms": self.elapsed_ms,
            "rounds": self.rounds,
        }


# ============================================================
# 主函数
# ============================================================
def translate(
    text: str,
    source_lang: str = DEFAULT_SOURCE_LANG,
    target_lang: str = DEFAULT_TARGET_LANG,
    mode: str = DEFAULT_MODE,
    use_tools: bool = True,
    return_trace: bool = False,
) -> Union[TranslationResult, Tuple[TranslationResult, TaskTrace]]:
    """
    翻译主函数（单轮 + RAG）

    Args:
        text: 待翻译文本
        source_lang: 源语言
        target_lang: 目标语言
        mode: 翻译模式（"direct" 直译 / "indirect" 意译）
        use_tools: 是否允许调用工具
        return_trace: 是否返回 trace

    Returns:
        TranslationResult
        或 (TranslationResult, TranslationTrace)（当 return_trace=True）
    """
    # 1. 参数校验
    if not text or not text.strip():
        raise ValueError("text 不能为空")

    if mode not in ("direct", "indirect"):
        raise ValueError(f"未知模式: {mode}，只支持 direct / indirect")

    text = text.strip()
    start_time = time.monotonic()

    # 创建 trace
    trace = create_trace(
        task_type="translation",
        original_text=text,
        source_lang=source_lang,
        target_lang=target_lang,
        mode=mode,
    )

    logger.info("=" * 60)
    logger.info(f"翻译任务")
    logger.info(f"模式: {mode}")
    logger.info(f"源语言: {source_lang}")
    logger.info(f"目标语言: {target_lang}")
    logger.info(f"允许工具: {use_tools}")
    logger.info(f"原文: {text[:80]}{'...' if len(text) > 80 else ''}")
    logger.info("=" * 60)

    # 2. 选择提示词
    system_prompt, prompt_template = _select_prompt(mode)

    # 3. 第 1 次调用模型
    logger.info("[第1轮] 调用模型...")
    prompt1 = prompt_template.format(
        source_lang=source_lang,
        target_lang=target_lang,
        text=text,
    )

    response1 = _call_model(system_prompt, prompt1)
    decision1 = _parse_json(response1)

    logger.info(f"思考: {decision1.get('thought', '')}")
    logger.info(f"行动: {decision1.get('action', '')}")

    # 4. 判断 action
    action = decision1.get("action", "")

    # ============================================================
    # 分支 1：直接输出（1 轮）
    # ============================================================
    if action == "output":
        translated = decision1.get("translation_traces", "").strip()
        if not translated:
            raise ValueError("模型未返回 translation_traces 字段")

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # 记录第 1 轮
        add_round(
            trace=trace,
            round_num=1,
            thought=decision1.get("thought", ""),
            action="output",
            elapsed_ms=elapsed_ms,
        )

        # finalize
        finalize_trace(
            trace=trace,
            output_data={"translated_text": translated},
            rounds=1,
            total_elapsed_ms=elapsed_ms,
            model_name=get_translation_config().model_name,
        )

        logger.info(f"→ 直接输出（1 轮）")
        logger.info(f"译文: {translated[:80]}{'...' if len(translated) > 80 else ''}")
        logger.info(f"耗时: {elapsed_ms}ms")

        result = TranslationResult(
            original_text=text,
            translated_text=translated,
            mode=mode,
            source_lang=source_lang,
            target_lang=target_lang,
            model_name=get_translation_config().model_name,
            elapsed_ms=elapsed_ms,
            rounds=1,
        )

        if return_trace:
            return result, trace
        return result

    # ============================================================
    # 分支 2：需要工具
    # ============================================================
    elif action == "tool":
        # 如果 use_tools=False，强制输出
        if not use_tools:
            logger.warning("模型请求工具，但 use_tools=False，强制输出")
            decision1 = _force_output(system_prompt, prompt1, decision1)
            translated = decision1.get("translation_traces", "").strip()

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            add_round(
                trace=trace,
                round_num=1,
                thought=decision1.get("thought", ""),
                action="output",
                elapsed_ms=elapsed_ms,
            )

            finalize_trace(
                trace=trace,
                output_data={"translated_text": translated},
                rounds=1,
                total_elapsed_ms=elapsed_ms,
                model_name=get_translation_config().model_name,
            )

            logger.info(f"→ 强制输出（1 轮）")
            logger.info(f"译文: {translated[:80]}{'...' if len(translated) > 80 else ''}")

            result = TranslationResult(
                original_text=text,
                translated_text=translated,
                mode=mode,
                source_lang=source_lang,
                target_lang=target_lang,
                model_name=get_translation_config().model_name,
                elapsed_ms=elapsed_ms,
                rounds=1,
            )

            if return_trace:
                return result, trace
            return result

        # 调用工具
        tools = decision1.get("tools", [])
        if not tools:
            logger.warning("action=tool 但 tools 为空，强制输出")
            raise ValueError("模型返回 action=tool 但 tools 为空")

        # 记录第 1 轮
        rr1 = add_round(
            trace=trace,
            round_num=1,
            thought=decision1.get("thought", ""),
            action="tool",
            elapsed_ms=int((time.monotonic() - start_time) * 1000),
        )

        logger.info(f"[工具调用] 共 {len(tools)} 个")
        tool_results = []
        for tool_call in tools:
            tool_start = time.monotonic()
            result = _call_tool(tool_call)
            tool_elapsed = int((time.monotonic() - tool_start) * 1000)

            # 记录工具调用
            add_tool_call(
                trace=trace,
                round_record=rr1,
                tool_type=tool_call.get("type", "unknown"),
                query=tool_call.get("query", ""),
                result=result,
                elapsed_ms=tool_elapsed,
            )

            tool_results.append({
                "tool": tool_call.get("type", "unknown"),
                "query": tool_call.get("query", ""),
                "result": result,
            })
            logger.info(f"  - {tool_call.get('type')}: {tool_call.get('query')[:50]}")

        # 5. 第 2 次调用模型（带工具结果）
        logger.info("[第 2 轮] 调用模型（带工具结果）...")
        prompt2 = prompt1 + _build_tool_context(tool_results)
        response2 = _call_model(system_prompt, prompt2)
        decision2 = _parse_json(response2)

        translated = decision2.get("translation_traces", "").strip()
        if not translated:
            raise ValueError("第 2 轮模型未返回 translation_traces 字段")

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # 记录第 2 轮
        add_round(
            trace=trace,
            round_num=2,
            thought=decision2.get("thought", ""),
            action="output",
            elapsed_ms=elapsed_ms,
        )

        # finalize
        finalize_trace(
            trace=trace,
            output_data={"translated_text": translated},
            rounds=2,
            total_elapsed_ms=elapsed_ms,
            model_name=get_translation_config().model_name,
        )

        logger.info(f"→ 工具后输出（2 轮）")
        logger.info(f"译文: {translated[:80]}{'...' if len(translated) > 80 else ''}")
        logger.info(f"耗时: {elapsed_ms}ms")

        result = TranslationResult(
            original_text=text,
            translated_text=translated,
            mode=mode,
            source_lang=source_lang,
            target_lang=target_lang,
            model_name=get_translation_config().model_name,
            elapsed_ms=elapsed_ms,
            rounds=2,
        )

        if return_trace:
            return result, trace
        return result

    else:
        raise ValueError(f"未知 action: {action}")


# ============================================================
# 辅助函数
# ============================================================
def _select_prompt(mode: str):
    """选择提示词"""
    if mode == "direct":
        return DIRECT_SYSTEM_PROMPT, DIRECT_PROMPT_TEMPLATE
    elif mode == "indirect":
        return INDIRECT_SYSTEM_PROMPT, INDIRECT_PROMPT_TEMPLATE
    else:
        raise ValueError(f"未知模式: {mode}")


def _call_model(system_prompt: str, user_prompt: str) -> str:
    """
    调用 DeepSeek 模型

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词

    Returns:
        模型输出文本（JSON 字符串）
    """
    config = get_translation_config()

    if not config.api_key:
        raise ValueError("未设置 DeepSeek API 密钥")

    try:
        response = requests.post(
            f"{config.base_url}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
            },
            json={
                "model": config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content

    except requests.exceptions.Timeout:
        logger.error("模型调用超时")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"模型调用失败: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"响应内容: {e.response.text}")
        raise


def _parse_json(text: str) -> Dict:
    """
    解析模型输出的 JSON

    容错：
        1. 去掉 markdown 代码块
        2. 提取第一个 JSON 对象
    """
    if not text:
        raise ValueError("模型输出为空")

    text = text.strip()

    # 去掉 markdown 代码块
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    # 解析 JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 容错：提取第一个 JSON 对象
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}")
                logger.error(f"原始内容: {text[:500]}")
                raise
        raise ValueError(f"无法解析 JSON: {text[:200]}")


def _call_tool(tool_call: Dict) -> str:
    """
    调用工具

    Args:
        tool_call: {"type": "rag" / "web", "query": "..."}

    Returns:
        工具结果文本
    """
    tool_type = tool_call.get("type", "")
    query = tool_call.get("query", "").strip()

    if not query:
        return "[工具调用失败: query 为空]"

    # ============================================================
    # RAG 工具
    # ============================================================
    if tool_type == "rag":
        try:
            from RAG.search.searcher import search

            results = search(
                query=query,
                category="翻译",
                top_k_final=5,
            )

            good_results = [r for r in results if r.rerank_score > 0]

            if not good_results:
                return "[RAG 无相关结果]"

            result = "\n\n".join([
                f"【{r.title}】\n{r.content}"
                for r in good_results
            ])

            if len(result) > MAX_TOOL_RESULT_LEN:
                result = result[:MAX_TOOL_RESULT_LEN] + "\n...[已截断]"

            return result

        except Exception as e:
            logger.error(f"RAG 工具调用失败: {e}")
            return f"[RAG 工具调用失败: {e}]"

    # ============================================================
    # Web 工具（联网搜索）
    # ============================================================
    elif tool_type == "web":
        try:
            # 延迟导入，避免顶层导入触发 tools/__init__.py 副作用
            from tools.web.web_search import web_search_tool

            return web_search_tool(query)

        except ImportError as e:
            logger.error(f"Web 工具导入失败: {e}")
            return f"[Web 工具导入失败: {e}]"
        except Exception as e:
            logger.error(f"Web 工具调用失败: {e}")
            return f"[Web 工具调用失败: {e}]"

    # ============================================================
    # 未实现的工具
    # ============================================================
    else:
        return f"[工具 {tool_type} 未实现]"


def _build_tool_context(tool_results: List[Dict]) -> str:
    """
    构造工具结果上下文，追加到提示词末尾
    """
    lines = ["\n\n【已有信息】"]
    lines.append("你在上一轮调用了工具：")

    for i, tr in enumerate(tool_results, 1):
        lines.append(f"\n[{i}] 工具: {tr['tool']}")
        lines.append(f"查询: {tr['query']}")
        lines.append(f"结果:")
        lines.append(tr["result"])

    lines.append("\n【当前判断】")
    lines.append("基于上述信息，请输出最终翻译。")
    lines.append("请输出 JSON：")
    lines.append("""{
    "thought": "你的思考",
    "action": "output",
    "translation_traces": "翻译结果"
}""")

    return "\n".join(lines)


def _force_output(system_prompt: str, prompt: str, decision: Dict) -> Dict:
    """
    当 use_tools=False 但模型请求工具时，强制模型输出
    简单做法：直接返回一个"需要输出"的决策
    """
    return {
        "thought": decision.get("thought", ""),
        "action": "output",
        "translation_traces": decision.get("translation_traces", "") or "[无法输出]",
    }


# ============================================================
# 命令行入口：测试
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 测试参数
    # ================================================
    TEXT = "OpenAI released GPT-5 in 2025."
    SOURCE_LANG = "英语"
    TARGET_LANG = "中文"
    MODE = "direct"
    USE_TOOLS = True
    RETURN_TRACE = True      # ← 返回 trace
    SAVE_TRACE = True        # ← 保存 trace
    # ================================================

    print("=" * 60)
    print("翻译测试（带 supervision）")
    print("=" * 60)
    print(f"原文: {TEXT[:80]}...")
    print(f"模式: {MODE}")
    print(f"允许工具: {USE_TOOLS}")
    print(f"返回 trace: {RETURN_TRACE}")
    print(f"保存 trace: {SAVE_TRACE}")
    print("=" * 60)

    result_data = translate(
        text=TEXT,
        source_lang=SOURCE_LANG,
        target_lang=TARGET_LANG,
        mode=MODE,
        use_tools=USE_TOOLS,
        return_trace=RETURN_TRACE,
    )

    if RETURN_TRACE:
        result, trace = result_data
    else:
        result = result_data
        trace = None

    print("\n" + "=" * 60)
    print("✅ 翻译完成")
    print("=" * 60)
    print(f"译文: {result.translated_text}")
    print(f"模式: {result.mode}")
    print(f"轮数: {result.rounds}")
    print(f"耗时: {result.elapsed_ms}ms")
    print(f"模型: {result.model_name}")

    # 打印 trace
    if trace:
        print("\n" + "=" * 60)
        print("Trace 摘要")
        print("=" * 60)
        print(trace.summary())

        # 保存
        if SAVE_TRACE:
            path = save_trace(trace)
            print(f"\n✅ Trace 已保存: {path}")


