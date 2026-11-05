"""
orm_models.py - RAG 模块的 SQLAlchemy ORM 模型
路径: /home/bina/LaLe/RAG/orm_models.py

对应 PostgreSQL 表：
- documents     知识库文档
- chunks        切块内容
- index_meta    索引版本元信息
- chunk_stats   chunk 检索统计
- search_logs   检索日志
"""

from datetime import datetime
import uuid

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text,
    Boolean, DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

# 声明基类（database.py 会 import 它来 create_all）
Base = declarative_base()


# ============================================================
# 1. documents 表
# ============================================================
class Document(Base):
    """知识库文档（书籍、论文等）"""
    __tablename__ = "documents"   # 表名称
    # 表级参数：用来传递表级别的配置，比如索引、约束、注释
    # 创建表时会生成：CREATE INDEX idx_documents_category ON documents(category);
    __table_args__ = (
        Index("idx_documents_category", "category"),   # 索引类（索引名称，要索引的列名，unique=True(可选，表示唯一索引））
        Index("idx_documents_language", "language"),
        Index("idx_documents_file_hash", "file_hash"),
        {"comment": "知识库文档（书籍、论文等）"},    # 表注释，创建表时会生成：COMMENT ON TABLE documents IS '知识库文档（书籍、论文等）';
    )
    # 列定义：Column：定义一个列，Integer：整数类型，对应 PostgreSQL 的 INTEGER，primary_key=True：主键，comment="主键"：列注释
    # 生成的sql：id SERIAL PRIMARY KEY
    # SERIAL：是 PostgreSQL 的自增整数，SQLAlchemy 自动识别 Integer + primary_key 为自增
    id = Column(Integer, primary_key=True, comment="主键（自增）")
    # 普通列
    doc_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        comment="业务唯一ID（UUID）",
    )
    # String(500)：变长字符串，最大 500 字符（对应 VARCHAR(500)），nullable=False：非空约束（对应 NOT NULL），comment：列注释
    title = Column(String(500), nullable=False, comment="文档标题（书名）")
    author = Column(String(200), comment="作者")
    category = Column(String(50), comment="分类：翻译/语法/写作/短语等")
    language = Column(String(20), default="zh", comment="语言：zh/en/mixed")
    # String(64)：MD5/SHA256 哈希长度（MD5 是 32，SHA256 是 64），用于防止同一本书被重复导入
    file_hash = Column(String(64), comment="文件哈希，用于去重")
    meta = Column(JSONB, default=dict,
                  comment="扩展元信息（source_path、ISBN、出版社等）")
    # default=datetime.utcnow：默认值是当前 UTC 时间，传的是函数本身，SQLAlchemy 会在插入时调用它
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    # default=datetime.utcnow：插入时设为当前时间，onupdate=datetime.utcnow：每次更新时自动刷新为当前时间
    # 注：onupdate 只在使用 ORM 更新时生效（如 session.commit()），用原生 SQL UPDATE 不会触发
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                        comment="更新时间")
    # "Chunk"：关联的类名（字符串形式），用字符串是因为 Chunk 类可能在 Document 之后定义，SQLAlchemy 会延迟解析这个字符串
    # cascade="all, delete-orphan"：级联操作：
    # all：所有级联操作（save-update, merge, refresh-expire, expunge, delete）
    # delete-orphan：删除父对象时，删除所有子对象；从父对象的集合中移除子对象时，也删除该子对象
    # 实际效果：删除文档时，自动删除其所有 chunk：session.delete(doc)
    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan",
    )

    # __repr__：Python 的魔法方法，定义对象的官方字符串表示
    # 用 f-string 格式化。{self.title!r}：用 repr() 格式化，字符串会带引号
    # 效果：调试时更清晰：
    # >>> doc = Document(id=1, title="中式英语之鉴")
    # >>> print(doc)
    # <Document(id=1, title='中式英语之鉴')>
    # !r：调用 repr()，字符串会显示引号；!s：调用 str()，字符串不带引号（默认）；!a：调用 ascii()，非 ASCII 字符转义
    def __repr__(self):
        return f"<Document(id={self.id}, title={self.title!r}, doc_uuid={self.doc_uuid!r})>"


# ============================================================
# 2. chunks 表
# ============================================================
class Chunk(Base):
    """知识库切块内容"""
    __tablename__ = "chunks"
    __table_args__ = (
        Index("idx_chunks_document_id", "document_id"),
        Index("idx_chunks_chunk_type", "chunk_type"),
        Index("idx_chunks_topic", "topic"),
        Index("idx_chunks_content_hash", "content_hash"),
        {"comment": "知识库切块内容"},
    )

    id = Column(BigInteger, primary_key=True, comment="主键")
    chunk_uid = Column(String(64), unique=True, nullable=False,
                       comment="全局唯一ID，与 Qdrant 对应")
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, comment="所属文档ID",
    )
    content = Column(Text, nullable=False, comment="切块正文")
    content_hash = Column(String(64), comment="内容哈希，用于去重")
    chunk_type = Column(
        String(50),
        comment="内容形式：method/case/term/rule/example/definition",
    )
    topic = Column(
        String(100),
        comment="内容主题：翻译腔/文化适配/术语一致性等",
    )
    meta = Column(JSONB, default=dict,
                  comment="扩展元信息（chapter/section/page/token_count等）")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    document = relationship("Document", back_populates="chunks")
    stats = relationship(
        "ChunkStat", back_populates="chunk", cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Chunk(chunk_uid={self.chunk_uid!r}, type={self.chunk_type})>"


# ============================================================
# 3. index_meta 表
# ============================================================
class IndexMeta(Base):
    """索引版本元信息"""
    __tablename__ = "index_meta"
    __table_args__ = (
        Index("idx_index_meta_active", "is_active"),
        Index("idx_index_meta_version", "version"),
        {"comment": "索引版本元信息"},
    )

    id = Column(Integer, primary_key=True, comment="主键")
    version = Column(String(64), unique=True, nullable=False,
                     comment="索引版本号，如 20260917_001")
    embedding_model = Column(String(100), comment="使用的 embedding 模型")
    embedding_dim = Column(Integer, comment="向量维度")
    rerank_model = Column(String(100), comment="使用的 rerank 模型")
    qdrant_collection = Column(String(100),
                               comment="对应的 Qdrant collection 名称")
    total_documents = Column(Integer, default=0, comment="文档总数")
    total_chunks = Column(Integer, default=0, comment="切块总数")
    chunk_strategy = Column(String(100), comment="切块策略版本")
    is_active = Column(Boolean, default=False,
                       comment="是否为当前激活索引（同一时间只有一个为 true）")
    meta = Column(JSONB, default=dict, comment="扩展元信息")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    def __repr__(self):
        return f"<IndexMeta(version={self.version!r}, active={self.is_active})>"


# ============================================================
# 4. chunk_stats 表
# ============================================================
class ChunkStat(Base):
    """chunk 检索统计（按模块维度）"""
    __tablename__ = "chunk_stats"
    __table_args__ = (
        UniqueConstraint("chunk_uid", "module", name="uq_chunk_stats_uid_module"),
        Index("idx_chunk_stats_chunk", "chunk_uid"),
        Index("idx_chunk_stats_module", "module"),
        Index("idx_chunk_stats_times", "search_times"),
        {"comment": "chunk 检索统计（按模块维度）"},
    )

    id = Column(BigInteger, primary_key=True, comment="主键")
    chunk_uid = Column(
        String(64),
        ForeignKey("chunks.chunk_uid", ondelete="CASCADE"),
        nullable=False, comment="对应的 chunk UID",
    )
    module = Column(
        String(50), nullable=False,
        comment="调用的模块：翻译/语法/写作/短语",
    )
    search_times = Column(Integer, default=0,
                          comment="该模块检索该 chunk 的次数")
    last_searched = Column(DateTime, comment="最近一次检索时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                        comment="更新时间")

    chunk = relationship("Chunk", back_populates="stats")

    def __repr__(self):
        return (f"<ChunkStat(chunk_uid={self.chunk_uid!r}, "
                f"module={self.module!r}, times={self.search_times})>")


# ============================================================
# 5. search_logs 表
# ============================================================
class SearchLog(Base):
    """检索日志"""
    __tablename__ = "search_logs"
    __table_args__ = (
        Index("idx_search_logs_module", "module"),
        Index("idx_search_logs_created", "created_at"),
        Index("idx_search_logs_index_version", "index_version"),
        {"comment": "检索日志"},
    )

    id = Column(BigInteger, primary_key=True, comment="主键")
    query = Column(Text, nullable=False, comment="检索查询文本")
    module = Column(String(50), comment="调用的模块：翻译/语法/写作/短语")
    index_version = Column(String(64), comment="使用的索引版本")
    top_k = Column(Integer, comment="请求的 top_k")
    result_chunks = Column(
        JSONB,
        comment="检索结果列表，每项含 chunk_uid/document_id/document_title/score/rank",
    )
    latency_ms = Column(Integer, comment="检索耗时（毫秒）")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    def __repr__(self):
        return (f"<SearchLog(id={self.id}, module={self.module!r}, "
                f"query={self.query[:30]!r})>")