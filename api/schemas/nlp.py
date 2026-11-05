from typing import Optional
from pydantic import BaseModel, Field


class GrammarRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待解析的原文")
    source_lang: str = Field("英语", description="源语言")
    use_tools: bool = Field(True, description="是否允许模型调用工具")
    return_trace: bool = Field(False, description="是否返回详细推理过程")


class TerminologyRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待识别术语的原文")
    source_lang: str = Field("英语", description="源语言")
    target_lang: str = Field("中文", description="目标语言")
    use_tools: bool = Field(True, description="是否允许模型调用工具")
    return_trace: bool = Field(False, description="是否返回详细推理过程")


class PhraseRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待识别词组/搭配的原文")
    source_lang: str = Field("英语", description="源语言")
    target_lang: str = Field("中文", description="目标语言")
    use_tools: bool = Field(True, description="是否允许模型调用工具")
    return_trace: bool = Field(False, description="是否返回详细推理过程")