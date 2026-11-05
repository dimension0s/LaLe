"""
整合笔记路由测试（mock DeepSeek）
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from user_manager import integrate_notes as integration_module
from tests.auth.pg_data_manager.database import get_session
from tests.auth.pg_data_manager.orm_models import Integration, UserNote


# ------------------------------------------------------------
# mock DeepSeek
# ------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_deepseek(monkeypatch):
    monkeypatch.setattr(
        integration_module, "_call_deepseek",
        lambda prompt: "## 整合结果\n\n测试整合内容",
    )


# ============================================================
# 整合
# ============================================================
class TestIntegrate:

    def test_integrate_ok(self, client, test_doc_with_notes, auth_header):
        payload = {"note_uuids": test_doc_with_notes["note_uuids"]}
        r = client.post(
            "/api/integrations", json=payload, headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["content"] == "## 整合结果\n\n测试整合内容"
        assert set(data["source_modules"]) == {"translation", "grammar"}
        assert len(data["source_note_ids"]) == 2

    def test_integrate_marks_notes_as_integrated(
        self, client, test_doc_with_notes, auth_header,
    ):
        payload = {"note_uuids": test_doc_with_notes["note_uuids"]}
        client.post("/api/integrations", json=payload, headers=auth_header)

        with get_session() as s:
            notes = s.query(UserNote).filter(
                UserNote.note_uuid.in_(test_doc_with_notes["note_uuids"]),
            ).all()
            assert all(n.is_integrated for n in notes)

    def test_integrate_less_than_2(self, client, test_doc_with_notes, auth_header):
        payload = {"note_uuids": test_doc_with_notes["note_uuids"][:1]}
        r = client.post("/api/integrations", json=payload, headers=auth_header)
        # Pydantic min_items=2 → 422
        assert r.status_code == 422

    def test_integrate_note_not_found(self, client, test_user, auth_header):
        payload = {"note_uuids": [
            "00000000-0000-0000-0000-000000000000",
            "11111111-1111-1111-1111-111111111111",
        ]}
        r = client.post("/api/integrations", json=payload, headers=auth_header)
        assert r.json()["code"] == 400


# ============================================================
# 列表 / 详情 / 删除
# ============================================================
class TestIntegrationQuery:

    def test_list_integrations(
        self, client, test_doc_with_integration, auth_header,
    ):
        r = client.get(
            f"/api/integrations?document_id={test_doc_with_integration['doc_id']}",
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        assert len(body["data"]) == 1
        assert body["data"][0]["integration_uuid"] == (
            test_doc_with_integration["integration_uuid"]
        )

    def test_get_integration(
        self, client, test_doc_with_integration, auth_header,
    ):
        uuid = test_doc_with_integration["integration_uuid"]
        r = client.get(f"/api/integrations/{uuid}", headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["integration_uuid"] == uuid

    def test_get_integration_not_found(self, client, test_user, auth_header):
        r = client.get(
            "/api/integrations/00000000-0000-0000-0000-000000000000",
            headers=auth_header,
        )
        assert r.json()["code"] == 404

    def test_delete_integration(
        self, client, test_doc_with_integration, auth_header,
    ):
        uuid = test_doc_with_integration["integration_uuid"]
        r = client.delete(f"/api/integrations/{uuid}", headers=auth_header)
        assert r.json()["code"] == 0

        with get_session() as s:
            i = s.query(Integration).filter_by(integration_uuid=uuid).first()
            assert i.status == "deleted"
            # 原笔记 is_integrated 恢复为 False
            notes = s.query(UserNote).filter(
                UserNote.note_uuid.in_(test_doc_with_integration["note_uuids"]),
            ).all()
            assert all(not n.is_integrated for n in notes)

    def test_delete_integration_not_found(self, client, test_user, auth_header):
        r = client.delete(
            "/api/integrations/00000000-0000-0000-0000-000000000000",
            headers=auth_header,
        )
        assert r.json()["code"] == 400