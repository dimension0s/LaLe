from typing import List, Optional
from pydantic import BaseModel, Field


class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200, description="搜索词")
    max_results: int = Field(5, ge=1, le=10, description="返回结果数量")
    search_depth: str = Field("basic", pattern="^(basic|advanced)$", description="搜索深度")
    topic: str = Field("general", pattern="^(general|news)$", description="搜索主题")
    time_range: Optional[str] = Field(None, pattern="^(day|week|month|year)$", description="时间范围")
    include_domains: Optional[List[str]] = Field(None, description="限定域名")
    exclude_domains: Optional[List[str]] = Field(None, description="排除域名")