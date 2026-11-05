"""
统一搜索路由
"""

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_current_user_id
from api.response import ok
from user_manager import search_notes


router = APIRouter()


@router.get("")
def search(
    keyword: str = Query(..., min_length=1),
    search_type: str = "all",
    limit: int = 20,
    user_id: int = Depends(get_current_user_id),
):
    """统一搜索（文件 + 笔记）"""
    result = search_notes.search(
        keyword, user_id, search_type=search_type, limit=limit,
    )
    return ok(data=result)