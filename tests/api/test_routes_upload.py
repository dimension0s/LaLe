"""
上传 / 文档列表 / 详情 / 删除 路由测试

上传测试 mock 掉 image_parser.parse_image，跳过 OCR。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from user_manager.parsers import image_parser
from user_manager import upload as upload_module
from tests.auth.pg_data_manager.database import get_session
from tests.auth.pg_data_manager.orm_models import UserDocument, RecycleBin


# ------------------------------------------------------------
# mock 解析器
# ------------------------------------------------------------
def _fake_parse_image(file_path: str, save_json: bool = False) -> dict:
    """假图片解析结果"""
    return {
        "file_name": Path(file_path).name,
        "file_type": "image",
        "source_channel": "file",
        "file_path": str(file_path),
        "file_size": 1024,
        "created_at": "2026-10-20T00:00:00",
        "parsed_at": "2026-10-20T00:00:00",
        "ocr_text": "假 OCR 文本",
        "ocr_success": True,
        "ocr_error": "",
        "image_width": 100,
        "image_height": 100,
        "image_mode": "RGB",
    }


@pytest.fixture(autouse=True)
def mock_image_parser(monkeypatch):
    """所有上传测试都 mock 掉 OCR"""
    monkeypatch.setattr(
        image_parser, "parse_image", _fake_parse_image,
    )


# ============================================================
# 上传
# ============================================================
class TestUpload:

    def test_upload_image_ok(self, client, test_user, auth_header):
        files = {"file": ("photo.png", b"fake png bytes", "image/png")}
        r = client.post(
            "/api/documents/upload",
            files=files,
            headers=auth_header,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["file_name"].endswith(".png")
        assert data["file_type"] == "image"
        assert data["status"] == "active"

    def test_upload_persists_to_db(self, client, test_user, auth_header):
        files = {"file": ("a.png", b"x", "image/png")}
        r = client.post("/api/documents/upload", files=files, headers=auth_header)
        doc_uuid = r.json()["data"]["doc_uuid"]

        with get_session() as s:
            doc = s.query(UserDocument).filter_by(doc_uuid=doc_uuid).first()
            assert doc is not None
            assert doc.user_id == test_user
            assert doc.status == "active"

    def test_upload_unsupported_type(self, client, test_user, auth_header):
        # .epub 不在 _dispatch_parser 里
        files = {"file": ("book.epub", b"x", "application/epub+zip")}
        r = client.post(
            "/api/documents/upload", files=files, headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 400

    def test_upload_no_token(self, client):
        files = {"file": ("a.png", b"x", "image/png")}
        r = client.post("/api/documents/upload", files=files)
        assert r.status_code == 401

    # def test_upload_empty_filename(self, client, test_user, auth_header):
    #     files = {"file": ("", b"x", "image/png")}
    #     r = client.post(
    #         "/api/documents/upload", files=files, headers=auth_header,
    #     )
    #     # filename 为空 → 400 或 422
    #     assert r.status_code in (400, 422)
    def test_upload_missing_file(self, client, test_user, auth_header):
        r = client.post(
            "/api/documents/upload",
            data={"other": "x"},
            headers=auth_header,
        )
        # 缺 file 字段 → 422（现在是干净的统一格式了）
        assert r.status_code == 422
        assert r.json()["code"] == 422


# ============================================================
# 列表 / 详情
# ============================================================
class TestDocumentList:

    def test_list_documents(self, client, test_doc, auth_header):
        r = client.get("/api/documents", headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert len(body["data"]) == 1
        assert body["data"][0]["doc_uuid"] == test_doc["doc_uuid"]

    def test_list_excludes_deleted(self, client, test_doc, auth_header):
        # 把文档标记为 deleted
        with get_session() as s:
            d = s.query(UserDocument).filter_by(
                doc_uuid=test_doc["doc_uuid"],
            ).first()
            d.status = "deleted"

        r = client.get("/api/documents", headers=auth_header)
        assert r.json()["data"] == []

    def test_get_document_ok(self, client, test_doc, auth_header):
        r = client.get(
            f"/api/documents/{test_doc['doc_uuid']}", headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["doc_uuid"] == test_doc["doc_uuid"]

    def test_get_document_not_found(self, client, test_user, auth_header):
        r = client.get(
            "/api/documents/00000000-0000-0000-0000-000000000000",
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 404


# ============================================================
# 删除（进回收站）
# ============================================================
class TestDeleteDocument:

    def test_delete_ok(self, client, test_doc, auth_header):
        r = client.delete(
            f"/api/documents/{test_doc['doc_uuid']}", headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0

        with get_session() as s:
            d = s.query(UserDocument).filter_by(
                doc_uuid=test_doc["doc_uuid"],
            ).first()
            assert d.status == "deleted"

            rb = s.query(RecycleBin).filter_by(
                file_type="user_document",
                file_id=test_doc["doc_id"],
            ).first()
            assert rb is not None

    def test_delete_not_found(self, client, test_user, auth_header):
        r = client.delete(
            "/api/documents/00000000-0000-0000-0000-000000000000",
            headers=auth_header,
        )
        assert r.json()["code"] == 404