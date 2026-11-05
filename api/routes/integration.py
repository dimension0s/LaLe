"""
整合笔记路由
"""

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from api.dependencies import get_current_user_id
from api.response import ok, fail
from api.schemas.integration import IntegrateRequest
from user_manager import integrate_notes, search_notes, recycle


router = APIRouter()


@router.get("/list/all")
def get_all_integrations(
        user_id: int = Depends(get_current_user_id),
):
    """获取当前用户的所有整合笔记"""
    from user_manager.pg_data_manager.database import get_session
    from user_manager.pg_data_manager.orm_models import Integration, UserDocument
    from user_manager.search_notes import _integration_to_dict

    with get_session() as session:
        rows = session.query(Integration, UserDocument).join(
            UserDocument, Integration.document_id == UserDocument.id
        ).filter(
            Integration.user_id == user_id,
            Integration.status == "active"
        ).order_by(Integration.created_at.desc()).all()

        items = [_integration_to_dict(integ, doc) for integ, doc in rows]
        return ok(data={"items": items, "total": len(items)})

@router.post("")
async def create_integration(
    req: IntegrateRequest,
    user_id: int = Depends(get_current_user_id),
):
    """整合笔记（可能耗时 10-30 秒）"""
    integ = await run_in_threadpool(
        integrate_notes.integrate_notes, req.note_uuids, user_id,
    )
    if integ is None:
        return fail(400, "整合失败（笔记不存在或调用模型失败）")

    data = search_notes._integration_to_dict(integ)
    return ok(data=data, msg="整合成功")


@router.get("")
def list_integrations(
    document_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """某文档下的整合列表"""
    items = search_notes.list_integrations(document_id, user_id)
    return ok(data=items)


@router.get("/{integration_uuid}")
def get_integration(
    integration_uuid: str,
    user_id: int = Depends(get_current_user_id),
):
    """整合详情"""
    item = search_notes.get_integration_by_uuid(integration_uuid, user_id)
    if item is None:
        return fail(404, "整合不存在")
    return ok(data=item)

@router.delete("/{integration_uuid}/cancel")
def cancel_integration(
    integration_uuid: str,
    user_id: int = Depends(get_current_user_id),
):
    """取消合并"""
    if not recycle.cancel_integration(integration_uuid, user_id):
        return fail(400, "取消合并失败")
    return ok(msg="已取消合并")

@router.delete("/{integration_uuid}")
def delete_integration(
    integration_uuid: str,
    user_id: int = Depends(get_current_user_id),
):
    """删除整合（软删除进回收站）"""
    ok_flag = recycle.delete_integration(integration_uuid, user_id)
    if not ok_flag:
        return fail(400, "删除失败（不存在或已在回收站）")
    return ok(msg="已移入回收站")