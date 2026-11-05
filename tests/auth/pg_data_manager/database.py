# tests/auth/pg_data_manager/database.py
"""
测试库连接：user_files_test
- 用户仍是 lale_user
- 只换库名
- 提供 get_session / init_test_db / drop_test_db
"""

import os
import sys
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.auth.pg_data_manager.orm_models import (
    AccountBase, UserManagerBase,
)

ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

TEST_DB_NAME = os.getenv("PG_TEST_DB", "user_files_test")

DB_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "database": TEST_DB_NAME,
    "user": os.getenv("PG_USER", "lale_user"),
    "password": os.getenv("PG_PASSWORD", ""),
}

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=3,
    max_overflow=5,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_test_db():
    """建表：两个 Base 各建一次"""
    AccountBase.metadata.create_all(bind=engine)
    UserManagerBase.metadata.create_all(bind=engine)


def drop_test_db():
    """删表（测试清理用）"""
    UserManagerBase.metadata.drop_all(bind=engine)
    AccountBase.metadata.drop_all(bind=engine)


def ensure_test_database_exists():
    """
    确保 user_files_test 库存在。
    连到 postgres 维护库执行 CREATE DATABASE（幂等）。
    需要 lale_user 有 CREATEDB 权限，或提前手工建好。
    """
    admin_url = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/postgres"
    )
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": TEST_DB_NAME},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
                print(f"✅ 已创建测试库: {TEST_DB_NAME}")
            else:
                print(f"ℹ️ 测试库已存在: {TEST_DB_NAME}")
    finally:
        admin_engine.dispose()