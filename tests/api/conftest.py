"""
tests/api/conftest.py

复用 tests/auth 的测试库（user_files_test）与 init/clean 逻辑，
并把 auth / account / user_manager 各模块的 get_session 替换成测试库版本。
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 复用 tests/auth 的 fixture 与测试库
from tests.auth.conftest import (   # noqa: F401
    setup_test_database, clean_tables, test_user, test_user_with_data,
)
from tests.auth.pg_data_manager import database as test_db
from tests.auth.pg_data_manager.database import get_session
from tests.auth.pg_data_manager.orm_models import (
    UserDocument, UserNote, Integration, RecycleBin,
)

# 各模块的 get_session 替换目标
from user_account_manager import auth as auth_module
from user_account_manager import account as account_module
from user_manager import (
    upload as upload_module,
    recycle as recycle_module,
    generate_notes as notes_module,
    integrate_notes as integration_module,
    search_notes as search_module,
    vocabulary as vocab_module,
)

from api.main import app


# ============================================================
# 替换 get_session（所有被测模块都指向测试库）
# ============================================================
@pytest.fixture(autouse=True)
def patch_get_session(monkeypatch, clean_tables):
    monkeypatch.setattr(auth_module, "get_session", test_db.get_session)
    monkeypatch.setattr(account_module, "get_session", test_db.get_session)
    monkeypatch.setattr(upload_module, "get_session", test_db.get_session)
    monkeypatch.setattr(recycle_module, "get_session", test_db.get_session)
    monkeypatch.setattr(notes_module, "get_session", test_db.get_session)
    monkeypatch.setattr(integration_module, "get_session", test_db.get_session)
    monkeypatch.setattr(search_module, "get_session", test_db.get_session)
    monkeypatch.setattr(vocab_module, "get_session", test_db.get_session)
    yield


# ============================================================
# TestClient
# ============================================================
@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ============================================================
# 数据 fixture
# ============================================================
@pytest.fixture
def test_doc(test_user):
    """造一条 user_documents 记录"""
    with get_session() as session:
        doc = UserDocument(
            user_id=test_user,
            file_name="test.pdf",
            file_type="pdf",
            file_path=f"/tmp/test_{test_user}.pdf",
            file_size=1024,
            status="active",
            meta={},
        )
        session.add(doc)
        session.flush()
        data = {"doc_id": doc.id, "doc_uuid": doc.doc_uuid}
    return data


@pytest.fixture
def test_doc_with_notes(test_user, test_doc):
    """造文档 + 2 条笔记（translation + grammar）"""
    with get_session() as session:
        n1 = UserNote(
            user_id=test_user,
            document_id=test_doc["doc_id"],
            note_type="translation",
            content="翻译笔记内容",
            content_size=20,
            status="active",
            is_integrated=False,
        )
        n2 = UserNote(
            user_id=test_user,
            document_id=test_doc["doc_id"],
            note_type="grammar",
            content="语法笔记内容",
            content_size=20,
            status="active",
            is_integrated=False,
        )
        session.add_all([n1, n2])
        session.flush()
        data = {
            **test_doc,
            "note_uuids": [n1.note_uuid, n2.note_uuid],
            "note_ids": [n1.id, n2.id],
        }
    return data


@pytest.fixture
def test_doc_with_integration(test_user, test_doc_with_notes):
    """造文档 + 2 条笔记 + 1 条整合"""
    with get_session() as session:
        integ = Integration(
            user_id=test_user,
            document_id=test_doc_with_notes["doc_id"],
            source_modules=["translation", "grammar"],
            source_note_ids=test_doc_with_notes["note_uuids"],
            content="整合内容",
            content_size=20,
            status="active",
        )
        session.add(integ)
        session.flush()
        integ_uuid = integ.integration_uuid
        # 把笔记标记为已整合（与业务逻辑一致）
        session.query(UserNote).filter(
            UserNote.note_uuid.in_(test_doc_with_notes["note_uuids"]),
        ).update({"is_integrated": True}, synchronize_session=False)
    return {**test_doc_with_notes, "integration_uuid": integ_uuid}


# ============================================================
# 鉴权头
# ============================================================
@pytest.fixture
def auth_header(test_user):
    from user_account_manager.jwt_utils import create_token
    token = create_token(test_user, "uuid-test")
    return {"Authorization": f"Bearer {token}"}

