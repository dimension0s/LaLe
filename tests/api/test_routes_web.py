import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _fake_web_search(query, **kwargs):
    return f"[1] 假新闻标题\n    URL: https://example.com\n    内容: 关于 {query} 的搜索结果"


@pytest.fixture(autouse=True)
def mock_web_search(monkeypatch):
    # 替换 routes 中引入的函数
    from api.routes import web as web_routes
    monkeypatch.setattr(web_routes, "web_search_tool", _fake_web_search)


class TestWebSearch:

    def test_search_ok(self, client, test_user, auth_header):
        payload = {"query": "人工智能", "max_results": 3}
        r = client.post("/api/web/search", json=payload, headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert "假新闻标题" in body["data"]["result"]
        assert "人工智能" in body["data"]["result"]

    def test_search_empty_query(self, client, test_user, auth_header):
        r = client.post("/api/web/search", json={"query": ""}, headers=auth_header)
        assert r.status_code == 422

    def test_search_bad_depth(self, client, test_user, auth_header):
        payload = {"query": "AI", "search_depth": "invalid"}
        r = client.post("/api/web/search", json=payload, headers=auth_header)
        assert r.status_code == 422

    def test_search_no_token(self, client):
        r = client.post("/api/web/search", json={"query": "AI"})
        assert r.status_code == 401