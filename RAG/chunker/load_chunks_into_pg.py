"""
load_chunks_into_pg.py - 将切块 JSONL 批量写入 PostgreSQL数据库

职责:
1. 批量读取 chunks 目录下所有 JSONL
2. 从 JSONL 第一行 metadata 读取 document_id、title、category、language
3. 批量写入 chunks 表（幂等，已存在则跳过）

不负责:
- 计算 embedding（由 build_index.py 负责）
- 写入 Qdrant（由 build_index.py 负责）
- 创建 documents 记录（由 pdf_chunker.py 负责）
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from RAG.database import get_session
from RAG.orm_models import Document, Chunk


# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CHUNKS_DIR = PROJECT_ROOT / "data" / "output" / "rag" / "chunks"


# ============================================================
# JSONL 读取
# ============================================================
def _read_jsonl(jsonl_path: Path) -> tuple:
    """
    读取 JSONL，返回 (metadata, chunks)

    格式约定：
        第一行：{"_type": "metadata", ...}
        后续行：{"chunk_uid": ..., "document_id": ..., "content": ...}
    """
    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL 文件不存在: {jsonl_path}")

    metadata = {}
    chunks = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("_type") == "metadata":
                    metadata = obj
                else:
                    chunks.append(obj)
            except json.JSONDecodeError as e:
                logger.warning(f"第 {line_num} 行 JSON 解析失败: {e}")
                continue

    return metadata, chunks


# ============================================================
# 数据库操作
# ============================================================
def _get_existing_chunk_uids(session, chunk_uids: List[str]) -> set:
    """查询已存在的 chunk_uid（分批查询，避免 SQL 参数过多）"""
    if not chunk_uids:
        return set()

    batch_size = 500
    existing = set()
    for i in range(0, len(chunk_uids), batch_size):
        batch = chunk_uids[i:i + batch_size]
        rows = session.query(Chunk.chunk_uid).filter(
            Chunk.chunk_uid.in_(batch)
        ).all()
        existing.update(row[0] for row in rows)

    return existing


def _load_single_jsonl(
    jsonl_path: Path,
    skip_existing: bool = True,
) -> Dict[str, int]:
    """
    加载单个 JSONL 到 PG

    Returns:
        {"total": ..., "inserted": ..., "skipped": ..., "failed": ...}
    """
    # 1. 读取 JSONL
    metadata, chunks_data = _read_jsonl(jsonl_path)
    stats = {
        "total": len(chunks_data),
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
    }

    if not metadata:
        logger.warning(f"JSONL 缺少 metadata: {jsonl_path.name}，跳过")
        stats["failed"] = stats["total"]
        return stats

    if not chunks_data:
        logger.warning(f"JSONL 没有 chunk: {jsonl_path.name}")
        return stats

    document_id = metadata.get("document_id")
    if document_id is None:
        logger.warning(f"JSONL metadata 缺少 document_id: {jsonl_path.name}，跳过")
        stats["failed"] = stats["total"]
        return stats

    logger.info(
        f"JSONL: {jsonl_path.name}, "
        f"document_id={document_id}, "
        f"title={metadata.get('title')}, "
        f"chunks={len(chunks_data)}"
    )

    # 2. 提取所有 chunk_uid
    chunk_uids = [item.get("chunk_uid") for item in chunks_data if item.get("chunk_uid")]

    # 3. 数据库操作
    with get_session() as session:
        # 3.1 检查 document 是否存在（应该由 pdf_chunker.py 已创建）
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            logger.error(
                f"documents 表没有 id={document_id} 的记录，"
                f"请先运行 pdf_chunker.py 创建"
            )
            stats["failed"] = stats["total"]
            return stats

        logger.info(f"documents 记录已存在: id={document_id}, title={doc.title}")

        # 3.2 查询已存在的 chunk_uid
        if skip_existing:
            existing_uids = _get_existing_chunk_uids(session, chunk_uids)
            logger.info(f"已存在的 chunk: {len(existing_uids)} 条")
        else:
            existing_uids = set()

        # 3.3 组装待插入数据
        to_insert = []
        for item in chunks_data:
            chunk_uid = item.get("chunk_uid")
            content = item.get("content")

            if not chunk_uid or not content:
                stats["failed"] += 1
                continue

            if skip_existing and chunk_uid in existing_uids:
                stats["skipped"] += 1
                continue

            to_insert.append({
                "chunk_uid": chunk_uid,
                "document_id": document_id,
                "content": content,
            })

        # 3.4 批量插入（手动填 created_at）
        if to_insert:
            from datetime import datetime
            now = datetime.utcnow()
            for item in to_insert:
                item["created_at"] = now

            session.bulk_insert_mappings(Chunk, to_insert)
            stats["inserted"] = len(to_insert)
            logger.info(f"批量插入: {len(to_insert)} 条")
        else:
            logger.info("没有需要插入的数据")

    return stats


# ============================================================
# 批量入口（唯一对外入口）
# ============================================================
def load_all_chunks_into_pg(
    chunks_dir: Optional[str] = None,
    skip_existing: bool = True,
) -> Dict[str, Dict]:
    """
    批量加载 chunks 目录下所有 JSONL 到 PG

    Args:
        chunks_dir: JSONL 目录（默认 LaLe/data/output/rag/chunks）
        skip_existing: 已存在的 chunk_uid 是否跳过

    Returns:
        {文件名: {"total": ..., "inserted": ..., "skipped": ..., "failed": ...}}
    """
    if chunks_dir is None:
        chunks_dir = DEFAULT_CHUNKS_DIR
    chunks_dir = Path(chunks_dir)

    if not chunks_dir.exists():
        raise FileNotFoundError(f"目录不存在: {chunks_dir}")

    # 1. 查找所有 JSONL
    jsonl_files = sorted(chunks_dir.glob("*.jsonl"))
    if not jsonl_files:
        logger.warning(f"目录下没有 JSONL: {chunks_dir}")
        return {}

    logger.info(f"发现 {len(jsonl_files)} 个 JSONL 文件")

    # 2. 逐个处理
    all_stats = {}
    for jsonl_file in jsonl_files:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"处理: {jsonl_file.name}")
        logger.info(f"{'=' * 60}")

        try:
            stats = _load_single_jsonl(
                jsonl_path=jsonl_file,
                skip_existing=skip_existing,
            )
            all_stats[jsonl_file.name] = stats
        except Exception as e:
            logger.error(f"处理失败: {jsonl_file.name} - {e}")
            all_stats[jsonl_file.name] = {"error": str(e)}

    return all_stats


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 在这里修改参数
    # ================================================
    CHUNKS_DIR = None        # None 表示用默认值（data/output/rag/chunks）
    SKIP_EXISTING = True     # 幂等：已存在则跳过
    # ================================================

    print("=" * 60)
    print("批量加载 JSONL → PostgreSQL")
    print("=" * 60)
    print(f"JSONL 目录: {CHUNKS_DIR or DEFAULT_CHUNKS_DIR}")
    print(f"skip_existing: {SKIP_EXISTING}")
    print("=" * 60)

    all_stats = load_all_chunks_into_pg(
        chunks_dir=CHUNKS_DIR,
        skip_existing=SKIP_EXISTING,
    )

    print("\n" + "=" * 60)
    print(f"✅ 批量加载完成: {len(all_stats)} 个 JSONL")
    print("=" * 60)

    # 汇总统计
    total_all = {"total": 0, "inserted": 0, "skipped": 0, "failed": 0}
    for filename, stats in all_stats.items():
        if "error" in stats:
            print(f"  ❌ {filename}: {stats['error']}")
            continue

        print(
            f"✅ {filename}: "
            f"total={stats['total']}, "
            f"inserted={stats['inserted']}, "
            f"skipped={stats['skipped']}, "
            f"failed={stats['failed']}"
        )
        for key in total_all:
            total_all[key] += stats.get(key, 0)

    print("\n" + "-" * 60)
    print(
        f"总计: total={total_all['total']}, "
        f"inserted={total_all['inserted']}, "
        f"skipped={total_all['skipped']}, "
        f"failed={total_all['failed']}"
    )
    print("-" * 60)