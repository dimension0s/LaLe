"""
supervision.py - 通用任务监督机制
路径: /home/bina/LaLe/translation/supervision.py

职责:
1. 记录任务的每一步（轮数、工具调用、耗时）
2. 输出 TaskTrace（结构化数据）
3. 支持落盘为 JSON

适用:
- 翻译、语法、术语、词组等所有任务
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from loguru import logger


# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRACE_DIR = PROJECT_ROOT / "data" / "output" / "traces"


# ============================================================
# 数据结构
# ============================================================
@dataclass
class ToolCallRecord:
    """工具调用记录"""
    round: int
    tool_type: str
    query: str
    result: str
    elapsed_ms: int
    result_length: int

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RoundRecord:
    """每轮记录"""
    round: int
    thought: str
    action: str
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    elapsed_ms: int = 0

    def to_dict(self) -> Dict:
        return {
            "round": self.round,
            "thought": self.thought,
            "action": self.action,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class TaskTrace:
    """通用任务追踪"""
    # 输入
    task_type: str               # ← 新增："translation" / "grammar" / ...
    original_text: str
    source_lang: str
    target_lang: str
    mode: str

    # 输出
    output_data: Dict = field(default_factory=dict)   # ← 通用输出（翻译是 translated_text）
    rounds: int = 0
    total_elapsed_ms: int = 0

    # 详细
    round_records: List[RoundRecord] = field(default_factory=list)
    tool_call_count: int = 0

    # 元信息
    model_name: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "task_type": self.task_type,
            "original_text": self.original_text,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "mode": self.mode,
            "output_data": self.output_data,
            "rounds": self.rounds,
            "total_elapsed_ms": self.total_elapsed_ms,
            "round_records": [rr.to_dict() for rr in self.round_records],
            "tool_call_count": self.tool_call_count,
            "model_name": self.model_name,
            "created_at": self.created_at,
        }

    def summary(self) -> str:
        """人类可读的摘要"""
        lines = [
            "=" * 60,
            "Task Trace Summary",
            "=" * 60,
            f"任务类型: {self.task_type}",
            f"模式: {self.mode}",
            f"源语言: {self.source_lang}",
            f"目标语言: {self.target_lang}",
            f"轮数: {self.rounds}",
            f"工具调用: {self.tool_call_count} 次",
            f"总耗时: {self.total_elapsed_ms}ms",
            f"模型: {self.model_name}",
            f"时间: {self.created_at}",
            "-" * 60,
            f"原文: {self.original_text[:100]}...",
            f"输出: {str(self.output_data)[:100]}...",
            "=" * 60,
        ]

        for rr in self.round_records:
            lines.append(f"\n[第 {rr.round} 轮] action={rr.action}, 耗时={rr.elapsed_ms}ms")
            lines.append(f"  思考: {rr.thought[:100]}...")
            for tc in rr.tool_calls:
                lines.append(
                    f"  [工具] {tc.tool_type}: {tc.query[:50]}... "
                    f"({tc.elapsed_ms}ms, 结果 {tc.result_length} 字符)"
                )

        return "\n".join(lines)


# ============================================================
# 便捷函数
# ============================================================
def create_trace(
    task_type: str,          # ← 新增
    original_text: str,
    source_lang: str = "",
    target_lang: str = "",
    mode: str = "",
) -> TaskTrace:
    """创建 trace"""
    return TaskTrace(
        task_type=task_type,
        original_text=original_text,
        source_lang=source_lang,
        target_lang=target_lang,
        mode=mode,
    )


def add_round(
    trace: TaskTrace,
    round_num: int,
    thought: str,
    action: str,
    elapsed_ms: int,
) -> RoundRecord:
    """添加一轮记录"""
    rr = RoundRecord(
        round=round_num,
        thought=thought,
        action=action,
        elapsed_ms=elapsed_ms,
    )
    trace.round_records.append(rr)
    return rr


def add_tool_call(
    trace: TaskTrace,
    round_record: RoundRecord,
    tool_type: str,
    query: str,
    result: str,
    elapsed_ms: int,
):
    """添加工具调用记录"""
    tc = ToolCallRecord(
        round=round_record.round,
        tool_type=tool_type,
        query=query,
        result=result,
        elapsed_ms=elapsed_ms,
        result_length=len(result),
    )
    round_record.tool_calls.append(tc)
    trace.tool_call_count += 1


def finalize_trace(
    trace: TaskTrace,
    output_data: Dict,       # ← 通用输出
    rounds: int,
    total_elapsed_ms: int,
    model_name: str,
) -> TaskTrace:
    """填充最终结果"""
    trace.output_data = output_data
    trace.rounds = rounds
    trace.total_elapsed_ms = total_elapsed_ms
    trace.model_name = model_name
    return trace


# ============================================================
# 落盘
# ============================================================
def save_trace(
    trace: TaskTrace,
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
) -> str:
    """
    保存 trace 为 JSON 文件

    Args:
        trace: TaskTrace
        output_dir: 输出目录（默认 LaLe/data/output/traces/{task_type}/）
        filename: 文件名（默认用时间戳）

    Returns:
        保存的文件路径
    """
    if output_dir is None:
        # 按 task_type 分目录
        output_dir = DEFAULT_TRACE_DIR / trace.task_type
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"trace_{timestamp}.json"

    output_path = output_dir / filename

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(trace.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Trace 已保存: {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"❌ Trace 保存失败: {e}")
        raise


def print_trace(trace: TaskTrace):
    """打印 trace 摘要"""
    print(trace.summary())