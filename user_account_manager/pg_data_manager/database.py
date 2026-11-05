"""
database.py - 用户账号模块的数据库连接

职责:
- 连接 user_files 库（和 user_documents 同库）
- 提供 Session 管理
- 提供初始化函数

说明:
- 复用 .env 中的 PG_* 配置
- 库名固定为 user_files
"""

import os
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .orm_models import Base


# ============================================================
# 环境变量
# ============================================================
# 路径计算：database.py → pg_data_manager/ → user_account_manager/ → LaLe/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# ============================================================
# 数据库连接配置
# ============================================================
DB_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "database": "user_files",           # ← 固定同库
    "user": os.getenv("PG_USER", "lale_user"),
    "password": os.getenv("PG_PASSWORD", ""),
}

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)


# ============================================================
# 引擎 + Session
# ============================================================
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


# ============================================================
# Session 上下文管理器
# ============================================================
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


# ============================================================
# 初始化
# ============================================================
def init_db():
    """创建表（如果不存在）"""
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """删除所有表（谨慎使用）"""
    Base.metadata.drop_all(bind=engine)


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("用户账号 - 数据库初始化")
    print("=" * 60)
    print(f"数据库: {DB_CONFIG['database']} @ {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"用户: {DB_CONFIG['user']}")
    print(f"密码: {'已设置' if DB_CONFIG['password'] else '未设置'}")
    print("=" * 60)

    try:
        init_db()
        print("✅ 表结构创建成功")

        print("\n已创建的表:")
        for table in Base.metadata.tables:
            print(f"  - {table}")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        raise