"""
搜索路由测试
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestSearch:

    def test_search_files(self, client, test_doc, auth_header):
        # test_doc.file_name = "test.pdf"
        r = client.get(
            "/api/search?keyword=test&search_type=file",
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["total_files"] >= 1

    def test_search_notes(self, client, test_doc_with_notes, auth_header):
        # 笔记内容含 "翻译"
        r = client.get(
            "/api/search?keyword=翻译&search_type=note",
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["total_notes"] >= 1

    def test_search_all(self, client, test_doc_with_notes, auth_header):
        r = client.get(
            "/api/search?keyword=笔记", headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        assert "files" in body["data"]
        assert "notes" in body["data"]

    def test_search_empty_keyword(self, client, test_user, auth_header):
        r = client.get("/api/search?keyword=", headers=auth_header)
        # min_length=1 → 422
        assert r.status_code == 422

    def test_search_no_token(self, client):
        r = client.get("/api/search?keyword=test")
        assert r.status_code == 401