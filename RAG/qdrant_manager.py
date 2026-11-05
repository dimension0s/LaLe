"""
qdrant_manager.py - Qdrant 向量数据库客户端封装
路径: /home/bina/LaLe/RAG/qdrant_manager.py

职责:
1. 管理 Qdrant 连接（单例）
2. Collection 生命周期管理（创建/删除/检查）
3. 向量的增删改查（upsert / search / delete）
4. 统一返回结构，便于上层调用

不负责:
- 文本 → 向量（由 embedding.py 负责）
- 重排序（由 reranker.py 负责）
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from RAG.qdrant_config import (
    QdrantConnectionConfig,
    QdrantCollectionConfig,
    get_connection_config,
    get_collection_config,
)


# ============================================================
# 统一返回结构
# ============================================================
@dataclass
class SearchHit:
    """单条检索结果"""
    chunk_uid: str
    score: float
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_uid": self.chunk_uid,
            "score": self.score,
            "payload": self.payload,
        }


# ============================================================
# 客户端封装
# ============================================================
class QdrantManager:
    """Qdrant 客户端管理器"""

    _instance: Optional["QdrantManager"] = None

    def __new__(cls, *args, **kwargs):
        """单例模式：全局复用一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        connection_config: Optional[QdrantConnectionConfig] = None,
        collection_config: Optional[QdrantCollectionConfig] = None,
    ):
        # 避免重复初始化
        if getattr(self, "_initialized", False):
            return

        self.conn_config = connection_config or get_connection_config()
        self.coll_config = collection_config or get_collection_config()

        # 创建客户端
        self.client = QdrantClient(
            host=self.conn_config.host,
            port=self.conn_config.port,
            grpc_port=self.conn_config.grpc_port,
            prefer_grpc=self.conn_config.prefer_grpc,
            api_key=self.conn_config.api_key,
            timeout=self.conn_config.timeout,
        )

        self._initialized = True
        logger.info(
            f"QdrantManager 初始化完成: {self.conn_config.url}, "
            f"collection={self.coll_config.collection_name}"
        )

    # ========================================================
    # 连接检查
    # ========================================================
    def ping(self) -> bool:
        """检查 Qdrant 服务是否可用"""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant 连接失败: {e}")
            return False

    # ========================================================
    # Collection 生命周期
    # ========================================================
    def collection_exists(self) -> bool:
        """检查 collection 是否存在"""
        try:
            collections = self.client.get_collections().collections
            names = [c.name for c in collections]
            return self.coll_config.collection_name in names
        except Exception as e:
            logger.error(f"检查 collection 失败: {e}")
            return False

    def create_collection(self, recreate: bool = False) -> bool:
        """
        创建 collection

        Args:
            recreate: 如果已存在是否删除后重建

        Returns:
            是否创建成功
        """
        name = self.coll_config.collection_name
        exists = self.collection_exists()

        if exists:
            if recreate:
                logger.warning(f"Collection {name} 已存在，将删除后重建")
                self.delete_collection()
            else:
                logger.info(f"Collection {name} 已存在，跳过创建")
                return True

        try:
            # 向量参数
            vectors_config = qmodels.VectorParams(
                size=self.coll_config.vector_size,
                distance=self.coll_config.distance,
                on_disk=self.coll_config.on_disk,
            )

            # HNSW 参数
            hnsw_config = qmodels.HnswConfigDiff(
                m=self.coll_config.hnsw.m,
                ef_construct=self.coll_config.hnsw.ef_construct,
                full_scan_threshold=self.coll_config.hnsw.full_scan_threshold,
                on_disk=self.coll_config.hnsw.on_disk,
            )

            # 量化配置（可选）
            quantization_config = None
            if self.coll_config.quantization_enabled:
                if self.coll_config.quantization_type == "scalar":
                    quantization_config = qmodels.ScalarQuantization(
                        scalar=qmodels.ScalarQuantizationConfig(
                            type=qmodels.ScalarType.INT8,
                            always_ram=True,
                        )
                    )
                elif self.coll_config.quantization_type == "binary":
                    quantization_config = qmodels.BinaryQuantization(
                        binary=qmodels.BinaryQuantizationConfig(always_ram=True)
                    )

            self.client.create_collection(
                collection_name=name,
                vectors_config=vectors_config,
                hnsw_config=hnsw_config,
                quantization_config=quantization_config,
            )
            logger.info(f"✅ Collection {name} 创建成功")
            return True

        except Exception as e:
            logger.error(f"创建 collection 失败: {e}")
            return False

    def delete_collection(self) -> bool:
        """删除 collection"""
        name = self.coll_config.collection_name
        try:
            self.client.delete_collection(collection_name=name)
            logger.info(f"✅ Collection {name} 已删除")
            return True
        except Exception as e:
            logger.error(f"删除 collection 失败: {e}")
            return False

    def get_collection_info(self) -> Optional[Dict[str, Any]]:
        """获取 collection 信息"""
        name = self.coll_config.collection_name
        try:
            info = self.client.get_collection(collection_name=name)
            return {
                "name": name,
                "vectors_count": getattr(info, "vectors_count", None),
                "points_count": getattr(info, "points_count", None),
                "status": str(getattr(info, "status", None)),
                "config": {
                    "vector_size": self.coll_config.vector_size,
                    "distance": str(self.coll_config.distance),
                },
            }
        except Exception as e:
            logger.error(f"获取 collection 信息失败: {e}")
            return None

    # ========================================================
    # 向量写入
    # ========================================================
    def upsert(
        self,
        points: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """
        批量写入向量

        Args:
            points: 列表，每项格式：
                {
                    "id": "chunk_uid 或 整数ID",
                    "vector": [0.1, 0.2, ...],
                    "payload": {"chunk_uid": "...", "document_id": 1, ...}
                }
            batch_size: 每批写入数量

        Returns:
            成功写入的数量
        """
        if not points:
            return 0

        name = self.coll_config.collection_name
        total = 0

        try:
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                qdrant_points = [
                    qmodels.PointStruct(
                        id=p["id"],
                        vector=p["vector"],
                        payload=p.get("payload", {}),
                    )
                    for p in batch
                ]
                self.client.upsert(
                    collection_name=name,
                    points=qdrant_points,
                    wait=True,
                )
                total += len(batch)
                logger.debug(f"已写入 {total}/{len(points)} 条")

            logger.info(f"✅ 成功写入 {total} 条向量")
            return total

        except Exception as e:
            logger.error(f"写入向量失败: {e}")
            raise

    # ========================================================
    # 向量检索
    # ========================================================
    def search(
            self,
            query_vector: List[float],
            top_k: int = 10,
            score_threshold: Optional[float] = None,
            query_filter: Optional[qmodels.Filter] = None,
            with_payload: bool = True,
    ) -> List[SearchHit]:
        """
        向量检索（兼容 qdrant-client 1.16+）

        Args:
            query_vector: 查询向量
            top_k: 返回条数
            score_threshold: 分数阈值
            query_filter: Qdrant 过滤器
            with_payload: 是否返回 payload

        Returns:
            List[SearchHit]
        """
        name = self.coll_config.collection_name
        try:
            response = self.client.query_points(
                collection_name=name,
                query=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=with_payload,
            )
            results = response.points

            hits = []
            for r in results:
                payload = r.payload or {}
                chunk_uid = payload.get("chunk_uid", str(r.id))
                hits.append(SearchHit(
                    chunk_uid=chunk_uid,
                    score=float(r.score),
                    payload=payload,
                ))
            return hits

        except Exception as e:
            logger.error(f"检索失败: {e}")
            return []

    def search_batch(
            self,
            query_vectors: List[List[float]],
            top_k: int = 10,
            score_threshold: Optional[float] = None,
            query_filter: Optional[qmodels.Filter] = None,
    ) -> List[List[SearchHit]]:
        """批量向量检索"""
        name = self.coll_config.collection_name
        try:
            responses = self.client.query_batch_points(
                collection_name=name,
                queries=[
                    qmodels.QueryRequest(
                        query=qv,
                        limit=top_k,
                        score_threshold=score_threshold,
                        filter=query_filter,
                        with_payload=True,
                    )
                    for qv in query_vectors
                ],
            )

            all_hits = []
            for response in responses:
                hits = []
                for r in response.points:
                    payload = r.payload or {}
                    chunk_uid = payload.get("chunk_uid", str(r.id))
                    hits.append(SearchHit(
                        chunk_uid=chunk_uid,
                        score=float(r.score),
                        payload=payload,
                    ))
                all_hits.append(hits)
            return all_hits

        except Exception as e:
            logger.error(f"批量检索失败: {e}")
            return [[] for _ in query_vectors]

    # ========================================================
    # 删除
    # ========================================================
    def delete_by_ids(self, ids: List[Union[str, int]]) -> bool:
        """按 ID 删除向量"""
        name = self.coll_config.collection_name
        try:
            self.client.delete(
                collection_name=name,
                points_selector=qmodels.PointIdsList(points=ids),
                wait=True,
            )
            logger.info(f"✅ 已删除 {len(ids)} 条向量")
            return True
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False

    def delete_by_filter(self, query_filter: qmodels.Filter) -> bool:
        """按 payload 条件删除"""
        name = self.coll_config.collection_name
        try:
            self.client.delete(
                collection_name=name,
                points_selector=qmodels.FilterSelector(filter=query_filter),
                wait=True,
            )
            logger.info("✅ 按条件删除成功")
            return True
        except Exception as e:
            logger.error(f"按条件删除失败: {e}")
            return False

    # ========================================================
    # 滚动遍历（用于全量导出/调试）
    # ========================================================
    def scroll(
        self,
        limit: int = 100,
        offset: Optional[Union[str, int]] = None,
        query_filter: Optional[qmodels.Filter] = None,
        with_payload: bool = True,
    ) -> tuple:
        """
        滚动遍历 collection

        Returns:
            (points, next_offset)
        """
        name = self.coll_config.collection_name
        try:
            points, next_offset = self.client.scroll(
                collection_name=name,
                limit=limit,
                offset=offset,
                scroll_filter=query_filter,
                with_payload=with_payload,
            )
            return points, next_offset
        except Exception as e:
            logger.error(f"滚动遍历失败: {e}")
            return [], None

    # ========================================================
    # 关闭
    # ========================================================
    def close(self):
        """关闭客户端连接"""
        try:
            self.client.close()
            logger.info("Qdrant 客户端已关闭")
        except Exception as e:
            logger.warning(f"关闭 Qdrant 客户端时出错: {e}")


# ============================================================
# 便捷函数
# ============================================================
def get_qdrant_manager() -> QdrantManager:
    """获取全局 QdrantManager 实例"""
    return QdrantManager()


# ============================================================
# 命令行入口：测试连接和 collection 管理
# ============================================================
if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Qdrant 客户端测试")
    print("=" * 60)

    manager = QdrantManager()

    # 1. 测试连接
    print("\n[1] 测试连接...")
    if not manager.ping():
        print("❌ 无法连接 Qdrant，请检查服务是否启动")
        sys.exit(1)
    print(f"✅ 连接成功: {manager.conn_config.url}")

    # 2. 查看 collection 是否存在
    print("\n[2] 检查 collection...")
    exists = manager.collection_exists()
    print(f"Collection {manager.coll_config.collection_name} 存在: {exists}")

    # 3. 命令行操作
    if len(sys.argv) >= 2:
        cmd = sys.argv[1]

        if cmd == "create":
            recreate = len(sys.argv) >= 3 and sys.argv[2] == "--recreate"
            manager.create_collection(recreate=recreate)
            print(f"✅ Collection 创建完成")

        elif cmd == "delete":
            manager.delete_collection()
            print(f"✅ Collection 已删除")

        elif cmd == "info":
            info = manager.get_collection_info()
            if info:
                import json
                print(json.dumps(info, ensure_ascii=False, indent=2))
            else:
                print("❌ 获取信息失败")

        elif cmd == "ping":
            print("✅ Qdrant 服务可用")

        else:
            print(f"未知命令: {cmd}")
            print("可用命令: create [--recreate] | delete | info | ping")
    else:
        print("\n用法:")
        print("  python qdrant_manager.py ping")
        print("  python qdrant_manager.py create [--recreate]")
        print("  python qdrant_manager.py delete")
        print("  python qdrant_manager.py info")