"""
文档路由：上传 / 列表 / 详情 / 删除
"""

from fastapi import APIRouter, Depends, File, UploadFile

from api.dependencies import get_current_user_id
from api.response import ok, fail
from user_manager import upload as upload_module
from user_manager import search_notes
from user_manager import recycle


router = APIRouter()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    """上传文件（multipart/form-data）"""
    if not file.filename:
        return fail(400, "文件名为空")

    doc = upload_module.upload_from_stream(
        file.file, file.filename, user_id,
    )
    if doc is None:
        return fail(400, "上传失败（文件类型不支持或解析失败）")

    data = search_notes._doc_to_dict(doc)
    return ok(data=data, msg="上传成功")


@router.get("")
def list_documents(
    user_id: int = Depends(get_current_user_id),
    include_deleted: bool = False,
):
    """文档列表"""
    docs = search_notes.list_documents(user_id, include_deleted=include_deleted)
    return ok(data=docs)


@router.get("/{doc_uuid}")
def get_document(
    doc_uuid: str,
    user_id: int = Depends(get_current_user_id),
):
    """文档详情"""
    doc = search_notes.get_document_by_uuid(doc_uuid, user_id)
    if doc is None:
        return fail(404, "文档不存在")
    return ok(data=doc)


@router.delete("/{doc_uuid}")
def delete_document(
    doc_uuid: str,
    user_id: int = Depends(get_current_user_id),
):
    """删除文档（软删除进回收站）"""
    doc = search_notes.get_document_by_uuid(doc_uuid, user_id)
    if doc is None:
        return fail(404, "文档不存在")

    ok_flag = recycle.delete_document(doc["doc_id"], user_id)
    if not ok_flag:
        return fail(400, "删除失败")
    return ok(msg="已移入回收站")