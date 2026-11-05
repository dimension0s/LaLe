"""
笔记路由测试：加入 / 分组 / 按日期 / 详情 / 删除
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.auth.pg_data_manager.database import get_session
from tests.auth.pg_data_manager.orm_models import UserNote, RecycleBin


# ============================================================
# 加入笔记
# ============================================================
class TestAddNote:

    def test_add_note_ok(self, client, test_doc, auth_header):
        payload = {
            "document_id": test_doc["doc_id"],
            "note_type": "translation",
            "content": "## 翻译\n测试内容",
        }
        r = client.post("/api/notes", json=payload, headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["note_type"] == "translation"
        assert body["data"]["is_integrated"] is False

    def test_add_note_invalid_type(self, client, test_doc, auth_header):
        payload = {
            "document_id": test_doc["doc_id"],
            "note_type": "invalid_type",
            "content": "x",
        }
        r = client.post("/api/notes", json=payload, headers=auth_header)
        # Pydantic pattern 校验失败 → 422
        assert r.status_code == 422

    def test_add_note_empty_content(self, client, test_doc, auth_header):
        payload = {
            "document_id": test_doc["doc_id"],
            "note_type": "grammar",
            "content": "",
        }
        r = client.post("/api/notes", json=payload, headers=auth_header)
        assert r.status_code == 422

    def test_add_note_doc_not_exist(self, client, test_user, auth_header):
        payload = {
            "document_id": 99999,
            "note_type": "grammar",
            "content": "x",
        }
        r = client.post("/api/notes", json=payload, headers=auth_header)
        assert r.json()["code"] == 400


# ============================================================
# 分组 / 按日期
# ============================================================
class TestNoteQuery:

    def test_grouped_ok(self, client, test_doc_with_notes, auth_header):
        r = client.get(
            f"/api/notes/grouped?document_id={test_doc_with_notes['doc_id']}",
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["document"]["doc_id"] == test_doc_with_notes["doc_id"]
        # 至少有一个模块下有日期格子
        total_cells = sum(
            len(v) for k, v in data.items() if k != "document"
        )
        assert total_cells >= 1

    def test_grouped_doc_not_found(self, client, test_user, auth_header):
        r = client.get(
            "/api/notes/grouped?document_id=99999", headers=auth_header,
        )
        assert r.json()["code"] == 404

    def test_by_date_ok(self, client, test_doc_with_notes, auth_header):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        r = client.get(
            f"/api/notes/by_date?document_id={test_doc_with_notes['doc_id']}"
            f"&note_type=translation&date={today}",
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        assert len(body["data"]) >= 1

    def test_get_note_ok(self, client, test_doc_with_notes, auth_header):
        uuid = test_doc_with_notes["note_uuids"][0]
        r = client.get(f"/api/notes/{uuid}", headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["note_uuid"] == uuid

    def test_get_note_not_found(self, client, test_user, auth_header):
        r = client.get(
            "/api/notes/00000000-0000-0000-0000-000000000000",
            headers=auth_header,
        )
        assert r.json()["code"] == 404

    def test_update_note_ok(self, client, test_doc_with_notes, auth_header):
        uuid = test_doc_with_notes["note_uuids"][0]
        payload = {"content": "## 更新后的内容\n测试"}
        r = client.patch(f"/api/notes/{uuid}", json=payload, headers=auth_header)
        assert r.json()["code"] == 0

        # 验证查询
        r2 = client.get(f"/api/notes/{uuid}", headers=auth_header)
        assert r2.json()["data"]["content"] == "## 更新后的内容\n测试"


# ============================================================
# 删除笔记
# ============================================================
class TestDeleteNote:

    def test_delete_note_ok(self, client, test_doc_with_notes, auth_header):
        uuid = test_doc_with_notes["note_uuids"][0]
        r = client.delete(f"/api/notes/{uuid}", headers=auth_header)
        body = r.json()
        assert body["code"] == 0

        with get_session() as s:
            n = s.query(UserNote).filter_by(note_uuid=uuid).first()
            assert n.status == "deleted"
            rb = s.query(RecycleBin).filter_by(
                file_type="user_note", file_id=n.id,
            ).first()
            assert rb is not None

    def test_delete_note_not_found(self, client, test_user, auth_header):
        r = client.delete(
            "/api/notes/00000000-0000-0000-0000-000000000000",
            headers=auth_header,
        )
        assert r.json()["code"] == 400