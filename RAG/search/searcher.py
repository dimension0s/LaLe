"""
search.py - 混合检索 + RRF 融合 + Reranker 重排

rrf_score分数标准：0~0.05，不看分数看相关，排名越高相关性越高，用于调试，在测试中无需排序
rerank_score分数标准：-10~10，大于0为正相关，越大越相关，在测试中降序排列

"""

from dataclasses import dataclass
from typing import List, Optional, Dict

from loguru import logger

from RAG.database import get_session
from RAG.orm_models import Chunk, Document
from RAG.search.bm25_search import bm25_search
from RAG.search.vector_search import vector_search
from RAG.search.rrf import reciprocal_rank_fusion
from RAG.search.reranker import get_reranker


# ============================================================
# 配置
# ============================================================
DEFAULT_TOP_K_RECALL = 60
DEFAULT_TOP_K_FUSION = 20
DEFAULT_TOP_K_FINAL = 5


# ============================================================
# 返回结构
# ============================================================
@dataclass
class SearchResult:
    """检索结果"""
    chunk_uid: str
    content: str
    rerank_score: float       # Reranker 分数（判断相关性，>0 相关）
    rrf_score: float          # RRF 分数（调试用）
    document_id: int
    title: str
    category: str

    def to_dict(self) -> Dict:
        return {
            "chunk_uid": self.chunk_uid,
            "content": self.content,
            "rerank_score": self.rerank_score,
            "rrf_score": self.rrf_score,
            "document_id": self.document_id,
            "title": self.title,
            "category": self.category,
        }


# ============================================================
# 核心函数
# ============================================================
def search(
    query: str,
    top_k_recall: int = DEFAULT_TOP_K_RECALL,
    top_k_fusion: int = DEFAULT_TOP_K_FUSION,
    top_k_final: int = DEFAULT_TOP_K_FINAL,
    use_rerank: bool = True,
    document_id: Optional[int] = None,
    category: Optional[str] = None,
) -> List[SearchResult]:
    """
    混合检索 + RRF 融合 + Reranker 重排

    Args:
        query: 查询文本
        top_k_recall: 每路召回数量（默认 60）
        top_k_fusion: RRF 融合后数量（默认 20）
        top_k_final: 最终返回数量（默认 5）
        use_rerank: 是否用 reranker（默认 True）
        document_id: 按文档 ID 过滤（可选）
        category: 按分类过滤（可选）

    Returns:
        List[SearchResult]
    """
    # 1. 空查询检查
    if not query or not query.strip():
        logger.warning("query 为空，返回空结果")
        return []

    query = query.strip()
    logger.info("=" * 60)
    logger.info(f"检索: query={query!r}")
    logger.info(
        f"参数: top_k_recall={top_k_recall}, "
        f"top_k_fusion={top_k_fusion}, "
        f"top_k_final={top_k_final}, "
        f"use_rerank={use_rerank}"
    )
    logger.info(f"过滤: document_id={document_id}, category={category}")
    logger.info("=" * 60)

    # 2. 两路检索
    logger.info("[1/5] 两路检索...")
    vector_hits = vector_search(
        query=query,
        top_k=top_k_recall,
        document_id=document_id,
        category=category,
    )
    bm25_hits = bm25_search(
        query=query,
        top_k=top_k_recall,
        document_id=document_id,
        category=category,
    )

    if not vector_hits and not bm25_hits:
        logger.warning("两路检索都没有结果，返回空")
        return []

    logger.info(f"  向量召回: {len(vector_hits)} 条")
    logger.info(f"  BM25 召回: {len(bm25_hits)} 条")

    # 3. RRF 融合
    logger.info("[2/5] RRF 融合...")
    fused = reciprocal_rank_fusion(
        result_lists=[vector_hits, bm25_hits],
        k=60,
    )
    fused = fused[:top_k_fusion]
    logger.info(f"  融合后: {len(fused)} 条（取 top-{top_k_fusion}）")

    if not fused:
        logger.warning("RRF 融合后无结果，返回空")
        return []

    # 4. 从 PG 取完整文本
    logger.info("[3/5] 从 PG 取文本...")
    chunk_uids = [uid for uid, _ in fused]
    rrf_score_map = {uid: score for uid, score in fused}

    with get_session() as session:
        rows = session.query(Chunk, Document).join(
            Document, Chunk.document_id == Document.id
        ).filter(Chunk.chunk_uid.in_(chunk_uids)).all()

    chunk_map = {chunk.chunk_uid: (chunk, doc) for chunk, doc in rows}
    logger.info(f"  从 PG 取到 {len(chunk_map)} 条")

    if not chunk_map:
        logger.warning("PG 中没有对应的 chunk，返回空")
        return []

    # 5. Reranker 重排
    logger.info("[4/5] Reranker 重排...")

    # 按 RRF 顺序构造文档列表
    ordered_uids = [uid for uid, _ in fused if uid in chunk_map]
    documents = [chunk_map[uid][0].content for uid in ordered_uids]

    if use_rerank:
        try:
            reranker = get_reranker()
            rerank_results = reranker.rerank(
                query=query,
                documents=documents,
                top_k=top_k_final,
            )

            # 按 rerank 结果构造最终结果
            results = []
            for r in rerank_results:
                chunk_uid = ordered_uids[r.index]
                chunk, doc = chunk_map[chunk_uid]
                results.append(SearchResult(
                    chunk_uid=chunk_uid,
                    content=chunk.content,
                    rerank_score=float(r.score),       # ← Reranker 分数
                    rrf_score=rrf_score_map.get(chunk_uid, 0.0),
                    document_id=chunk.document_id,
                    title=doc.title,
                    category=doc.category or "",
                ))
        except Exception as e:
            logger.error(f"Reranker 失败: {e}，回退到 RRF 排序")
            use_rerank = False
            results = []

    if not use_rerank:
        # 不用 reranker，用 RRF 顺序
        # rerank_score 设为 0（表示未重排）
        results = []
        for chunk_uid in ordered_uids[:top_k_final]:
            chunk, doc = chunk_map[chunk_uid]
            results.append(SearchResult(
                chunk_uid=chunk_uid,
                content=chunk.content,
                rerank_score=0.0,                       # 无 reranker
                rrf_score=rrf_score_map.get(chunk_uid, 0.0),
                document_id=chunk.document_id,
                title=doc.title,
                category=doc.category or "",
            ))

    # 6. 返回结果
    logger.info("[5/5] 检索完成")
    logger.info(f"  最终返回: {len(results)} 条")
    if results:
        logger.debug(
            f"  top-3: "
            f"{[(r.chunk_uid[:8], round(r.rerank_score, 4)) for r in results[:3]]}"
        )

    return results


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 在这里修改参数
    # ================================================
    QUERY = "如何做好汉英翻译"
    TOP_K_RECALL = 60
    TOP_K_FUSION = 20
    TOP_K_FINAL = 5
    USE_RERANK = True
    DOCUMENT_ID = None
    CATEGORY = "翻译"
    # ================================================

    print("=" * 60)
    print("混合检索测试")
    print("=" * 60)
    print(f"Query: {QUERY}")
    print(f"top_k_recall: {TOP_K_RECALL}")
    print(f"top_k_fusion: {TOP_K_FUSION}")
    print(f"top_k_final: {TOP_K_FINAL}")
    print(f"use_rerank: {USE_RERANK}")
    print(f"document_id: {DOCUMENT_ID}")
    print(f"category: {CATEGORY}")
    print("=" * 60)

    results = search(
        query=QUERY,
        top_k_recall=TOP_K_RECALL,
        top_k_fusion=TOP_K_FUSION,
        top_k_final=TOP_K_FINAL,
        use_rerank=USE_RERANK,
        document_id=DOCUMENT_ID,
        category=CATEGORY,
    )

    print("\n" + "=" * 60)
    print(f"✅ 检索完成: {len(results)} 条")
    print("=" * 60)

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] rerank_score={r.rerank_score:.4f}  rrf_score={r.rrf_score:.6f}")
        print(f" chunk_uid: {r.chunk_uid}")
        print(f" document_id: {r.document_id}")
        print(f" title: {r.title}")
        print(f" category: {r.category}")
        print(f" content: {r.content[:150]}...")