"""
orm_models.py - 用户账号模块的 ORM 模型

职责:
- 定义 user_account 表
- 使用 PostgreSQL（user_files 库，和 user_documents 同库）

表说明:
- user_account: 用户账号（手机号登录、昵称、头像等）
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ============================================================
# user_account 表
# ============================================================
class UserAccount(Base):
    """用户账号"""
    __tablename__ = "user_account"
    __table_args__ = (
        Index("idx_user_account_phone_number", "phone_number"),
        Index("idx_user_account_status", "status"),
        Index("idx_user_account_created_at", "created_at"),
        {"comment": "用户账号"},
    )

    # -------------------- 主键 --------------------
    id = Column(
        Integer,
        primary_key=True,
        comment="主键（PG 自增，内部用）",
    )
    user_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        comment="业务唯一ID（UUID，对外暴露）",
    )

    # -------------------- 登录信息 --------------------
    phone_number = Column(
        String(20),
        unique=True,
        nullable=False,
        comment="手机号（登录账号）",
    )
    password_hash = Column(
        String(200),
        comment="密码哈希（当前一键登录不用，预留）",
    )

    # -------------------- 个人信息 --------------------
    nickname = Column(
        String(100),
        comment="昵称",
    )
    avatar_url = Column(
        String(500),
        comment="头像 URL",
    )
    email = Column(
        String(200),
        comment="邮箱（绑定后填充）",
    )
    wechat_openid = Column(
        String(200),
        comment="微信 OpenID（绑定后填充）",
    )

    # -------------------- 状态 --------------------
    status = Column(
        String(20),
        default="active",
        nullable=False,
        comment="状态：active / deleted",
    )

    # -------------------- 时间 --------------------
    last_login_at = Column(
        DateTime,
        comment="最近登录时间",
    )
    created_at = Column(
        DateTime,
        default=datetime.now,
        comment="注册时间",
    )
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="最后修改时间",
    )

    def __repr__(self):
        return (
            f"<UserAccount(id={self.id}, "
            f"phone={self.phone!r}, "
            f"nickname={self.nickname!r}, "
            f"status={self.status!r})>"
        )