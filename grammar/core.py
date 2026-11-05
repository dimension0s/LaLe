"""
core.py - 语法解析主流程
路径: /home/bina/LaLe/grammar/core.py

职责:
1. 调用 DeepSeek 模型解析语法
2. 支持工具调用（RAG / Web）
3. 返回 GrammarResult
4. 支持 trace

不负责:
- 提示词定义（由 prompt.py 负责）
- 模型配置（由 models_config.py 负责）
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Tuple

import requests
from loguru import logger

from grammar.models_config import get_grammar_config
from grammar.prompt import GRAMMAR_SYSTEM_PROMPT, GRAMMAR_PROMPT_TEMPLATE
from translation.supervision import (   # ← 复用 translation 的
    create_trace,
    add_round,
    add_tool_call,
    finalize_trace,
    save_trace,
    TaskTrace,
)


# ============================================================
# 返回结构
# ============================================================
@dataclass
class GrammarResult:
    """语法解析结果"""
    original_text: str
    analysis: str               # 语法解析结果
    source_lang: str
    model_name: str
    elapsed_ms: int
    rounds: int

    def to_dict(self) -> Dict:
        return {
            "original_text": self.original_text,
            "analysis": self.analysis,
            "source_lang": self.source_lang,
            "model_name": self.model_name,
            "elapsed_ms": self.elapsed_ms,
            "rounds": self.rounds,
        }


# ============================================================
# 主函数
# ============================================================
def parse_grammar(
    text: str,
    source_lang: str = "英语",
    use_tools: bool = True,
    return_trace: bool = False,
) -> Union[GrammarResult, Tuple[GrammarResult, TaskTrace]]:
    """
    语法解析主函数

    Args:
        text: 待解析文本
        source_lang: 源语言
        use_tools: 是否允许工具
        return_trace: 是否返回 trace

    Returns:
        GrammarResult 或 (GrammarResult, TaskTrace)
    """
    # 1. 参数校验
    if not text or not text.strip():
        raise ValueError("text 不能为空")

    text = text.strip()
    start_time = time.monotonic()

    # 创建 trace
    trace = create_trace(
        task_type="grammar",       # ← 关键
        original_text=text,
        source_lang=source_lang,
        target_lang="",            # 语法不需要目标语言
        mode="grammar",
    )

    logger.info("=" * 60)
    logger.info(f"语法解析任务")
    logger.info(f"  源语言: {source_lang}")
    logger.info(f"  允许工具: {use_tools}")
    logger.info(f"  原文: {text[:80]}{'...' if len(text) > 80 else ''}")
    logger.info("=" * 60)

    # 2. 第 1 次调用
    logger.info("[第 1 轮] 调用模型...")
    prompt1 = GRAMMAR_PROMPT_TEMPLATE.format(
        source_lang=source_lang,
        text=text,
    )

    response1 = _call_model(GRAMMAR_SYSTEM_PROMPT, prompt1)
    decision1 = _parse_json(response1)

    logger.info(f"  思考: {decision1.get('thought', '')}")
    logger.info(f"  行动: {decision1.get('action', '')}")

    action = decision1.get("action", "")

    # 3. 判断 action
    if action == "output":
        analysis = decision1.get("analysis", "").strip()
        if not analysis:
            raise ValueError("模型未返回 analysis 字段")

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
            output_data={"analysis": analysis},
            rounds=1,
            total_elapsed_ms=elapsed_ms,
            model_name=get_grammar_config().model_name,
        )

        logger.info(f"  → 直接输出（1 轮）")
        logger.info(f"  解析: {analysis[:80]}...")
        logger.info(f"  耗时: {elapsed_ms}ms")

        result = GrammarResult(
            original_text=text,
            analysis=analysis,
            source_lang=source_lang,
            model_name=get_grammar_config().model_name,
            elapsed_ms=elapsed_ms,
            rounds=1,
        )

        if return_trace:
            return result, trace
        return result

    elif action == "tool":
        if not use_tools:
            # 强制输出
            logger.warning("模型请求工具，但 use_tools=False，强制输出")
            decision1 = _force_output(decision1)
            analysis = decision1.get("analysis", "").strip()

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
                output_data={"analysis": analysis},
                rounds=1,
                total_elapsed_ms=elapsed_ms,
                model_name=get_grammar_config().model_name,
            )

            result = GrammarResult(
                original_text=text,
                analysis=analysis,
                source_lang=source_lang,
                model_name=get_grammar_config().model_name,
                elapsed_ms=elapsed_ms,
                rounds=1,
            )

            if return_trace:
                return result, trace
            return result

        # 调用工具
        tools = decision1.get("tools", [])
        if not tools:
            raise ValueError("模型返回 action=tool 但 tools 为空")

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

        # 第 2 次调用
        logger.info("[第 2 轮] 调用模型（带工具结果）...")
        prompt2 = prompt1 + _build_tool_context(tool_results)
        response2 = _call_model(GRAMMAR_SYSTEM_PROMPT, prompt2)
        decision2 = _parse_json(response2)

        analysis = decision2.get("analysis", "").strip()
        if not analysis:
            raise ValueError("第 2 轮模型未返回 analysis 字段")

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        add_round(
            trace=trace,
            round_num=2,
            thought=decision2.get("thought", ""),
            action="output",
            elapsed_ms=elapsed_ms,
        )

        finalize_trace(
            trace=trace,
            output_data={"analysis": analysis},
            rounds=2,
            total_elapsed_ms=elapsed_ms,
            model_name=get_grammar_config().model_name,
        )

        logger.info(f"  → 工具后输出（2 轮）")
        logger.info(f"  解析: {analysis[:80]}...")
        logger.info(f"  耗时: {elapsed_ms}ms")

        result = GrammarResult(
            original_text=text,
            analysis=analysis,
            source_lang=source_lang,
            model_name=get_grammar_config().model_name,
            elapsed_ms=elapsed_ms,
            rounds=2,
        )

        if return_trace:
            return result, trace
        return result

    else:
        raise ValueError(f"未知 action: {action}")


# ============================================================
# 辅助函数（复用 translation 的逻辑）
# ============================================================
def _call_model(system_prompt: str, user_prompt: str) -> str:
    """调用 DeepSeek 模型"""
    config = get_grammar_config()

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
        return data["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        logger.error("模型调用超时")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"模型调用失败: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"响应内容: {e.response.text}")
        raise


def _parse_json(text: str) -> Dict:
    """解析模型输出的 JSON"""
    if not text:
        raise ValueError("模型输出为空")

    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}")
                raise
        raise ValueError(f"无法解析 JSON: {text[:200]}")


def _call_tool(tool_call: Dict) -> str:
    """调用工具（复用 translation 的 RAG/Web 逻辑）"""
    tool_type = tool_call.get("type", "")
    query = tool_call.get("query", "").strip()

    if not query:
        return "[工具调用失败: query 为空]"

    MAX_TOOL_RESULT_LEN = 2000

    if tool_type == "rag":
        try:
            from RAG.search.searcher import search

            results = search(
                query=query,
                category="语法",       # ← 语法模块，按语法过滤
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

    elif tool_type == "web":
        try:
            from tools.web.web_search import web_search_tool
            return web_search_tool(query)
        except Exception as e:
            logger.error(f"Web 工具调用失败: {e}")
            return f"[Web 工具调用失败: {e}]"

    else:
        return f"[工具 {tool_type} 未实现]"


def _build_tool_context(tool_results: List[Dict]) -> str:
    """构造工具结果上下文"""
    lines = ["\n\n【已有信息】"]
    lines.append("你在上一轮调用了工具：")

    for i, tr in enumerate(tool_results, 1):
        lines.append(f"\n[{i}] 工具: {tr['tool']}")
        lines.append(f"查询: {tr['query']}")
        lines.append(f"结果:")
        lines.append(tr["result"])

    lines.append("\n【当前判断】")
    lines.append("基于上述信息，请输出最终语法解析。")
    lines.append("请输出 JSON：")
    lines.append("""{
    "thought": "你的思考",
    "action": "output",
    "analysis": "语法解析结果"
}""")

    return "\n".join(lines)


def _force_output(decision: Dict) -> Dict:
    """强制输出"""
    return {
        "thought": decision.get("thought", ""),
        "action": "output",
        "analysis": decision.get("analysis", "") or "[无法输出]",
    }


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 测试参数
    # ================================================
    TEXT = "The phenomenon, which has puzzled scientists for decades, remains unexplained."
    SOURCE_LANG = "英语"
    USE_TOOLS = True
    RETURN_TRACE = True
    SAVE_TRACE = True
    # ================================================

    print("=" * 60)
    print("语法解析测试")
    print("=" * 60)
    print(f"原文: {TEXT}")
    print(f"源语言: {SOURCE_LANG}")
    print(f"允许工具: {USE_TOOLS}")
    print("=" * 60)

    result_data = parse_grammar(
        text=TEXT,
        source_lang=SOURCE_LANG,
        use_tools=USE_TOOLS,
        return_trace=RETURN_TRACE,
    )

    if RETURN_TRACE:
        result, trace = result_data
    else:
        result = result_data
        trace = None

    print("\n" + "=" * 60)
    print("✅ 语法解析完成")
    print("=" * 60)
    print(f"解析结果: {result.analysis}")
    print(f"轮数: {result.rounds}")
    print(f"耗时: {result.elapsed_ms}ms")

    if trace and SAVE_TRACE:
        print("\n" + "=" * 60)
        print("Trace 摘要")
        print("=" * 60)
        print(trace.summary())
        path = save_trace(trace)
        print(f"\n✅ Trace 已保存: {path}")