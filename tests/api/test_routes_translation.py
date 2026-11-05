"""
翻译路由测试（mock 掉底层模型调用）
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from translation.core import TranslationResult


# 构造一个假的翻译结果
def _fake_translate(
    text: str,
    source_lang: str = "自动检测",
    target_lang: str = "中文",
    mode: str = "direct",
    use_tools: bool = True,
    return_trace: bool = False,
):
    result = TranslationResult(
        original_text=text,
        translated_text="这是翻译后的测试结果",
        mode=mode,
        source_lang=source_lang,
        target_lang=target_lang,
        model_name="deepseek-mock",
        elapsed_ms=100,
        rounds=1,
    )
    if return_trace:
        return result, None  # trace 暂时 mock 为 None
    return result


@pytest.fixture(autouse=True)
def mock_translation(monkeypatch):
    """mock 掉 route 里的 translate 函数"""
    from api.routes import translation as trans_routes
    monkeypatch.setattr(trans_routes, "translate", _fake_translate)


# ============================================================
# 翻译测试
# ============================================================
class TestTranslation:

    def test_translate_ok(self, client, test_user, auth_header):
        r = client.post(
            "/api/translation",
            json={"text": "Hello world", "mode": "direct"},
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["translated_text"] == "这是翻译后的测试结果"
        assert body["data"]["mode"] == "direct"

    def test_translate_indirect(self, client, test_user, auth_header):
        r = client.post(
            "/api/translation",
            json={"text": "Hello world", "mode": "indirect"},
            headers=auth_header,
        )
        assert r.json()["code"] == 0
        assert r.json()["data"]["mode"] == "indirect"

    def test_translate_empty_text(self, client, test_user, auth_header):
        r = client.post(
            "/api/translation",
            json={"text": ""},
            headers=auth_header,
        )
        # Pydantic min_length=1 拦截
        assert r.status_code == 422

    def test_translate_invalid_mode(self, client, test_user, auth_header):
        r = client.post(
            "/api/translation",
            json={"text": "Hello", "mode": "wrong_mode"},
            headers=auth_header,
        )
        # Pydantic pattern 拦截
        assert r.status_code == 422

    def test_translate_no_token(self, client):
        r = client.post(
            "/api/translation",
            json={"text": "Hello"},
        )
        assert r.status_code == 401