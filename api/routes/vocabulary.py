"""
生词本路由
"""

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_current_user_id
from api.response import ok, fail
from api.schemas.vocabulary import AddVocabularyRequest
from user_manager import vocabulary as vocab_module
from user_manager import recycle


router = APIRouter()


@router.post("")
def add_vocabulary(
    req: AddVocabularyRequest,
    user_id: int = Depends(get_current_user_id),
):
    """加入生词本"""
    vocab = vocab_module.add_vocabulary(
        user_id=user_id,
        word=req.word,
        word_info=req.word_info,
    )
    if vocab is None:
        return fail(400, "加入失败（已存在或参数非法）")

    return ok(data={
        "vocab_uuid": vocab.vocab_uuid,
        "word": vocab.word,
        "created_at": vocab.created_at.isoformat() if vocab.created_at else None,
    }, msg="已加入生词本")


@router.get("")
def list_vocabulary(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
):
    """生词本列表（摘要）"""
    result = vocab_module.list_vocabulary(user_id, limit=limit, offset=offset)
    return ok(data=result)


@router.get("/{vocab_uuid}")
def get_vocabulary(
    vocab_uuid: str,
    user_id: int = Depends(get_current_user_id),
):
    """生词详情（完整 word_info）"""
    item = vocab_module.get_vocabulary(vocab_uuid, user_id)
    if item is None:
        return fail(404, "生词不存在")
    return ok(data=item)


@router.delete("/{vocab_uuid}")
def delete_vocabulary(
    vocab_uuid: str,
    user_id: int = Depends(get_current_user_id),
):
    """删除生词（进回收站）"""
    if not recycle.delete_vocabulary(vocab_uuid, user_id):
        return fail(400, "删除失败（不存在或已在回收站）")
    return ok(msg="已移入回收站")