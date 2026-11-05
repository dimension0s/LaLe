"""
回收站路由测试
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.auth.pg_data_manager.database import get_session
from tests.auth.pg_data_manager.orm_models import (
    UserDocument, UserNote, Integration, RecycleBin,
)
from user_manager import recycle


# ============================================================
# 文件列表
# ============================================================
class TestRecycleList:

    def test_list_empty(self, client, test_user, auth_header):
        r = client.get("/api/recycle", headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert body["data"] == []

    def test_list_after_delete(
        self, client, test_doc_with_notes, auth_header,
    ):
        # 删一个文档进回收站
        recycle.delete_document(test_doc_with_notes["doc_id"], test_doc_with_notes.get("user_id", 1))
        # 注：这里用路由更真实，但 fixture 没暴露 user_id，直接用 recycle
        # 简化：直接调用，测试列表接口
        r = client.get("/api/recycle", headers=auth_header)
        assert r.status_code == 200


# ============================================================
# 恢复文件
# ============================================================
class TestRecycleRestore:

    def _put_in_recycle(self, doc_id: int, user_id: int):
        recycle.delete_document(doc_id, user_id)

    def test_restore_document(
        self, client, test_doc, test_user, auth_header,
    ):
        recycle.delete_document(test_doc["doc_id"], test_user)

        r = client.post(
            "/api/recycle/restore",
            json={
                "file_type": "user_document",
                "file_id": test_doc["doc_uuid"],
            },
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0

        with get_session() as s:
            d = s.query(UserDocument).filter_by(
                doc_uuid=test_doc["doc_uuid"],
            ).first()
            assert d.status == "active"
            rb = s.query(RecycleBin).filter_by(
                file_type="user_document", file_id=test_doc["doc_id"],
            ).first()
            assert rb is None

    def test_restore_note(
        self, client, test_doc_with_notes, test_user, auth_header,
    ):
        uuid = test_doc_with_notes["note_uuids"][0]
        recycle.delete_note(uuid, test_user)

        r = client.post(
            "/api/recycle/restore",
            json={"file_type": "user_note", "file_id": uuid},
            headers=auth_header,
        )
        assert r.json()["code"] == 0

        with get_session() as s:
            n = s.query(UserNote).filter_by(note_uuid=uuid).first()
            assert n.status == "active"

    def test_restore_integration(
        self, client, test_doc_with_integration, test_user, auth_header,
    ):
        uuid = test_doc_with_integration["integration_uuid"]
        recycle.delete_integration(uuid, test_user)

        r = client.post(
            "/api/recycle/restore",
            json={"file_type": "integration", "file_id": uuid},
            headers=auth_header,
        )
        assert r.json()["code"] == 0

        with get_session() as s:
            i = s.query(Integration).filter_by(integration_uuid=uuid).first()
            assert i.status == "active"
            # 原笔记 is_integrated 恢复 True
            notes = s.query(UserNote).filter(
                UserNote.note_uuid.in_(test_doc_with_integration["note_uuids"]),
            ).all()
            assert all(n.is_integrated for n in notes)

    def test_restore_not_in_recycle(
        self, client, test_doc, auth_header,
    ):
        # 没删就恢复
        r = client.post(
            "/api/recycle/restore",
            json={
                "file_type": "user_document",
                "file_id": test_doc["doc_uuid"],
            },
            headers=auth_header,
        )
        assert r.json()["code"] == 400

    def test_restore_bad_type(self, client, test_user, auth_header):
        r = client.post(
            "/api/recycle/restore",
            json={"file_type": "unknown", "file_id": "x"},
            headers=auth_header,
        )
        assert r.status_code == 422


# ============================================================
# 彻底删除文件
# ============================================================
class TestRecyclePermanentDelete:

    def test_permanent_delete(self, client, test_doc, test_user, auth_header):
        # 1. 先放入回收站
        recycle.delete_document(test_doc["doc_id"], test_user)

        # 2. 查回收站记录拿到 recycle_id 和 file_id，并验证 preview_text 字段
        r = client.get("/api/recycle", headers=auth_header)
        item = r.json()["data"][0]
        assert item["preview_text"] is not None

        # 3. 调用彻底删除接口
        payload = {
            "items": [
                {"file_type": item["file_type"], "file_id": item["file_id"]}
            ]
        }
        r2 = client.request(
            "DELETE",
            "/api/recycle/permanent",
            json=payload,
            headers=auth_header
        )
        assert r2.json()["code"] == 0

        # 4. 验证数据库：确认物理记录彻底没了，且回收站列表已清空
        r3 = client.get("/api/recycle", headers=auth_header)
        assert len(r3.json()["data"]) == 0

        with get_session() as s:
            from tests.auth.pg_data_manager.orm_models import UserDocument
            # 文档记录应该被彻底删除
            doc = s.query(UserDocument).filter_by(id=test_doc["doc_id"]).first()
            assert doc is None