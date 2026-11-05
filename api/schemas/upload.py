from typing import Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    doc_id: int
    doc_uuid: str
    file_name: str
    file_type: str
    file_path: str
    file_size: Optional[int] = None
    status: str
    created_at: Optional[str] = None