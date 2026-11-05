from pydantic import BaseModel, Field


class RestoreRequest(BaseModel):
    file_type: str = Field(
        ...,
        pattern="^(user_document|user_note|integration|user_vocabulary)$",
    )
    file_id: str   # 文档传 uuid，笔记/整合也传 uuid