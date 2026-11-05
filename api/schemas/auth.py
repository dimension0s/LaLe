from typing import Optional

from pydantic import BaseModel, Field


class SendCodeRequest(BaseModel):
    phone_number: str = Field(..., min_length=11, max_length=11)


class LoginRequest(BaseModel):
    phone_number: str = Field(
        ..., min_length=11, max_length=11,
        json_schema_extra={"example": "13900000001"},
    )
    code: Optional[str] = Field(
        None,
        json_schema_extra={"example": "123456"},
    )