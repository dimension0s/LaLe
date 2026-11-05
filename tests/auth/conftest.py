# tests/auth/conftest.py
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.auth.pg_data_manager import database as test_db
from tests.auth.pg_data_manager.database import (
    engine, get_session, init_test_db, ensure_test_database_exists,
)
from tests.auth.pg_data_manager.orm_models import (
    UserAccount, UserDocument, UserNote, Integration, RecycleBin,
)
from user_account_manager import auth as auth_module
from user_account_manager import account as account_module


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    ensure_test_database_exists()
    init_test_db()
    yield


@pytest.fixture(autouse=True)
def clean_tables(setup_test_database):
    """每个测试前清空所有表（TRUNCATE 比 DELETE 快，且重置自增序列）"""
    with engine.begin() as conn:
        conn.execute(text(
            # 加上 user_vocabulary
            "TRUNCATE TABLE recycle_bin, integration, user_notes, "
            "user_documents, user_account, user_vocabulary RESTART IDENTITY CASCADE"
        ))
    yield


@pytest.fixture(autouse=True)
def patch_get_session(monkeypatch, clean_tables):
    """
    把 auth / account 里的 get_session 换成测试库的 get_session。
    这是测试隔离的关键：被测代码必须操作 user_files_test。
    """
    monkeypatch.setattr(auth_module, "get_session", test_db.get_session)
    monkeypatch.setattr(account_module, "get_session", test_db.get_session)
    yield


@pytest.fixture
def test_user():
    with get_session() as session:
        user = UserAccount(
            phone_number="13900000001",
            nickname="测试用户",
            avatar_url="",
            status="active",
        )
        session.add(user)
        session.flush()
        user_id = user.id
    return user_id


@pytest.fixture
def test_user_with_data(test_user):
    with get_session() as session:
        doc = UserDocument(
            user_id=test_user,
            file_name="test.pdf",
            file_type="pdf",
            file_path=f"/tmp/test_{test_user}.pdf",
        )
        session.add(doc)
        session.flush()

        note = UserNote(
            user_id=test_user,
            document_id=doc.id,
            note_type="translation",
            content="测试笔记",
        )
        session.add(note)

        integration = Integration(
            user_id=test_user,
            document_id=doc.id,
            source_modules=["translation"],
            source_note_ids=[],
            content="整合内容",
        )
        session.add(integration)
        session.flush()

        recycle = RecycleBin(
            user_id=test_user,
            file_type="user_document",
            file_id=doc.id,
            expires_at=datetime.now() + timedelta(days=15),
        )
        session.add(recycle)
        session.flush()

        ids = {
            "user_id": test_user,
            "doc_id": doc.id,
            "note_id": note.id,
            "integration_id": integration.id,
            "recycle_id": recycle.id,
        }
    return ids