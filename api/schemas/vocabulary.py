from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class LookupRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)
    context: Optional[str] = Field(None, max_length=1000)


class AddVocabularyRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)
    word_info: Dict[str, Any] = Field(...)