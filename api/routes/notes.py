"""
笔记路由：加入 / 分组 / 详情 / 删除
"""

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_current_user_id
from api.response import ok, fail
from api.schemas.notes import (
    AddNoteRequest, GroupedNotesRequest, NotesByDateRequest,
)
from user_manager import generate_notes, search_notes, recycle
from pydantic import BaseModel


router = APIRouter()


@router.post("")
def add_note(
    req: AddNoteRequest,
    user_id: int = Depends(get_current_user_id),
):
    """加入笔记"""
    note = generate_notes.add_note(
        document_id=req.document_id,
        note_type=req.note_type,
        content=req.content,
        user_id=user_id,
    )
    if note is None:
        return fail(400, "添加笔记失败（文档不存在或类型非法）")

    data = search_notes._note_to_dict(note)
    return ok(data=data, msg="笔记已添加")


@router.get("/grouped")
def list_grouped(
    document_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """按模块 + 日期分组返回笔记"""
    result = search_notes.list_notes_grouped(document_id, user_id)
    if result["document"] is None:
        return fail(404, "文档不存在")
    return ok(data=result)


@router.get("/by_date")
def list_by_date(
    document_id: int,
    note_type: str,
    date: str,
    user_id: int = Depends(get_current_user_id),
):
    """某日期某模块下的笔记列表"""
    notes = search_notes.list_notes_by_date(
        document_id, note_type, date, user_id,
    )
    return ok(data=notes)
@router.get("/list/all")
def get_all_notes(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
):
    """获取当前用户的全部笔记"""
    from user_manager import search_notes
    result = search_notes.list_all_notes(user_id, limit=limit, offset=offset)
    return ok(data=result)

@router.get("/{note_uuid}")
def get_note(
    note_uuid: str,
    user_id: int = Depends(get_current_user_id),
):
    """笔记详情"""
    note = search_notes.get_note_by_uuid(note_uuid, user_id)
    if note is None:
        return fail(404, "笔记不存在")
    return ok(data=note)


@router.delete("/{note_uuid}")
def delete_note(
    note_uuid: str,
    user_id: int = Depends(get_current_user_id),
):
    """删除笔记（软删除进回收站）"""
    ok_flag = recycle.delete_note(note_uuid, user_id)
    if not ok_flag:
        return fail(400, "删除失败（笔记不存在或已在回收站）")
    return ok(msg="已移入回收站")



class UpdateNoteRequest(BaseModel):
    content: str

@router.patch("/{note_uuid}")
def update_note(
    note_uuid: str,
    req: UpdateNoteRequest,
    user_id: int = Depends(get_current_user_id),
):
    """编辑笔记内容"""
    from user_manager import generate_notes
    if not generate_notes.update_note_content(note_uuid, user_id, req.content):
        return fail(400, "更新失败（笔记不存在或内容为空）")
    return ok(msg="笔记已更新")