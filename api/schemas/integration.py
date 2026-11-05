from typing import List

from pydantic import BaseModel, Field


class IntegrateRequest(BaseModel):
    note_uuids: List[str] = Field(..., min_length=2)