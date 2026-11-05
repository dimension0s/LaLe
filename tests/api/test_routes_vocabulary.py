"""
查词 + 生词本路由测试
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.auth.pg_data_manager.database import get_session
from tests.auth.pg_data_manager.orm_models import UserVocabulary, RecycleBin



# 假牛津词条
FAKE_ENTRY = {
    "headword": "apple",
    "phonetic_uk": "/ˈæpl/",
    "phonetic_us": "/ˈæpl/",
    "pos": ["noun"],
    "senses": [
        {
            "definition": "a round fruit",
            "translation": "苹果",
            "examples": [{"english": "An apple.", "chinese": "一个苹果。"}],
        }
    ],
}


@pytest.fixture(autouse=True)
def mock_lookup(monkeypatch):
    """mock lookup_raw，避免依赖真实词典文件"""
    from api.routes import dictionary as dict_routes
    monkeypatch.setattr(
        dict_routes, "lookup_raw",
        lambda word: FAKE_ENTRY if word.lower() == "apple" else None,
    )


# ============================================================
# 查词
# ============================================================
class TestLookup:

    def test_lookup_found(self, client, test_user, auth_header):
        r = client.post(
            "/api/dictionary/lookup",
            json={"word": "apple"},
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["word"] == "apple"
        assert body["data"]["found"] is True
        assert body["data"]["in_vocabulary"] is False
        assert body["data"]["word_info"]["headword"] == "apple"

    def test_lookup_not_found(self, client, test_user, auth_header):
        r = client.post(
            "/api/dictionary/lookup",
            json={"word": "zzzznotaword"},
            headers=auth_header,
        )
        assert r.json()["code"] == 404

    def test_lookup_in_vocabulary_flag(
        self, client, test_user, auth_header,
    ):
        # 先加入生词本
        client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        # 再查词
        r = client.post(
            "/api/dictionary/lookup",
            json={"word": "apple"},
            headers=auth_header,
        )
        assert r.json()["data"]["in_vocabulary"] is True

    def test_lookup_no_token(self, client):
        r = client.post("/api/dictionary/lookup", json={"word": "apple"})
        assert r.status_code == 401

    def test_lookup_returns_vocab_uuid_when_added(
            self, client, test_user, auth_header,
    ):
        # 先加入
        add = client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        uuid = add.json()["data"]["vocab_uuid"]

        # 再查词
        r = client.post(
            "/api/dictionary/lookup",
            json={"word": "apple"},
            headers=auth_header,
        )
        data = r.json()["data"]
        assert data["in_vocabulary"] is True
        assert data["vocab_uuid"] == uuid

    def test_lookup_vocab_uuid_null_when_not_added(
            self, client, test_user, auth_header,
    ):
        r = client.post(
            "/api/dictionary/lookup",
            json={"word": "apple"},
            headers=auth_header,
        )
        data = r.json()["data"]
        assert data["in_vocabulary"] is False
        assert data["vocab_uuid"] is None


# ============================================================
# 加入生词本
# ============================================================
class TestAddVocabulary:

    def test_add_ok(self, client, test_user, auth_header):
        r = client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["word"] == "apple"
        assert body["data"]["vocab_uuid"]

    def test_add_lowercases_word(self, client, test_user, auth_header):
        r = client.post(
            "/api/vocabulary",
            json={"word": "APPLE", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        assert r.json()["data"]["word"] == "apple"

    def test_add_duplicate(self, client, test_user, auth_header):
        payload = {"word": "apple", "word_info": FAKE_ENTRY}
        client.post("/api/vocabulary", json=payload, headers=auth_header)
        r = client.post("/api/vocabulary", json=payload, headers=auth_header)
        assert r.json()["code"] == 400

    def test_add_empty_word(self, client, test_user, auth_header):
        r = client.post(
            "/api/vocabulary",
            json={"word": "", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        assert r.status_code == 422


# ============================================================
# 列表 / 详情
# ============================================================
class TestVocabularyQuery:

    def test_list_empty(self, client, test_user, auth_header):
        r = client.get("/api/vocabulary", headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0

    def test_list_after_add(self, client, test_user, auth_header):
        client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        r = client.get("/api/vocabulary", headers=auth_header)
        body = r.json()
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["word"] == "apple"
        assert body["data"]["items"][0]["first_meaning"] == "苹果"

    def test_get_detail(self, client, test_user, auth_header):
        add = client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        uuid = add.json()["data"]["vocab_uuid"]
        r = client.get(f"/api/vocabulary/{uuid}", headers=auth_header)
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["word_info"]["headword"] == "apple"

    def test_get_not_found(self, client, test_user, auth_header):
        r = client.get(
            "/api/vocabulary/00000000-0000-0000-0000-000000000000",
            headers=auth_header,
        )
        assert r.json()["code"] == 404


# ============================================================
# 删除 / 恢复
# ============================================================
class TestVocabularyDelete:

    def test_delete_ok(self, client, test_user, auth_header):
        add = client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        uuid = add.json()["data"]["vocab_uuid"]

        r = client.delete(f"/api/vocabulary/{uuid}", headers=auth_header)
        assert r.json()["code"] == 0

        with get_session() as s:
            v = s.query(UserVocabulary).filter_by(vocab_uuid=uuid).first()
            assert v.status == "deleted"
            rb = s.query(RecycleBin).filter_by(
                file_type="user_vocabulary", file_id=v.id,
            ).first()
            assert rb is not None

    def test_delete_not_found(self, client, test_user, auth_header):
        r = client.delete(
            "/api/vocabulary/00000000-0000-0000-0000-000000000000",
            headers=auth_header,
        )
        assert r.json()["code"] == 400

    def test_restore_ok(self, client, test_user, auth_header):
        add = client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        uuid = add.json()["data"]["vocab_uuid"]
        client.delete(f"/api/vocabulary/{uuid}", headers=auth_header)

        r = client.post(
            "/api/recycle/restore",
            json={"file_type": "user_vocabulary", "file_id": uuid},
            headers=auth_header,
        )
        assert r.json()["code"] == 0

        with get_session() as s:
            v = s.query(UserVocabulary).filter_by(vocab_uuid=uuid).first()
            assert v.status == "active"

    def test_restore_conflict(self, client, test_user, auth_header):
        """删除 apple → 重新加 apple → 恢复旧的应该失败"""
        add1 = client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        uuid1 = add1.json()["data"]["vocab_uuid"]
        client.delete(f"/api/vocabulary/{uuid1}", headers=auth_header)

        # 重新加
        client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )

        # 恢复旧的应该失败
        r = client.post(
            "/api/recycle/restore",
            json={"file_type": "user_vocabulary", "file_id": uuid1},
            headers=auth_header,
        )
        assert r.json()["code"] == 400

    def test_cancel_then_re_add(self, client, test_user, auth_header):
        """加入 → 取消（删除）→ 再次加入（新建）"""
        # 加入
        add1 = client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        uuid1 = add1.json()["data"]["vocab_uuid"]

        # 取消（删除）
        r = client.delete(f"/api/vocabulary/{uuid1}", headers=auth_header)
        assert r.json()["code"] == 0

        # 再次加入（应成功，新建一条）
        add2 = client.post(
            "/api/vocabulary",
            json={"word": "apple", "word_info": FAKE_ENTRY},
            headers=auth_header,
        )
        assert add2.json()["code"] == 0
        uuid2 = add2.json()["data"]["vocab_uuid"]
        assert uuid2 != uuid1  # 新记录，不同 UUID

        # 生词本里只有 1 条 active
        with get_session() as s:
            active = s.query(UserVocabulary).filter_by(
                user_id=test_user, word="apple", status="active",
            ).all()
            assert len(active) == 1