"""
orm_models.py - 用户管理模块的 ORM 模型
路径: /home/bina/LaLe/user_manager/pg_data_manager/orm_models.py

职责:
- 定义用户相关的所有表
- 使用 PostgreSQL（user_files 库）

表说明:
- user_documents: 用户上传的阅读材料
- user_notes: 用户笔记
- integration: 整合笔记
- recycle_bin: 回收站（文档/笔记/整合）
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text,
    Boolean, DateTime, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text,
    Boolean, DateTime, ForeignKey, Index, text,
)

Base = declarative_base()


# ============================================================
# 配置
# ============================================================
# 回收站保留天数
RECYCLE_BIN_DAYS = 15


# ============================================================
# 1. user_documents 表（用户文档）
# ============================================================
class UserDocument(Base):
    """用户上传的阅读材料"""
    __tablename__ = "user_documents"
    __table_args__ = (
        Index("idx_user_documents_user_id", "user_id"),
        Index("idx_user_documents_status", "status"),
        Index("idx_user_documents_file_type", "file_type"),
        Index("idx_user_documents_created_at", "created_at"),
        {"comment": "用户上传的阅读材料"},
    )

    id = Column(
        Integer,
        primary_key=True,
        comment="主键（PG 自增）",
    )
    doc_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        comment="业务唯一ID（UUID，对外暴露）",
    )

    user_id = Column(
        Integer,
        nullable=False,
        default=1,
        comment="用户 ID（阶段 1 固定为 1）",
    )

    file_name = Column(
        String(500),
        nullable=False,
        comment="文件名",
    )
    file_type = Column(
        String(20),
        nullable=False,
        comment="文件类型：pdf / epub / txt / md / image",
    )
    source_channel = Column(
        String(20),
        default="file",
        comment="来源渠道：file / image / cloud",
    )
    file_path = Column(
        String(500),
        nullable=False,
        comment="文件在文件系统中的路径",
    )
    file_size = Column(
        BigInteger,
        comment="文件大小（字节）",
    )

    status = Column(
        String(20),
        default="active",
        nullable=False,
        comment="状态：active / deleted / parsing / failed",
    )

    meta = Column(
        JSONB,
        default=dict,
        comment="扩展元信息",
    )

    created_at = Column(
        DateTime,
        default=datetime.now,
        comment="上传时间",
    )
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="最后修改时间",
    )

    def __repr__(self):
        return (
            f"<UserDocument(id={self.id}, "
            f"file_name={self.file_name!r}, "
            f"status={self.status!r})>"
        )


# ============================================================
# 2. user_notes 表（用户笔记）
# ============================================================
class UserNote(Base):
    """用户笔记"""
    __tablename__ = "user_notes"
    __table_args__ = (
        Index("idx_user_notes_user_id", "user_id"),
        Index("idx_user_notes_document_id", "document_id"),
        Index("idx_user_notes_note_type", "note_type"),
        Index("idx_user_notes_status", "status"),
        Index("idx_user_notes_created_at", "created_at"),
        {"comment": "用户笔记"},
    )

    id = Column(
        Integer,
        primary_key=True,
        comment="主键（PG 自增）",
    )
    note_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        comment="业务唯一ID（UUID，对外暴露）",
    )

    user_id = Column(
        Integer,
        nullable=False,
        default=1,
        comment="用户 ID",
    )
    document_id = Column(
        Integer,
        ForeignKey("user_documents.id"),
        nullable=False,
        comment="所属文档 ID",
    )

    note_type = Column(
        String(50),
        nullable=False,
        comment="笔记类型：translation / grammar / terminology / phrase",
    )
    content = Column(
        Text,
        nullable=False,
        comment="笔记内容（markdown 格式）",
    )
    content_size = Column(
        Integer,
        comment="内容大小（字节）",
    )

    is_integrated = Column(
        Boolean,
        default=False,
        comment="是否已被整合",
    )

    status = Column(
        String(20),
        default="active",
        nullable=False,
        comment="状态：active / deleted",
    )

    created_at = Column(
        DateTime,
        default=datetime.now,
        comment="创建时间",
    )
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="最后修改时间",
    )

    def __repr__(self):
        return (
            f"<UserNote(id={self.id}, "
            f"note_uuid={self.note_uuid[:8]}..., "
            f"note_type={self.note_type!r})>"
        )


# ============================================================
# 3. integration 表（整合笔记）
# ============================================================
class Integration(Base):
    """整合笔记"""
    __tablename__ = "integration"
    __table_args__ = (
        Index("idx_integration_user_id", "user_id"),
        Index("idx_integration_document_id", "document_id"),
        Index("idx_integration_status", "status"),
        Index("idx_integration_created_at", "created_at"),
        {"comment": "整合笔记"},
    )

    id = Column(
        Integer,
        primary_key=True,
        comment="主键（PG 自增）",
    )
    integration_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        comment="业务唯一ID（UUID，对外暴露）",
    )

    user_id = Column(
        Integer,
        nullable=False,
        default=1,
        comment="用户 ID",
    )
    document_id = Column(
        Integer,
        ForeignKey("user_documents.id"),
        nullable=False,
        comment="所属文档 ID",
    )

    source_modules = Column(
        JSONB,
        default=list,
        comment="被整合的模块列表，如 ['translation', 'grammar']",
    )
    source_note_ids = Column(
        JSONB,
        default=list,
        comment="被整合的笔记 UUID 列表",
    )

    content = Column(
        Text,
        nullable=False,
        comment="整合后的内容（markdown 格式）",
    )
    content_size = Column(
        Integer,
        comment="内容大小（字节）",
    )

    status = Column(
        String(20),
        default="active",
        nullable=False,
        comment="状态：active / deleted",
    )

    created_at = Column(
        DateTime,
        default=datetime.now,
        comment="创建时间",
    )
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="最后修改时间",
    )

    def __repr__(self):
        return (
            f"<Integration(id={self.id}, "
            f"integration_uuid={self.integration_uuid[:8]}..., "
            f"modules={self.source_modules})>"
        )


# ============================================================
# 4. recycle_bin 表（回收站）
# ============================================================
class RecycleBin(Base):
    """回收站"""
    __tablename__ = "recycle_bin"
    __table_args__ = (
        Index("idx_recycle_bin_user_id", "user_id"),
        Index("idx_recycle_bin_file_type_id", "file_type", "file_id"),
        Index("idx_recycle_bin_expires_at", "expires_at"),
        {"comment": "回收站（软删除的文档/笔记/整合）"},
    )

    id = Column(
        Integer,
        primary_key=True,
        comment="主键（PG 自增）",
    )

    user_id = Column(
        Integer,
        nullable=False,
        default=1,
        comment="用户 ID",
    )
    file_type = Column(
        String(20),
        nullable=False,
        comment="文件类型：user_document / user_note / integration",
    )
    file_id = Column(
        Integer,
        nullable=False,
        comment="关联的文件 ID",
    )

    deleted_at = Column(
        DateTime,
        default=datetime.now,
        nullable=False,
        comment="放入回收站的时间",
    )
    expires_at = Column(
        DateTime,
        nullable=False,
        comment="过期时间（默认 +15 天）",
    )

    created_at = Column(
        DateTime,
        default=datetime.now,
        comment="记录创建时间",
    )

    def __repr__(self):
        return (
            f"<RecycleBin(id={self.id}, "
            f"user_id={self.user_id}, "
            f"file_type={self.file_type!r}, "
            f"file_id={self.file_id})>"
        )

    @staticmethod
    def calc_expires_at(deleted_at: datetime = None) -> datetime:
        """计算过期时间（删除时间 + 保留天数）"""
        if deleted_at is None:
            deleted_at = datetime.now()
        return deleted_at + timedelta(days=RECYCLE_BIN_DAYS)

# ============================================================
# 5. user_vocabulary 表（生词本）
# ============================================================
class UserVocabulary(Base):
    """用户生词本"""
    __tablename__ = "user_vocabulary"
    __table_args__ = (
        Index("idx_user_vocabulary_user_id", "user_id"),
        Index("idx_user_vocabulary_word", "word"),
        Index("idx_user_vocabulary_created_at", "created_at"),
        Index(
            "idx_user_vocabulary_unique_active",
            "user_id", "word",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        {"comment": "用户生词本"},
    )

    id = Column(
        Integer,
        primary_key=True,
        comment="主键（PG 自增）",
    )
    vocab_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        comment="业务唯一ID（UUID，对外暴露）",
    )

    user_id = Column(
        Integer,
        nullable=False,
        default=1,
        comment="用户 ID",
    )
    word = Column(
        String(100),
        nullable=False,
        comment="单词拼写（小写归一化）",
    )
    word_info = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="单词详细信息（牛津词典词条结构 + source_context）",
    )

    status = Column(
        String(20),
        default="active",
        nullable=False,
        comment="状态：active / deleted",
    )

    created_at = Column(
        DateTime,
        default=datetime.now,
        comment="创建时间",
    )
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="最后修改时间",
    )

    def __repr__(self):
        return (
            f"<UserVocabulary(id={self.id}, "
            f"user_id={self.user_id}, "
            f"word={self.word!r}, "
            f"status={self.status!r})>"
        )