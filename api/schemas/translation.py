from typing import Optional

from pydantic import BaseModel, Field


class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待翻译的原文")
    source_lang: str = Field("自动检测", description="源语言")
    target_lang: str = Field("中文", description="目标语言")
    mode: str = Field("direct", pattern="^(direct|indirect)$", description="翻译模式：直译 / 意译")
    use_tools: bool = Field(True, description="是否允许模型调用工具（RAG/Web）")
    return_trace: bool = Field(False, description="是否返回详细的推理过程（用于调试）")