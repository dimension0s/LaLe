"""
回收站路由
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_current_user_id
from api.response import ok, fail
from api.schemas.recycle import RestoreRequest
from user_manager import recycle, search_notes
from typing import List
from pydantic import BaseModel

from user_manager.pg_data_manager.database import get_session
from user_manager.pg_data_manager.orm_models import UserDocument, UserNote, Integration, UserVocabulary, RecycleBin
from user_manager import recycle, search_notes
from loguru import logger


router = APIRouter()


@router.get("")
def list_recycle(user_id: int = Depends(get_current_user_id)):
    """回收站列表"""
    items = recycle.list_recycle_bin(user_id)
    return ok(data=items)


@router.post("/restore")
def restore(
        req: RestoreRequest,
        user_id: int = Depends(get_current_user_id),
):
    file_type = req.file_type
    file_id = str(req.file_id)  # 统一转字符串
    logger.info(f"收到恢复请求: type={file_type}, file_id={file_id}")

    # 根据 file_type 严格去对应的表里查
    if file_type == "user_document":
        with get_session() as session:
            # 👇 严格按 ID 或 UUID 查，绝不串表
            if file_id.isdigit():
                doc = session.query(UserDocument).filter_by(id=int(file_id), user_id=user_id, status="deleted").first()
            else:
                doc = session.query(UserDocument).filter_by(doc_uuid=file_id, user_id=user_id, status="deleted").first()

            if not doc:
                return fail(404, "文档不存在或不在回收站")

            # 调用你原本的 restore 逻辑
            ok_flag = recycle.restore_document(str(doc.id), user_id)

    elif file_type == "user_note":
        with get_session() as session:
            if file_id.isdigit():
                note = session.query(UserNote).filter_by(id=int(file_id), user_id=user_id, status="deleted").first()
            else:
                note = session.query(UserNote).filter_by(note_uuid=file_id, user_id=user_id, status="deleted").first()

            if not note:
                return fail(404, "笔记不存在或不在回收站")

            ok_flag = recycle.restore_note(str(note.note_uuid), user_id)

    elif file_type == "integration":
        with get_session() as session:
            if file_id.isdigit():
                integ = session.query(Integration).filter_by(id=int(file_id), user_id=user_id, status="deleted").first()
            else:
                integ = session.query(Integration).filter_by(integration_uuid=file_id, user_id=user_id,
                                                             status="deleted").first()

            if not integ:
                return fail(404, "整合不存在或不在回收站")

            ok_flag = recycle.restore_integration(str(integ.integration_uuid), user_id)

    elif file_type == "user_vocabulary":
        with get_session() as session:
            if file_id.isdigit():
                vocab = session.query(UserVocabulary).filter_by(id=int(file_id), user_id=user_id,
                                                                status="deleted").first()
            else:
                vocab = session.query(UserVocabulary).filter_by(vocab_uuid=file_id, user_id=user_id,
                                                                status="deleted").first()

            if not vocab:
                return fail(404, "生词不存在或不在回收站")

            ok_flag = recycle.restore_vocabulary(str(vocab.vocab_uuid), user_id)

    else:
        return fail(400, "未知 file_type")

    if not ok_flag:
        return fail(400, "恢复失败")
    return ok("已恢复")

class DeleteRequestItem(BaseModel):
    file_type: str
    file_id: int

class BatchDeleteRequest(BaseModel):
    items: List[DeleteRequestItem]


@router.delete("/permanent")
def permanent_delete(
        req: BatchDeleteRequest,
        user_id: int = Depends(get_current_user_id),
):
    """彻底删除（物理删除）"""
    from user_manager import recycle
    success_count = 0
    for item in req.items:
        if recycle.permanent_delete(item.file_type, item.file_id):
            success_count += 1

    if success_count == 0:
        return fail(400, "彻底删除失败，未找到相关文件")
    return ok(msg=f"成功彻底删除 {success_count} 项")