"""
vector_search.py - 向量检索（基于 Qdrant）
路径: /home/bina/LaLe/RAG/search/vector_search.py

职责:
1. 计算 query 的 embedding
2. 在 Qdrant 中做向量相似度检索
3. 支持 document_id / category 过滤
4. 返回 (chunk_uid, score) 列表

过滤说明:
- document_id: 精确到某本书（备用，默认 None）
- category: 按知识类别过滤（主流程，如 "翻译"/"语法"/"写作"）

不负责:
- BM25 检索（由 bm25_search.py 负责）
- RRF 融合（由 rrf.py 负责）
- 重排序（由 search.py 负责）
"""

from typing import List, Tuple, Optional

from loguru import logger
from qdrant_client.http import models as qmodels

from RAG.embedding import get_embedding_model
from RAG.qdrant_manager import get_qdrant_manager


# ============================================================
# 配置
# ============================================================
DEFAULT_TOP_K = 60


# ============================================================
# 核心函数
# ============================================================
def vector_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    document_id: Optional[int] = None,
    category: Optional[str] = None,
) -> List[Tuple[str, float]]:
    """
    向量检索

    Args:
        query: 查询文本
        top_k: 返回条数
        document_id: 按文档 ID 过滤（可选，默认不过滤）
        category: 按知识类别过滤（推荐，如 "翻译"/"语法"/"写作"）

    Returns:
        [(chunk_uid, score), ...]，按 score 降序
    """
    # 1. 空查询检查
    if not query or not query.strip():
        logger.warning("query 为空，返回空结果")
        return []

    query = query.strip()

    # 2. 计算 query embedding
    try:
        model = get_embedding_model()
        query_vector = model.encode(query)
    except Exception as e:
        logger.error(f"计算 query embedding 失败: {e}")
        raise

    # 3. 构造 Qdrant 过滤条件
    query_filter = _build_qdrant_filter(
        document_id=document_id,
        category=category,
    )

    # 4. Qdrant 检索
    try:
        manager = get_qdrant_manager()
        hits = manager.search(
            query_vector=query_vector,
            top_k=top_k,
            query_filter=query_filter,
        )
    except Exception as e:
        logger.error(f"Qdrant 检索失败: {e}")
        raise

    # 5. 转换格式
    results = [(h.chunk_uid, h.score) for h in hits]

    logger.info(
        f"向量检索: query={query!r}, "
        f"过滤=(document_id={document_id}, category={category}), "
        f"返回 {len(results)} 条"
    )
    if results:
        logger.debug(f"向量 top-3: {[(h[0][:8], round(h[1], 4)) for h in results[:3]]}")

    return results


# ============================================================
# 辅助函数
# ============================================================
def _build_qdrant_filter(
    document_id: Optional[int] = None,
    category: Optional[str] = None,
) -> Optional[qmodels.Filter]:
    """
    构造 Qdrant 过滤条件

    Args:
        document_id: 按文档 ID 过滤
        category: 按知识类别过滤

    Returns:
        qmodels.Filter 或 None（无过滤）
    """
    must_conditions = []

    if document_id is not None:
        must_conditions.append(
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchValue(value=document_id),
            )
        )

    if category:
        must_conditions.append(
            qmodels.FieldCondition(
                key="category",
                match=qmodels.MatchValue(value=category),
            )
        )

    if not must_conditions:
        return None

    return qmodels.Filter(must=must_conditions)


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 在这里修改参数
    # ================================================
    QUERY = "翻译腔怎么避免"
    TOP_K = 10
    DOCUMENT_ID = None      # None: 不过滤具体文档
    CATEGORY = "翻译"       # 主过滤：按知识类别
    # ================================================

    print("=" * 60)
    print("向量检索测试")
    print("=" * 60)
    print(f"Query: {QUERY}")
    print(f"top_k: {TOP_K}")
    print(f"document_id: {DOCUMENT_ID}")
    print(f"category: {CATEGORY}")
    print("=" * 60)

    hits = vector_search(
        query=QUERY,
        top_k=TOP_K,
        document_id=DOCUMENT_ID,
        category=CATEGORY,
    )

    print("\n" + "=" * 60)
    print(f"✅ 检索完成: {len(hits)} 条")
    print("=" * 60)

    for i, (chunk_uid, score) in enumerate(hits, 1):
        print(f" [{i}] score={score:.6f}  chunk_uid={chunk_uid}")