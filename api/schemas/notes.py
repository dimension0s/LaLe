from pydantic import BaseModel, Field


class AddNoteRequest(BaseModel):
    document_id: int
    note_type: str = Field(
        ...,
        pattern="^(translation|grammar|terminology|phrase)$",
    )
    content: str = Field(..., min_length=1)


class GroupedNotesRequest(BaseModel):
    document_id: int


class NotesByDateRequest(BaseModel):
    document_id: int
    note_type: str
    date: str   # YYYY-MM-DD