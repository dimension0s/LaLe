"""
build_index.py - 从 PG 读 chunk，算 embedding，写入 Qdrant

职责:
1. 从 PG 读 chunk（支持指定 document_id）
2. 计算 embedding
3. 写入 Qdrant
4. 支持增量更新
5. 支持换模型更换并重建索引

不负责:
- 删除文档索引（单独脚本）
- 创建 documents / chunks 记录
"""

from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from RAG.database import get_session
from RAG.orm_models import Chunk, Document, IndexMeta
from RAG.embedding import get_embedding_model
from RAG.qdrant_manager import get_qdrant_manager

from RAG.models_config import get_embedding_config

# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_BATCH_SIZE = 16


# ============================================================
# index_meta 操作
# ============================================================
def _get_active_index_meta() -> Optional[IndexMeta]:
    """获取当前激活的 index_meta"""
    with get_session() as session:
        return session.query(IndexMeta).filter_by(is_active=True).first()


def _deactivate_all_index_meta():
    """把所有 index_meta 设为非激活"""
    with get_session() as session:
        session.query(IndexMeta).update({"is_active": False})


def _create_index_meta(
    version: str,
    embedding_model: str,
    embedding_dim: int,
    qdrant_collection: str,
    total_documents: int,
    total_chunks: int,
    chunk_strategy: str = "fixed_length",
):
    """创建新的 index_meta 记录"""
    with get_session() as session:
        # 先全部设为非激活
        session.query(IndexMeta).update({"is_active": False})
        session.flush()

        # 创建新的
        meta = IndexMeta(
            version=version,
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
            qdrant_collection=qdrant_collection,
            total_documents=total_documents,
            total_chunks=total_chunks,
            chunk_strategy=chunk_strategy,
            is_active=True,
        )
        session.add(meta)
        logger.info(f"创建 index_meta: version={version}, model={embedding_model}")


# ============================================================
# Qdrant 操作
# ============================================================
def _get_indexed_chunk_uids() -> set:
    """
    从 Qdrant 获取已索引的 chunk_uid

    通过 scroll 遍历 collection，收集所有 chunk_uid
    """
    manager = get_qdrant_manager()

    indexed_uids = set()
    offset = None
    batch_count = 0

    while True:
        points, offset = manager.scroll(
            limit=1000,
            offset=offset,
            with_payload=True,
        )
        if not points:
            break

        for point in points:
            payload = point.payload or {}
            chunk_uid = payload.get("chunk_uid")
            if chunk_uid:
                indexed_uids.add(chunk_uid)

        batch_count += 1
        if batch_count % 10 == 0:
            logger.info(f"已扫描 {len(indexed_uids)} 个已索引 chunk")

        if offset is None:
            break

    logger.info(f"Qdrant 已有 {len(indexed_uids)} 个 chunk")
    return indexed_uids


# ============================================================
# 从 PG 读 chunk
# ============================================================
def _load_chunks_from_pg(document_id: Optional[int] = None) -> List[Dict]:
    """
    从 PG 读取 chunk

    Args:
        document_id: 指定文档（None 表示全部）

    Returns:
        [{"chunk_uid": ..., "document_id": ..., "content": ..., "title": ...}, ...]
    """
    with get_session() as session:
        query = session.query(Chunk, Document).join(
            Document, Chunk.document_id == Document.id
        )
        if document_id is not None:
            query = query.filter(Chunk.document_id == document_id)

        rows = query.all()

    chunks = []
    for chunk, doc in rows:
        chunks.append({
            "chunk_uid": chunk.chunk_uid,
            "document_id": chunk.document_id,
            "content": chunk.content,
            "title": doc.title,
            "category": doc.category,
            "language": doc.language,
        })

    logger.info(f"从 PG 读取 {len(chunks)} 个 chunk")
    return chunks


# ============================================================
# 核心流程
# ============================================================
def build_index(
    document_id: Optional[int] = None,
    batch_size: Optional[int] = None,
    recreate: bool = False,
) -> Dict:
    """
    构建/更新索引

    Args:
        document_id: 指定文档（None 表示全部）
        batch_size: embedding 批大小（None 表示用配置值）
        recreate: 是否强制重建

    Returns:
        {
            "mode": "rebuild" 或 "incremental",
            "total": ...,
            "indexed": ...,
            "skipped": ...,
        }
    """
    # ============================================================
    # ✅ 从配置读模型信息
    # ============================================================
    emb_config = get_embedding_config()
    embedding_model = emb_config.model_id
    embedding_dim = emb_config.embedding_dim

    if batch_size is None:
        batch_size = emb_config.batch_size

    logger.info("=" * 60)
    logger.info("构建索引")
    logger.info("=" * 60)
    logger.info(f"embedding_model: {embedding_model}")
    logger.info(f"embedding_dim: {embedding_dim}")
    logger.info(f"document_id: {document_id or '全部'}")
    logger.info(f"batch_size: {batch_size}")
    logger.info(f"recreate: {recreate}")

    manager = get_qdrant_manager()

    # 1. 检查 Qdrant collection 是否存在
    collection_exists = manager.collection_exists()
    logger.info(f"Qdrant collection 存在: {collection_exists}")

    # 2. 读当前 index_meta
    active_meta = _get_active_index_meta()

    # 3. 判断是"重建"还是"增量"
    rebuild = recreate or not collection_exists

    if not rebuild and active_meta:
        if active_meta.embedding_model != embedding_model:
            logger.warning(
                f"embedding 模型变了: "
                f"{active_meta.embedding_model} → {embedding_model}，将重建索引"
            )
            rebuild = True
        else:
            logger.info(f"模型未变 ({embedding_model})，进入增量模式")
    elif not active_meta:
        logger.info("没有激活的 index_meta，进入重建模式")
        rebuild = True

    # 4. 重建流程
    if rebuild:
        logger.info("🔨 重建索引")
        if collection_exists:
            manager.delete_collection()
            logger.info("已删除旧 collection")
        manager.create_collection()
        logger.info("已创建新 collection")
        mode = "rebuild"
        indexed_uids = set()
    else:
        logger.info("♻️  增量更新")
        mode = "incremental"
        indexed_uids = _get_indexed_chunk_uids()

    # 5. 从 PG 读 chunk
    chunks = _load_chunks_from_pg(document_id=document_id)
    if not chunks:
        logger.warning("没有可索引的 chunk")
        return {
            "mode": mode,
            "total": 0,
            "indexed": 0,
            "skipped": 0,
        }

    # 6. 增量过滤
    if mode == "incremental" and indexed_uids:
        to_index = [
            c for c in chunks
            if c["chunk_uid"] not in indexed_uids
        ]
        skipped = len(chunks) - len(to_index)
        logger.info(f"增量更新: {len(to_index)} 个待索引, {skipped} 个已存在")
    else:
        to_index = chunks
        skipped = 0

    if not to_index:
        logger.info("所有 chunk 已索引，无需更新")
        return {
            "mode": mode,
            "total": len(chunks),
            "indexed": 0,
            "skipped": skipped,
        }

    # 7. 批量计算 embedding
    logger.info(f"开始计算 embedding: {len(to_index)} 条")
    embedding = get_embedding_model()

    texts = [c["content"] for c in to_index]
    vectors = embedding.encode_batch(texts, batch_size=batch_size)

    # 8. 组装 Qdrant points
    points = []
    for chunk, vector in zip(to_index, vectors):
        if vector is None:
            logger.debug(f"跳过空向量: {chunk['chunk_uid']}")
            continue
        points.append({
            "id": chunk["chunk_uid"],
            "vector": vector,
            "payload": {
                "chunk_uid": chunk["chunk_uid"],
                "document_id": chunk["document_id"],
                "title": chunk.get("title", ""),
                "category": chunk.get("category", ""),
                "language": chunk.get("language", ""),
            },
        })

    # 9. 批量写入 Qdrant
    logger.info(f"开始写入 Qdrant: {len(points)} 条")
    manager.upsert(points, batch_size=100)

    # 10. 更新 index_meta
    if mode == "rebuild":
        # 重建：创建新的 index_meta
        from datetime import datetime
        version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        _create_index_meta(
            version=version,
            embedding_model=embedding_model,        # ✅ 来自配置
            embedding_dim=embedding_dim,            # ✅ 来自配置
            qdrant_collection=manager.coll_config.collection_name,
            total_documents=len(set(c["document_id"] for c in chunks)),
            total_chunks=len(points),
            chunk_strategy="fixed_length",
        )
    else:
        # 增量：更新 total_chunks
        # 查询Qdrant 的 points_count，即当前的实际数量
        info = manager.get_collection_info()
        actual_count = info.get("points_count", 0)

        with get_session() as session:
            meta = session.query(IndexMeta).filter_by(is_active=True).first()
            if meta:
                meta.total_chunks = actual_count

    stats = {
        "mode": mode,
        "total": len(chunks),
        "indexed": len(points),
        "skipped": skipped,
    }

    logger.info("=" * 60)
    logger.info(f"✅ 索引完成")
    logger.info(f"模式: {mode}")
    logger.info(f"总数: {stats['total']}")
    logger.info(f"已索引: {stats['indexed']}")
    logger.info(f"跳过: {stats['skipped']}")
    logger.info("=" * 60)

    return stats


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 在这里修改参数
    # ================================================
    DOCUMENT_ID = None     # None 表示全部；或指定 document_id
    BATCH_SIZE = None      # None 表示用配置值（emb_config.batch_size）
    RECREATE = False       # True 表示强制重建
    # ================================================

    cfg = get_embedding_config()

    print("=" * 60)
    print("构建索引")
    print("=" * 60)
    print(f"embedding_model: {cfg.model_id}")
    print(f"embedding_dim: {cfg.embedding_dim}")
    print(f"document_id: {DOCUMENT_ID or '全部'}")
    print(f"batch_size: {BATCH_SIZE or cfg.batch_size}（配置默认）")
    print(f"recreate: {RECREATE}")
    print("=" * 60)

    stats = build_index(
        document_id=DOCUMENT_ID,
        batch_size=BATCH_SIZE,
        recreate=RECREATE,
    )

    print("\n" + "=" * 60)
    print("✅ 完成")
    print("=" * 60)
    print(f"  模式: {stats['mode']}")
    print(f"  总数: {stats['total']}")
    print(f"  已索引: {stats['indexed']}")
    print(f"  跳过: {stats['skipped']}")
