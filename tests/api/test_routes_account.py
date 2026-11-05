"""
路由层测试：用 TestClient 走真实 HTTP 语义，但 DB 是 user_files_test。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from user_account_manager import auth as auth_module
from user_account_manager.jwt_utils import create_token


def _auth_header(user_id: int) -> dict:
    token = create_token(user_id, "uuid-test")
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# /api/auth
# ============================================================
class TestAuthRoutes:

    def test_send_code_ok(self, client):
        r = client.post("/api/auth/send_code", json={"phone_number": "13900000001"})
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0

    def test_send_code_bad_phone(self, client):
        r = client.post("/api/auth/send_code", json={"phone_number": "123"})
        # Pydantic 校验失败 → 422
        assert r.status_code == 422
        assert r.json()["code"] == 422

    def test_login_new_user(self, client):
        r = client.post("/api/auth/login", json={"phone_number": "13900000001"})
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["is_new_user"] is True
        assert body["data"]["token"]
        assert body["data"]["user"]["phone_number"] == "13900000001"

    def test_login_existing_user(self, client, test_user):
        r = client.post("/api/auth/login", json={"phone_number": "13900000001"})
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["is_new_user"] is False

    def test_login_bad_phone(self, client):
        r = client.post("/api/auth/login", json={"phone_number": "123"})
        assert r.status_code == 422

    def test_logout(self, client, test_user):
        r = client.post(
            "/api/auth/logout",
            headers=_auth_header(test_user),
        )
        assert r.status_code == 200
        assert r.json()["code"] == 0


# ============================================================
# /api/account
# ============================================================
class TestAccountRoutes:

    def test_get_account_ok(self, client, test_user):
        r = client.get("/api/account", headers=_auth_header(test_user))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["id"] == test_user

    def test_get_account_no_token(self, client):
        r = client.get("/api/account")
        assert r.status_code == 401
        body = r.json()
        assert body["code"] == 401
        assert "缺少" in body["msg"]

    def test_get_account_bad_token(self, client):
        r = client.get(
            "/api/account",
            headers={"Authorization": "Bearer bad.token"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == 401

    def test_get_account_nonexistent_user(self, client):
        # 用不存在的 user_id 造 token
        r = client.get("/api/account", headers=_auth_header(99999))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 404
        assert "不存在" in body["msg"]

    def test_update_nickname_ok(self, client, test_user):
        r = client.patch(
            "/api/account/nickname",
            json={"nickname": "新昵称"},
            headers=_auth_header(test_user),
        )
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_update_nickname_empty(self, client, test_user):
        r = client.patch(
            "/api/account/nickname",
            json={"nickname": "   "},
            headers=_auth_header(test_user),
        )
        body = r.json()
        assert body["code"] == 400

    def test_update_avatar_ok(self, client, test_user):
        r = client.patch(
            "/api/account/avatar",
            json={"avatar_url": "https://x.com/a.png"},
            headers=_auth_header(test_user),
        )
        assert r.json()["code"] == 0

    def test_bind_email_ok(self, client, test_user):
        r = client.post(
            "/api/account/email",
            json={"email": "a@b.com"},
            headers=_auth_header(test_user),
        )
        assert r.json()["code"] == 0

    def test_bind_email_bad_format(self, client, test_user):
        r = client.post(
            "/api/account/email",
            json={"email": "abc"},
            headers=_auth_header(test_user),
        )
        assert r.json()["code"] == 400

    def test_bind_wechat_ok(self, client, test_user):
        r = client.post(
            "/api/account/wechat",
            json={"wechat_openid": "wx_1"},
            headers=_auth_header(test_user),
        )
        assert r.json()["code"] == 0

    def test_delete_account_ok(self, client, test_user):
        r = client.delete("/api/account", headers=_auth_header(test_user))
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 删完再查 → 404
        r2 = client.get("/api/account", headers=_auth_header(test_user))
        assert r2.json()["code"] == 404

    def test_delete_nonexistent(self, client):
        r = client.delete("/api/account", headers=_auth_header(99999))
        assert r.json()["code"] == 400