# tests/auth/test_account_auth.py
import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.auth.pg_data_manager.database import get_session
from tests.auth.pg_data_manager.orm_models import (
    UserAccount, UserDocument, UserNote, Integration, RecycleBin,
)

from user_account_manager import auth, account
from user_account_manager.jwt_utils import create_token, decode_token


# ============================================================
# 1. jwt_utils
# ============================================================
class TestJwtUtils:

    def test_create_and_decode(self):
        token = create_token(1, "uuid-test-1234")
        payload = decode_token(token)
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["user_uuid"] == "uuid-test-1234"
        assert "exp" in payload and "iat" in payload

    def test_decode_with_bearer_prefix(self):
        token = create_token(1, "uuid")
        payload = decode_token(f"Bearer {token}")
        assert payload["user_id"] == 1

    def test_decode_invalid_token(self):
        assert decode_token("invalid.token.here") is None

    def test_decode_empty_token(self):
        assert decode_token("") is None
        assert decode_token(None) is None

    def test_get_user_id_from_token(self):
        from user_account_manager.jwt_utils import get_user_id_from_token
        token = create_token(42, "uuid")
        assert get_user_id_from_token(token) == 42

    def test_get_user_uuid_from_token(self):
        from user_account_manager.jwt_utils import get_user_uuid_from_token
        token = create_token(1, "my-uuid")
        assert get_user_uuid_from_token(token) == "my-uuid"


# ============================================================
# 2. auth - send_code
# ============================================================
class TestSendCode:

    def test_empty_phone(self):
        assert auth.send_code("") is False
        assert auth.send_code(None) is False

    def test_invalid_phone_format(self):
        assert auth.send_code("123") is False
        assert auth.send_code("abcdefghijk") is False
        assert auth.send_code("1380013800") is False   # 10 位

    def test_valid_phone_dev_mode(self):
        # AUTH_DEV_MODE=true 时固定返回 True
        assert auth.send_code("13800138000") is True


# ============================================================
# 3. auth - login
# ============================================================
class TestLogin:

    def test_new_user_created(self):
        result = auth.login("13900000001")
        assert result is not None
        assert result["is_new_user"] is True
        assert result["token"]
        assert result["user"]["phone_number"] == "13900000001"
        assert result["user"]["nickname"] == "用户0001"
        assert result["user"]["status"] == "active"

        # 库里有记录
        with get_session() as s:
            u = s.query(UserAccount).filter_by(
                phone_number="13900000001",
            ).first()
            assert u is not None
            assert u.last_login_at is not None

    def test_existing_user_login(self, test_user):
        # test_user 手机号是 13900000001
        result = auth.login("13900000001")
        assert result["is_new_user"] is False
        assert result["user"]["id"] == test_user

    def test_login_updates_last_login(self, test_user):
        with get_session() as s:
            before = s.get(UserAccount, test_user).last_login_at

        auth.login("13900000001")

        with get_session() as s:
            after = s.get(UserAccount, test_user).last_login_at

        assert after is not None
        if before is not None:
            assert after >= before

    def test_login_empty_phone(self):
        assert auth.login("") is None
        assert auth.login("   ") is None

    def test_login_deleted_user_rejected(self, test_user):
        # 把用户改成 deleted
        with get_session() as s:
            u = s.get(UserAccount, test_user)
            u.status = "deleted"

        assert auth.login("13900000001") is None

    def test_login_after_delete_creates_new_user(self, test_user):
        # 物理删除用户
        account.delete_account(test_user)

        # 同手机号再登录 → 新用户
        result = auth.login("13900000001")
        assert result is not None
        assert result["is_new_user"] is True
        assert result["user"]["id"] != test_user


# ============================================================
# 4. auth - get_user_by_token / logout
# ============================================================
class TestGetUserByToken:

    def test_valid_token(self, test_user):
        token = create_token(test_user, "uuid-x")
        user = auth.get_user_by_token(token)
        assert user is not None
        assert user["id"] == test_user

    def test_invalid_token(self):
        assert auth.get_user_by_token("bad.token") is None

    def test_token_for_nonexistent_user(self):
        token = create_token(99999, "uuid")
        assert auth.get_user_by_token(token) is None

    def test_token_for_deleted_user(self, test_user):
        token = create_token(test_user, "uuid")
        with get_session() as s:
            u = s.get(UserAccount, test_user)
            u.status = "deleted"
        assert auth.get_user_by_token(token) is None

    def test_logout_returns_true(self, test_user):
        token = create_token(test_user, "uuid")
        assert auth.logout(token) is True
        assert auth.logout("bad.token") is True


# ============================================================
# 5. account - get_account
# ============================================================
class TestGetAccount:

    def test_get_existing(self, test_user):
        info = account.get_account(test_user)
        assert info is not None
        assert info["id"] == test_user
        assert info["status"] == "active"

    def test_get_nonexistent(self):
        assert account.get_account(99999) is None

    def test_get_deleted_user_returns_none(self, test_user):
        with get_session() as s:
            u = s.get(UserAccount, test_user)
            u.status = "deleted"
        assert account.get_account(test_user) is None


# ============================================================
# 6. account - update_nickname
# ============================================================
class TestUpdateNickname:

    def test_update_success(self, test_user):
        assert account.update_nickname(test_user, "新昵称") is True
        with get_session() as s:
            assert s.get(UserAccount, test_user).nickname == "新昵称"

    def test_empty_nickname(self, test_user):
        assert account.update_nickname(test_user, "") is False
        assert account.update_nickname(test_user, "   ") is False

    def test_nickname_too_long(self, test_user):
        assert account.update_nickname(test_user, "a" * 101) is False

    def test_nickname_strips_whitespace(self, test_user):
        assert account.update_nickname(test_user, "  张三  ") is True
        with get_session() as s:
            assert s.get(UserAccount, test_user).nickname == "张三"

    def test_update_nonexistent_user(self):
        assert account.update_nickname(99999, "x") is False


# ============================================================
# 7. account - update_avatar
# ============================================================
class TestUpdateAvatar:

    def test_update_success(self, test_user):
        url = "https://example.com/a.png"
        assert account.update_avatar(test_user, url) is True
        with get_session() as s:
            assert s.get(UserAccount, test_user).avatar_url == url

    def test_empty_avatar(self, test_user):
        assert account.update_avatar(test_user, "") is False
        assert account.update_avatar(test_user, "   ") is False

    def test_update_nonexistent_user(self):
        assert account.update_avatar(99999, "https://x") is False


# ============================================================
# 8. account - bind_email
# ============================================================
class TestBindEmail:

    def test_bind_success(self, test_user):
        assert account.bind_email(test_user, "a@b.com") is True
        with get_session() as s:
            assert s.get(UserAccount, test_user).email == "a@b.com"

    def test_invalid_email(self, test_user):
        assert account.bind_email(test_user, "abc") is False
        assert account.bind_email(test_user, "a@b") is False

    def test_empty_email(self, test_user):
        assert account.bind_email(test_user, "") is False

    def test_email_conflict(self, test_user):
        # 另造一个用户
        with get_session() as s:
            other = UserAccount(
                phone_number="13900000002",
                nickname="other",
                status="active",
            )
            s.add(other)
            s.flush()
            other_id = other.id

        assert account.bind_email(other_id, "dup@x.com") is True
        assert account.bind_email(test_user, "dup@x.com") is False

    def test_rebind_same_email_self(self, test_user):
        # 自己绑自己的邮箱不算冲突
        assert account.bind_email(test_user, "self@x.com") is True
        assert account.bind_email(test_user, "self@x.com") is True

    def test_bind_nonexistent_user(self):
        assert account.bind_email(99999, "a@b.com") is False


# ============================================================
# 9. account - bind_wechat
# ============================================================
class TestBindWechat:

    def test_bind_success(self, test_user):
        assert account.bind_wechat(test_user, "wx_openid_1") is True
        with get_session() as s:
            assert s.get(UserAccount, test_user).wechat_openid == "wx_openid_1"

    def test_empty_openid(self, test_user):
        assert account.bind_wechat(test_user, "") is False
        assert account.bind_wechat(test_user, "   ") is False

    def test_wechat_conflict(self, test_user):
        with get_session() as s:
            other = UserAccount(
                phone_number="13900000002",
                nickname="other",
                status="active",
            )
            s.add(other)
            s.flush()
            other_id = other.id

        assert account.bind_wechat(other_id, "wx_dup") is True
        assert account.bind_wechat(test_user, "wx_dup") is False

    def test_bind_nonexistent_user(self):
        assert account.bind_wechat(99999, "wx_x") is False


# ============================================================
# 10. account - delete_account
# ============================================================
class TestDeleteAccount:

    def test_delete_simple(self, test_user):
        assert account.delete_account(test_user) is True
        with get_session() as s:
            assert s.query(UserAccount).filter_by(id=test_user).first() is None

    def test_delete_nonexistent(self):
        assert account.delete_account(99999) is False

    def test_delete_with_data(self, test_user_with_data):
        ids = test_user_with_data
        uid = ids["user_id"]

        assert account.delete_account(uid) is True

        with get_session() as s:
            assert s.query(UserAccount).filter_by(id=uid).first() is None
            assert s.query(UserDocument).filter_by(user_id=uid).count() == 0
            assert s.query(UserNote).filter_by(user_id=uid).count() == 0
            assert s.query(Integration).filter_by(user_id=uid).count() == 0
            assert s.query(RecycleBin).filter_by(user_id=uid).count() == 0

    def test_delete_removes_upload_dir(self, test_user):
        # 造一个用户上传目录
        user_dir = account.USER_UPLOAD_DIR / str(test_user)
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "f.txt").write_text("x")

        assert account.delete_account(test_user) is True
        assert not user_dir.exists()

    def test_delete_after_delete_returns_false(self, test_user):
        assert account.delete_account(test_user) is True
        assert account.delete_account(test_user) is False


# ============================================================
# 11. 端到端
# ============================================================
class TestEndToEnd:

    def test_login_update_delete_relogin(self):
        # 1. 登录（新用户）
        r1 = auth.login("13911112222")
        assert r1["is_new_user"] is True
        uid = r1["user"]["id"]

        # 2. 用 token 拿用户
        user = auth.get_user_by_token(r1["token"])
        assert user["id"] == uid

        # 3. 改昵称
        assert account.update_nickname(uid, "E2E") is True
        assert account.get_account(uid)["nickname"] == "E2E"

        # 4. 注销
        assert account.delete_account(uid) is True
        assert account.get_account(uid) is None

        # 5. 旧 token 失效
        assert auth.get_user_by_token(r1["token"]) is None

        # 6. 同手机号重新登录 → 新用户
        r2 = auth.login("13911112222")
        assert r2["is_new_user"] is True
        assert r2["user"]["id"] != uid