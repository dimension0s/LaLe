"""
qdrant_config.py - Qdrant 向量数据库配置
路径: /home/bina/LaLe/RAG/qdrant_config.py

包含:
- 连接配置（host / port / api_key）
- Collection 配置（向量维度、距离度量、HNSW 索引参数）
- 量化配置（可选）
"""

from dataclasses import dataclass, field
from typing import Optional
from qdrant_client.models import Distance

# ============================================================
# 连接配置
# ============================================================
@dataclass
class QdrantConnectionConfig:
    """Qdrant 连接配置"""
    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    api_key: Optional[str] = None      # 本地无鉴权时留空
    prefer_grpc: bool = False          # 是否优先使用 gRPC
    timeout: int = 30                  # 请求超时（秒）

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "grpc_port": self.grpc_port,
            "prefer_grpc": self.prefer_grpc,
            "timeout": self.timeout,
        }


# ============================================================
# HNSW 索引配置
# ============================================================
@dataclass
class HNSWConfig:
    """HNSW 索引参数"""
    m: int = 16                        # 每层最大连接数，16-32 平衡；64+ 高精度
    ef_construct: int = 100            # 构建时候选集大小，100-200 平衡
    full_scan_threshold: int = 10000   # 低于此规模时使用全扫描
    on_disk: bool = False              # 是否将索引存磁盘

    def to_dict(self) -> dict:
        return {
            "m": self.m,
            "ef_construct": self.ef_construct,
            "full_scan_threshold": self.full_scan_threshold,
            "on_disk": self.on_disk,
        }


# ============================================================
# Collection 配置
# ============================================================
@dataclass
class QdrantCollectionConfig:
    """Qdrant Collection 配置"""
    collection_name: str = "lale_knowledge"
    vector_size: int = 1024            # 必须与 embedding_dim 一致
    distance: Distance = Distance.COSINE
    on_disk: bool = False              # 向量是否存磁盘
    hnsw: HNSWConfig = field(default_factory=HNSWConfig)
    # 量化配置（可选，数据量大时启用可省内存）
    quantization_enabled: bool = False
    quantization_type: str = "scalar"  # scalar / binary

    def to_dict(self) -> dict:
        return {
            "collection_name": self.collection_name,
            "vector_size": self.vector_size,
            "distance": self.distance.value if hasattr(self.distance, 'value') else str(self.distance),
            "on_disk": self.on_disk,
            "hnsw": self.hnsw.to_dict(),
            "quantization_enabled": self.quantization_enabled,
        }


# ============================================================
# 默认实例
# ============================================================
DEFAULT_CONNECTION = QdrantConnectionConfig()
DEFAULT_COLLECTION = QdrantCollectionConfig()


def get_connection_config() -> QdrantConnectionConfig:
    """获取 Qdrant 连接配置"""
    return DEFAULT_CONNECTION


def get_collection_config() -> QdrantCollectionConfig:
    """获取 Qdrant Collection 配置"""
    return DEFAULT_COLLECTION