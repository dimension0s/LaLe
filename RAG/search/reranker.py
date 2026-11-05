"""
reranker.py - 重排序（基于 bge-reranker-v2-m3）
路径: /home/bina/LaLe/RAG/reranker.py

职责:
1. 加载 bge-reranker-v2-m3 模型（单例）
2. 对候选文档重新排序（query-document 打分）
3. 提供便捷函数给上层调用

不负责:
- 向量检索（由 qdrant_manager.py 负责）
- 文本向量化（由 embedding.py 负责）
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import numpy as np
from loguru import logger

from RAG.models_config import (
    RerankerConfig,
    get_reranker_config,
)


# ============================================================
# 返回结构
# ============================================================
@dataclass
class RerankResult:
    """单条重排序结果"""
    index: int          # 在原始列表中的索引
    score: float        # 相关性分数
    document: str       # 文档内容
    metadata: Dict[str, Any]  # 附加信息（可选）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "score": self.score,
            "document": self.document,
            "metadata": self.metadata,
        }


# ============================================================
# Reranker 模型封装
# ============================================================
class RerankerModel:
    """bge-reranker-v2-m3 模型封装（单例）"""

    _instance: Optional["RerankerModel"] = None

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[RerankerConfig] = None):
        if getattr(self, "_initialized", False):
            return

        self.config = config or get_reranker_config()
        self.model = None

        self._load_model()
        self._initialized = True

    # ========================================================
    # 模型加载
    # ========================================================
    def _load_model(self):
        """加载 bge-reranker-v2-m3 模型"""
        model_path = self.config.model_name
        logger.info(f"正在从本地加载 reranker 模型: {model_path}")

        # FlagEmbedding 提供 FlagReranker
        from FlagEmbedding import FlagReranker
        self.model = FlagReranker(
            model_path,
            use_fp16=(self.config.device == "cuda"),
            device=self.config.device,
        )
        logger.info(f"✅ Reranker 模型加载完成: {model_path}")


    # ========================================================
    # 打分（核心）
    # ========================================================
    def score(
        self,
        query: str,
        documents: List[str],
        normalize: bool = False,
    ) -> List[float]:
        """
        给 query 与每个 document 打分

        Args:
            query: 查询文本
            documents: 候选文档列表
            normalize: 是否归一化到 [0, 1]

        Returns:
            List[float]，长度等于 len(documents)
        """
        if not query or not query.strip():
            raise ValueError("query 不能为空")
        if not documents:
            return []

        # 构造 (query, doc) 对
        pairs = [[query.strip(), doc.strip()] for doc in documents]

        scores = self.model.compute_score(
            pairs,
            normalize=normalize,
            max_length=self.config.max_length,
            batch_size=self.config.batch_size,
        )


        # 确保返回 List[float]
        if isinstance(scores, (float, int)):
            scores = [float(scores)]
        elif isinstance(scores, np.ndarray):
            scores = scores.tolist()
        else:
            scores = [float(s) for s in scores]

        return scores


    # ========================================================
    # 重排序（核心）
    # ========================================================
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        normalize: bool = False,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> List[RerankResult]:
        """
        对候选文档重排序

        Args:
            query: 查询文本
            documents: 候选文档列表
            top_k: 返回前 k 条，None 则返回全部
            normalize: 是否归一化分数
            metadata: 每条文档的附加信息（可选），长度必须等于 len(documents)

        Returns:
            List[RerankResult]，按 score 降序排列
        """
        if not documents:
            return []

        if metadata is not None and len(metadata) != len(documents):
            raise ValueError(
                f"metadata 长度 {len(metadata)} 与 documents 长度 {len(documents)} 不一致"
            )

        # 打分
        scores = self.score(query, documents, normalize=normalize)

        # 组装结果
        results = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            results.append(RerankResult(
                index=i,
                score=float(score),
                document=doc,
                metadata=metadata[i] if metadata else {},
            ))

        # 按分数降序排序
        results.sort(key=lambda x: x.score, reverse=True)

        # 截取 top_k
        if top_k is not None and top_k > 0:
            results = results[:top_k]

        return results

    # ========================================================
    # 批量重排序（多 query）
    # ========================================================
    def rerank_batch(
        self,
        queries: List[str],
        documents_list: List[List[str]],
        top_k: Optional[int] = None,
        normalize: bool = False,
    ) -> List[List[RerankResult]]:
        """
        批量重排序（每个 query 对应一组 documents）

        Args:
            queries: query 列表
            documents_list: 每个 query 对应的候选文档列表
            top_k: 每个 query 返回前 k 条
            normalize: 是否归一化分数

        Returns:
            List[List[RerankResult]]
        """
        if len(queries) != len(documents_list):
            raise ValueError(
                f"queries 长度 {len(queries)} 与 documents_list 长度 {len(documents_list)} 不一致"
            )

        results = []
        for query, documents in zip(queries, documents_list):
            results.append(
                self.rerank(query, documents, top_k=top_k, normalize=normalize)
            )
        return results

    # ========================================================
    # 属性
    # ========================================================
    # @property
    # def backend(self) -> str:
    #     return self._backend


# ============================================================
# 便捷函数
# ============================================================
def get_reranker() -> RerankerModel:
    """获取全局 Reranker 实例"""
    return RerankerModel()


def rerank(
    query: str,
    documents: List[str],
    top_k: Optional[int] = None,
    normalize: bool = False,
    metadata: Optional[List[Dict[str, Any]]] = None,
) -> List[RerankResult]:
    """快速重排序"""
    return get_reranker().rerank(
        query, documents, top_k=top_k, normalize=normalize, metadata=metadata,
    )


# ============================================================
# 命令行入口：测试
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Reranker 模型测试")
    print("=" * 60)

    # 1. 加载模型
    print("\n[1] 加载模型...")
    model = get_reranker()
    print(f"✅ 模型: {model.config.model_name}")
    print(f" 设备: {model.config.device}")

    # 2. 单组打分
    print("\n[2] 打分测试...")
    query = "翻译腔怎么避免"
    documents = [
        "翻译时避免'进行……的处理'这类翻译腔",
        "black sheep 应译为'害群之马'",
        "Federal Reserve 应统一译为'美联储'",
        "被动语态在中英翻译中的处理",
    ]
    scores = model.score(query, documents)
    print(f" Query: {query}")
    for i, (doc, score) in enumerate(zip(documents, scores)):
        print(f" [{i}] {score:.2f}  {doc}")

    # 3. 重排序
    print("\n[3] 重排序测试...")
    results = model.rerank(query, documents)
    print(f" Query: {query}")
    for rank, r in enumerate(results, 1):
        print(f" {rank}. [{r.score:.2f}] (原索引 {r.index}) {r.document}")

    # 4. top_k 截取
    print("\n[4] Top-2 测试...")
    results = model.rerank(query, documents, top_k=2)
    for rank, r in enumerate(results, 1):
        print(f" {rank}. [{r.score:.4f}] {r.document}")

    # 5. 带 metadata
    print("\n[5] 带 metadata 测试...")
    metadata = [
        {"source": "中式英语之鉴", "topic": "翻译腔"},
        {"source": "翻译的技巧", "topic": "文化适配"},
        {"source": "术语库", "topic": "术语一致性"},
        {"source": "翻译教程", "topic": "被动语态"},
    ]
    results = model.rerank(query, documents, top_k=3, metadata=metadata)
    for rank, r in enumerate(results, 1):
        print(f" {rank}. [{r.score:.4f}] {r.document}")
        print(f" 元数据: {r.metadata}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)