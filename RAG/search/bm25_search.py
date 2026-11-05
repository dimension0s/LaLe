"""
bm25_search.py - BM25 关键词检索（基于 PG 全文索引）
路径: /home/bina/LaLe/RAG/search/bm25_search.py

职责:
1. 用 PG 的 jiebacfg 全文索引做 BM25-like 检索
2. 用 Python jieba 分词 + OR 连接，构造 tsquery
3. 支持 document_id / category 过滤
4. 返回 (chunk_uid, score) 列表
"""

from typing import List, Tuple, Optional

import jieba
from loguru import logger
from sqlalchemy import text

from RAG.database import get_session


# ============================================================
# 配置
# ============================================================
DEFAULT_TOP_K = 60
DEFAULT_TS_CONFIG = "jiebacfg"   # 使用 pg_jieba 的中文分词


# ============================================================
# 核心函数
# ============================================================
def bm25_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    document_id: Optional[int] = None,
    category: Optional[str] = None,
    ts_config: str = DEFAULT_TS_CONFIG,
) -> List[Tuple[str, float]]:
    """
    BM25-like 关键词检索

    Args:
        query: 查询文本
        top_k: 返回条数
        document_id: 按文档 ID 过滤
        category: 按分类过滤（JOIN documents 表）
        ts_config: PostgreSQL 全文检索配置（默认 jiebacfg）

    Returns:
        [(chunk_uid, score), ...]，按 score 降序
    """
    # 1. 空查询检查
    if not query or not query.strip():
        logger.warning("query 为空，返回空结果")
        return []

    query = query.strip()

    # 2. 构造 tsquery（jieba 分词 + OR 连接）
    ts_query_str = _build_ts_query(query)
    if not ts_query_str:
        logger.warning(f"查询无法构造 tsquery: {query!r}")
        return []

    # 3. 构造 SQL
    sql_parts = ["""
        SELECT
            c.chunk_uid,
            ts_rank(
                to_tsvector(:ts_config, c.content),
                to_tsquery(:ts_config, :ts_query)
            ) AS score
        FROM chunks c
    """]

    if category:
        sql_parts.append("JOIN documents d ON c.document_id = d.id")

    where_conditions = [
        "to_tsvector(:ts_config, c.content) @@ to_tsquery(:ts_config, :ts_query)"
    ]

    params = {
        "ts_config": ts_config,
        "ts_query": ts_query_str,
        "top_k": top_k,
    }

    if document_id is not None:
        where_conditions.append("c.document_id = :document_id")
        params["document_id"] = document_id

    if category:
        where_conditions.append("d.category = :category")
        params["category"] = category

    sql_parts.append("WHERE " + " AND ".join(where_conditions))
    sql_parts.append("ORDER BY score DESC")
    sql_parts.append("LIMIT :top_k")

    sql = "\n".join(sql_parts)

    # 4. 执行查询
    try:
        with get_session() as session:
            result = session.execute(text(sql), params)
            rows = result.fetchall()

        hits = [(row[0], float(row[1])) for row in rows]

        logger.info(
            f"BM25 检索: query={query!r}, "
            f"ts_query={ts_query_str!r}, "
            f"过滤=(document_id={document_id}, category={category}), "
            f"返回 {len(hits)} 条"
        )
        if hits:
            logger.debug(f"BM25 top-3: {[(h[0][:8], round(h[1], 4)) for h in hits[:3]]}")

        return hits

    except Exception as e:
        logger.error(f"BM25 检索失败: {e}")
        raise


# ============================================================
# 辅助函数
# ============================================================
def _build_ts_query(query: str) -> str:
    """
    用 jieba 分词 + OR 连接，构造 tsquery

    例：
        "翻译腔怎么避免" → "翻译 | 腔 | 怎么 | 避免"

    注意：
        - PG 的 to_tsquery 需要特殊格式（& | <-> 等）
        - 直接传中文串会被识别为短语，导致 0 匹配
        - 所以用 jieba 分词，再 OR 连接
    """
    tokens = jieba.lcut(query)
    # 去掉空白
    tokens = [t.strip() for t in tokens if t.strip()]
    if not tokens:
        return ""
    return " | ".join(tokens)


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 在这里修改参数
    # ================================================
    QUERY = "翻译腔怎么避免"
    TOP_K = 10
    DOCUMENT_ID = None      # None 表示不过滤
    CATEGORY = None         # None 表示不过滤
    # ================================================

    print("=" * 60)
    print("BM25 检索测试")
    print("=" * 60)
    print(f"Query: {QUERY}")
    print(f"top_k: {TOP_K}")
    print(f"document_id: {DOCUMENT_ID}")
    print(f"category: {CATEGORY}")
    print("=" * 60)

    hits = bm25_search(
        query=QUERY,
        top_k=TOP_K,
        document_id=DOCUMENT_ID,
        category=CATEGORY,
    )

    print("\n" + "=" * 60)
    print(f"✅ 检索完成: {len(hits)} 条")
    print("=" * 60)

    for i, (chunk_uid, score) in enumerate(hits, 1):
        print(f"[{i}] score={score:.6f}  chunk_uid={chunk_uid}")