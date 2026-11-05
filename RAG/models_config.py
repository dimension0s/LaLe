"""
models_config.py - RAG 模块的模型配置
路径: /home/bina/LaLe/RAG/models_config.py

包含:
- Embedding 模型配置（bge-m3）,降级版：bge-base-zh-v1.5
- Reranker 模型配置（bge-reranker-v2-m3），降级版：bge-reranker-base
"""

from dataclasses import dataclass
from pathlib import Path

# ============================================================
# 项目根目录（供模型缓存路径使用）
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# Embedding 模型配置（bge-m3）
# ============================================================
@dataclass
class EmbeddingConfig:
    """Embedding 模型配置"""
    model_id:str = "bge-m3"  # 用于pg中的index_meta表的模型录入，优于路径录入
    model_name: str = str(PROJECT_ROOT / "data/models/BAAI/bge-m3") # 绝对路径
    # model_name: str = "BAAI/bge-m3"  # 触发下载
    embedding_dim: int = 1024          # bge-m3 输出维度，必须与 Qdrant collection 的向量维度一致
    max_length: int = 8192             # 最大输入 token 数，该模型支持长文本，可处理较长 chunk
    batch_size: int = 16               # 批处理大小
    device: str = "cuda"               # cuda / cpu / mps
    normalize_embeddings: bool = True  # 是否 L2 归一化，配个余弦距离使用
    # cache_dir: Optional[str] = None    # 模型缓存目录，None 使用默认

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "max_length": self.max_length,
            "batch_size": self.batch_size,
            "device": self.device,
            "normalize_embeddings": self.normalize_embeddings,
        }


# ============================================================
# Reranker 模型配置（bge-reranker-v2-m3）
# ============================================================
@dataclass
class RerankerConfig:
    """Reranker 模型配置"""
    # model_name: str = "BAAI/bge-reranker-v2-m3"
    model_id: str = "bge-reranker-v2-m3"
    model_name: str = str(PROJECT_ROOT / "data/models/BAAI/bge-reranker-v2-m3")  # 本地模型路径
    max_length: int = 512              # reranker 通常处理较短的 query-passage 对
    batch_size: int = 8
    device: str = "cuda"
    # cache_dir: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "max_length": self.max_length,
            "batch_size": self.batch_size,
            "device": self.device,
        }


# ============================================================
# 默认实例
# ============================================================
DEFAULT_EMBEDDING_CONFIG = EmbeddingConfig()
DEFAULT_RERANKER_CONFIG = RerankerConfig()


def get_embedding_config() -> EmbeddingConfig:
    """获取 Embedding 模型配置"""
    return DEFAULT_EMBEDDING_CONFIG


def get_reranker_config() -> RerankerConfig:
    """获取 Reranker 模型配置"""
    return DEFAULT_RERANKER_CONFIG


















