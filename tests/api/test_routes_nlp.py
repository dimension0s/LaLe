import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from grammar.core import GrammarResult
from terminology.core import TerminologyResult
from phrase.core import PhraseResult


# 假数据
def _fake_grammar(text, source_lang, use_tools, return_trace):
    res = GrammarResult(text, "语法解析测试", source_lang, "mock", 100, 1)
    return (res, None) if return_trace else res

def _fake_terminology(text, source_lang, target_lang, use_tools, return_trace):
    res = TerminologyResult(text, "术语识别测试", source_lang, target_lang, "mock", 100, 1)
    return (res, None) if return_trace else res

def _fake_phrase(text, source_lang, target_lang, use_tools, return_trace):
    res = PhraseResult(text, "词组识别测试", source_lang, target_lang, "mock", 100, 1)
    return (res, None) if return_trace else res


@pytest.fixture(autouse=True)
def mock_nlp(monkeypatch):
    from api.routes import nlp as nlp_routes
    monkeypatch.setattr(nlp_routes, "parse_grammar", _fake_grammar)
    monkeypatch.setattr(nlp_routes, "parse_terminology", _fake_terminology)
    monkeypatch.setattr(nlp_routes, "parse_phrase", _fake_phrase)


class TestNLPRoutes:

    def test_grammar_ok(self, client, test_user, auth_header):
        r = client.post("/api/nlp/grammar", json={"text": "Test"}, headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["analysis"] == "语法解析测试"

    def test_terminology_ok(self, client, test_user, auth_header):
        r = client.post("/api/nlp/terminology", json={"text": "Test"}, headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["analysis"] == "术语识别测试"

    def test_phrase_ok(self, client, test_user, auth_header):
        r = client.post("/api/nlp/phrase", json={"text": "Test"}, headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["analysis"] == "词组识别测试"

    def test_empty_text(self, client, test_user, auth_header):
        r = client.post("/api/nlp/grammar", json={"text": ""}, headers=auth_header)
        assert r.status_code == 422

    def test_no_token(self, client):
        r = client.post("/api/nlp/grammar", json={"text": "Test"})
        assert r.status_code == 401