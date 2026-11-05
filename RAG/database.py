"""
database.py - RAG 模块的数据库连接与初始化
路径: /home/bina/LaLe/RAG/database.py
"""

import os
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from .orm_models import Base


# 环境变量
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


DB_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "database": os.getenv("PG_DATABASE", "lale_rag"),
    "user": os.getenv("PG_USER", "lale"),
    "password": os.getenv("PG_PASSWORD", ""),
}

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
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
    """获取数据库会话"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """创建所有表（如果不存在）"""
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """删除所有表（谨慎使用）"""
    Base.metadata.drop_all(bind=engine)


def create_fulltext_index():
    """创建全文索引（使用 jiebacfg 中文分词）"""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chunks_content_fts
            ON chunks USING GIN(to_tsvector('jiebacfg', content))
        """))
        conn.commit()



if __name__ == "__main__":
    print("=" * 60)
    print("RAG 数据库初始化")
    print("=" * 60)
    print(f"数据库: {DB_CONFIG['database']} @ {DB_CONFIG['host']}:{DB_CONFIG['port']}")

    try:
        init_db()
        print("✅ 表结构创建成功")

        create_fulltext_index()
        print("✅ 全文索引创建成功")

        # ❌ 不再调用 init_default_index_meta()

        print("\n已创建的表:")
        for table in Base.metadata.tables:
            print(f"  - {table}")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        raise