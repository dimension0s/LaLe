from fastapi import APIRouter, Depends
from api.dependencies import get_current_user_id
from api.response import ok
from user_manager import search_notes, recycle, vocabulary

router = APIRouter()


@router.get("/stats")
def get_dashboard_stats(user_id: int = Depends(get_current_user_id)):
    """获取主界面四大模块统计数据"""
    files_count = search_notes.count_documents(user_id)
    notes_count = search_notes.count_notes(user_id)
    vocab_count = search_notes.count_vocabulary(user_id)
    recycle_count = len(recycle.list_recycle_bin(user_id))

    return ok(data={
        "files": files_count,
        "notes": notes_count,
        "vocabulary": vocab_count,
        "recycle": recycle_count
    })