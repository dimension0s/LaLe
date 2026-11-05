"""
embedding.py - 文本向量化（基于 bge-m3）
路径: /home/bina/LaLe/RAG/embedding.py

职责:
1. 加载 bge-m3 模型（单例）
2. 文本 → 向量（单条 / 批量）
3. 提供便捷函数给上层调用

"""

from typing import List, Union, Optional

import numpy as np
from loguru import logger

from RAG.models_config import (
    EmbeddingConfig,
    get_embedding_config,
)


# ============================================================
# Embedding 模型封装
# ============================================================
class EmbeddingModel:
    """bge-m3 Embedding 模型封装（单例）"""

    _instance: Optional["EmbeddingModel"] = None

    def __new__(cls, *args, **kwargs):
        """单例模式：全局复用一个模型实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        # 避免重复初始化
        if getattr(self, "_initialized", False):
            return

        self.config = config or get_embedding_config()
        self.model = None

        self._load_model()
        self._initialized = True

    # ========================================================
    # 模型加载
    # ========================================================
    def _load_model(self):
        """加载 bge-m3 模型"""
        # 从本地加载模型
        model_path = self.config.model_name
        logger.info(f"正在从本地加载模型: {model_path}")
        # 优先使用 FlagEmbedding（bge 官方推荐，支持多语言、长文本）
        from FlagEmbedding import BGEM3FlagModel

        logger.info(f"正在加载 {self.config.model_name}（FlagEmbedding）...")

        self.model = BGEM3FlagModel(
            model_path,
            # self.config.model_name,  # 被替换成了本地加载模型的参数
            use_fp16=(self.config.device == "cuda"),
            device=self.config.device,
            normalize_embeddings=self.config.normalize_embeddings,
        )
        self._backend = "flagembedding"
        # logger.info(f"✅ 模型加载完成: {self.config.model_name}")
        logger.info(f"✅ 模型加载完成: {model_path}")  # 被替换成了本地加载模型的参数
        return

        # # 回退 sentence-transformers
        # try:
        #     from sentence_transformers import SentenceTransformer
        #     self.model = SentenceTransformer(
        #         # self.config.model_name,
        #         model_path,  # 改为直接传本地路径
        #         device=self.config.device,
        #         cache_folder=self.config.cache_dir,
        #     )
        #     self.model.max_seq_length = self.config.max_length
        #     self._backend = "sentence_transformers"
        #     # logger.info(f"✅ 模型加载完成: {self.config.model_name}")
        #     logger.info(f"✅ 模型加载完成: {model_path}")
        # except ImportError:
        #     raise ImportError(
        #         "请安装 FlagEmbedding 或 sentence-transformers：\n"
        #         "  pip install FlagEmbedding\n"
        #         "  或 pip install sentence-transformers"
        #     )

    # ========================================================
    # 单条编码
    # ========================================================
    def encode(
        self,
        text: str,
        normalize: Optional[bool] = None,
    ) -> List[float]:
        """
        单条文本编码

        Args:
            text: 待编码文本
            normalize: 是否 L2 归一化，None 则用配置值

        Returns:
            List[float]，长度等于 embedding_dim
        """
        if not text or not text.strip():
            raise ValueError("待编码文本不能为空")

        result = self.model.encode(
            [text.strip()],
            batch_size=1,
            max_length=self.config.max_length,
        )
        vec = result["dense_vecs"][0]

        return vec.tolist() if isinstance(vec, np.ndarray) else list(vec)


    # ========================================================
    # 批量编码
    # ========================================================
    def encode_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """
        批量文本编码

        Args:
            texts: 文本列表
            batch_size: 批大小，None 则用配置值
            show_progress: 是否显示进度条

        Returns:
            List[Optional[List[float]]]
            - 长度等于 len(texts)
            - 非空文本对应 List[float]（向量）
            - 空文本对应 None
        """
        if not texts:
            return []

        # 过滤空文本（保留位置，用 None 占位）
        cleaned = [t.strip() if t and t.strip() else "" for t in texts]
        # 找出非空文本的索引，比如：cleaned = ["hello", "", "", "world"]，则索引为：valid_indices = [0, 3]
        valid_indices = [i for i, t in enumerate(cleaned) if t]
        # 提取非空文本
        valid_texts = [cleaned[i] for i in valid_indices]

        if not valid_texts:
            logger.warning("所有文本都为空，返回全 None 列表")
            return [None] * len(texts)

        # 默认参数值
        if batch_size is None:
            batch_size = self.config.batch_size

        logger.info(f"开始批量编码: {len(valid_texts)} 条有效文本（共 {len(texts)} 条），batch_size={batch_size}")

        result = self.model.encode(
            valid_texts,
            batch_size=batch_size,
            max_length=self.config.max_length,
        )
        # dense_vecs：字典键之一，稠密向量，这是bge-m3模型的特点之一，它支持三种检索方式，除稠密向量外，还包含稀疏向量、多向量
        # 这里只需用到稠密向量
        vectors = result["dense_vecs"]
        # 统一转成 Python list，即np.ndarray.tolist() 转成嵌套的 Python list
        # 因为Qdrant 的 upsert 接受 List[List[float]]，不接受 numpy 数组，JSON 序列化也只接受 Python list
        # 比如：np.ndarray 形状 (2, 4)：
        # array([[0.1, 0.2, 0.3, 0.4],
        #        [0.5, 0.6, 0.7, 0.8]])
        # tolist() 后：
        # [[0.1, 0.2, 0.3, 0.4],
        #  [0.5, 0.6, 0.7, 0.8]]
        if isinstance(vectors, np.ndarray):
            vectors = vectors.tolist()


        # 还原到原位置：非空为止填向量，空为止填None
        aligned = [None] * len(texts)
        for idx, vec in zip(valid_indices, vectors):
            aligned[idx] = vec

        logger.info(f"✅ 批量编码完成: {len(vectors)} 条有效 / {len(texts)} 条输入")
        return aligned

    # ========================================================
    # 便捷：直接返回 numpy 数组
    # ========================================================
    def encode_to_numpy(
        self,
        texts: Union[str, List[str]],
        normalize: Optional[bool] = None,
    ) -> np.ndarray:
        """编码并返回 numpy 数组（便于后续计算）"""
        if isinstance(texts, str):
            return np.array([self.encode(texts, normalize)])
        else:
            return np.array(self.encode_batch(texts, normalize=normalize))

    # ========================================================
    # 计算相似度（调试用）
    # ========================================================
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    # ========================================================
    # 属性
    # ========================================================
    @property
    def dim(self) -> int:
        """向量维度"""
        return self.config.embedding_dim

    @property
    def backend(self) -> str:
        """当前使用的后端"""
        return self._backend


# ============================================================
# 便捷函数
# ============================================================
def get_embedding_model() -> EmbeddingModel:
    """获取全局 Embedding 模型实例"""
    return EmbeddingModel()


def encode(text: str, normalize: Optional[bool] = None) -> List[float]:
    """单条编码便捷函数"""
    return get_embedding_model().encode(text, normalize=normalize)


def encode_batch(
    texts: List[str],
    batch_size: Optional[int] = None,
    normalize: Optional[bool] = None,
) -> List[List[float]]:
    """批量编码便捷函数"""
    return get_embedding_model().encode_batch(
        texts, batch_size=batch_size, normalize=normalize,
    )


# ============================================================
# 命令行入口：测试
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Embedding 模型测试")
    print("=" * 60)

    # 1. 加载模型
    print("\n[1] 加载模型...")
    model = get_embedding_model()
    print(f"✅ 模型: {model.config.model_name}")
    print(f"   维度: {model.dim}")
    print(f"   设备: {model.config.device}")

    # 2. 单条编码
    print("\n[2] 单条编码...")
    text1 = "翻译时避免'进行……的处理'这类翻译腔"
    vec1 = model.encode(text1)
    print(f" 文本: {text1}")
    print(f" 向量维度: {len(vec1)}")
    print(f" 向量前 5 维: {vec1[:5]}")
    print(f" 向量 L2 范数: {np.linalg.norm(vec1):.4f}")

    # 3. 批量编码
    print("\n[3] 批量编码...")
    texts = [
        "翻译时避免翻译腔",
        "black sheep 应译为害群之马",
        "Federal Reserve 应统一译为美联储",
        "被动语态在中英翻译中的处理",
    ]
    vecs = model.encode_batch(texts)
    print(f" 批量数量: {len(vecs)}")
    print(f" 每条维度: {len(vecs[0])}")

    # 4. 相似度测试
    print("\n[4] 相似度测试...")
    text_query = "翻译腔怎么避免"
    vec_query = model.encode(text_query)

    # 计算 query 与批量中每条文本的相似度
    print(f" Query: {text_query}")
    for i, (t, v) in enumerate(zip(texts, vecs)):
        sim = model.cosine_similarity(vec_query, v)
        print(f"   [{i}] 相似度 {sim:.4f}  {t}")

    # 5. 验证归一化
    print("\n[5] 验证归一化...")
    norms = [np.linalg.norm(v) for v in vecs]
    print(f" 所有向量 L2 范数: {[f'{n:.4f}' for n in norms]}")
    print(f" 是否都接近 1.0: {all(abs(n - 1.0) < 1e-5 for n in norms)}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)