"""
查词路由（无状态，不写库；返回 in_vocabulary + vocab_uuid 供前端切换 +/√）
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_current_user_id
from api.response import ok, fail
from api.schemas.vocabulary import LookupRequest
from vocabulary.arrange_word import lookup_raw
from user_manager import vocabulary as vocab_module


router = APIRouter()


@router.post("/lookup")
def lookup(
    req: LookupRequest,
    user_id: int = Depends(get_current_user_id),
):
    """查词（本地牛津词典）"""
    entry = lookup_raw(req.word)
    if entry is None:
        return fail(404, f"未找到单词: {req.word}")

    vocab = vocab_module.get_vocabulary_by_word(user_id, req.word)

    return ok(data={
        "word": req.word.strip().lower(),
        "found": True,
        "word_info": entry,
        "in_vocabulary": vocab is not None,
        "vocab_uuid": vocab.vocab_uuid if vocab else None,   # ← 新增
    })