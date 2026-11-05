"""
rrf.py - Reciprocal Rank Fusion（RRF）融合算法
路径: /home/bina/LaLe/RAG/search/rrf.py

职责:
1. 把多路检索结果融合成一路
2. 只使用排名，不使用原始分数
3. 纯函数，无外部依赖

公式:
    rrf_score(d) = Σ 1 / (k + rank_i(d))

    其中：
        rank_i(d) = 文档 d 在第 i 路检索中的排名（从 1 开始）
        k = 平滑参数（默认 60）
"""

from collections import defaultdict
from typing import List, Tuple, Dict

from loguru import logger


# ============================================================
# 配置
# ============================================================
DEFAULT_K = 60


# ============================================================
# 核心算法
# ============================================================
def reciprocal_rank_fusion(
    result_lists: List[List[Tuple[str, float]]],
    k: int = DEFAULT_K,
) -> List[Tuple[str, float]]:
    """
    RRF 融合

    Args:
        result_lists: 多路检索结果，每路是 [(chunk_uid, score), ...]
                      score 会被忽略，只用 chunk_uid 的排名
        k: RRF 平滑参数（默认 60）

    Returns:
        [(chunk_uid, rrf_score), ...]，按 rrf_score 降序
    """
    # 1. 空输入检查
    if not result_lists:
        logger.warning("result_lists 为空，返回空结果")
        return []

    # 2. 累加 RRF 分数
    rrf_scores: Dict[str, float] = defaultdict(float)

    for list_idx, result_list in enumerate(result_lists, start=1):
        if not result_list:
            logger.debug(f"第 {list_idx} 路检索结果为空，跳过")
            continue

        for rank, item in enumerate(result_list, start=1):
            chunk_uid = item[0]   # 只用 chunk_uid，忽略 score
            rrf_scores[chunk_uid] += 1.0 / (k + rank)

    # 3. 按 RRF 分数降序排序
    sorted_results = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    logger.info(
        f"RRF 融合: {len(result_lists)} 路输入, "
        f"共 {len(sorted_results)} 个唯一 chunk, "
        f"k={k}"
    )
    if sorted_results:
        logger.debug(
            f"RRF top-3: "
            f"{[(uid[:8], round(score, 6)) for uid, score in sorted_results[:3]]}"
        )

    return sorted_results


# ============================================================
# 命令行入口：测试
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("RRF 融合测试")
    print("=" * 60)

    # 模拟两路检索结果
    # 向量检索（top-5）
    vector_results = [
        ("chunk_A", 0.95),
        ("chunk_B", 0.90),
        ("chunk_C", 0.85),
        ("chunk_D", 0.80),
        ("chunk_E", 0.75),
    ]

    # BM25 检索（top-5）
    bm25_results = [
        ("chunk_C", 0.050),
        ("chunk_A", 0.045),
        ("chunk_F", 0.040),
        ("chunk_G", 0.035),
        ("chunk_B", 0.030),
    ]

    print("\n[1] 向量检索结果:")
    for rank, (uid, score) in enumerate(vector_results, 1):
        print(f" [{rank}] {uid}  score={score:.4f}")

    print("\n[2] BM25 检索结果:")
    for rank, (uid, score) in enumerate(bm25_results, 1):
        print(f" [{rank}] {uid}  score={score:.4f}")

    # RRF 融合
    print("\n[3] RRF 融合（k=60）:")
    fused = reciprocal_rank_fusion(
        result_lists=[vector_results, bm25_results],
        k=60,
    )

    print(f"\n 融合后共 {len(fused)} 个唯一 chunk:")
    for rank, (uid, rrf_score) in enumerate(fused, 1):
        print(f" [{rank}] {uid}  rrf_score={rrf_score:.6f}")

    # 手动验证 RRF 分数
    print("\n[4] 手动验证 RRF 分数（前 3 名）:")
    print(" 公式: rrf_score = Σ 1 / (k + rank)")

    # chunk_A: 向量 rank=1, BM25 rank=2
    chunk_a_score = 1/(60+1) + 1/(60+2)
    print(f" chunk_A: 1/(60+1) + 1/(60+2) = {chunk_a_score:.6f}")

    # chunk_C: 向量 rank=3, BM25 rank=1
    chunk_c_score = 1/(60+3) + 1/(60+1)
    print(f" chunk_C: 1/(60+3) + 1/(60+1) = {chunk_c_score:.6f}")

    # chunk_B: 向量 rank=2, BM25 rank=5
    chunk_b_score = 1/(60+2) + 1/(60+5)
    print(f" chunk_B: 1/(60+2) + 1/(60+5) = {chunk_b_score:.6f}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)