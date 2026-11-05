"""
load_files_into_pg.py - 将解析后的 JSON 文件批量加载到 PostgreSQL
路径: /home/bina/LaLe/user_manager/pg_data_manager/load_files_into_pg.py

职责:
1. 扫描 data/output/user_files_parsed/ 下的所有 JSON
2. 读取 JSON 元信息
3. 插入 user_documents 表（幂等）

不负责:
- 文件解析（由 parsers/ 负责）
- 回收站操作（由 recycle.py 负责）
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from .database import get_session
from .orm_models import UserDocument


# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PARSED_DIR = PROJECT_ROOT / "data" / "output" / "user_files_parsed"


# ============================================================
# JSON 读取
# ============================================================
def _read_parsed_json(json_path: Path) -> Optional[Dict]:
    """读取解析后的 JSON"""
    if not json_path.exists():
        logger.warning(f"JSON 不存在: {json_path}")
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {json_path} - {e}")
        return None


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """解析 ISO 格式时间字符串"""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None


# ============================================================
# 单个 JSON 入库
# ============================================================
def _load_single_json(
    json_path: Path,
    skip_existing: bool = True,
) -> Dict:
    """
    加载单个 JSON 到 PG

    Returns:
        {"status": "inserted" / "skipped" / "failed", "doc_id": ..., "error": ...}
    """
    # 1. 读取 JSON
    data = _read_parsed_json(json_path)
    if data is None:
        return {"status": "failed", "error": "JSON 读取失败"}

    # 2. 校验关键字段
    required_fields = ["file_name", "file_type", "file_path"]
    for field in required_fields:
        if not data.get(field):
            logger.warning(f"JSON 缺少字段 {field}: {json_path.name}")
            return {"status": "failed", "error": f"缺少字段 {field}"}

    file_path = data["file_path"]
    file_name = data["file_name"]

    # 3. 幂等检查
    with get_session() as session:
        if skip_existing:
            existing = session.query(UserDocument).filter_by(
                file_path=file_path
            ).first()
            if existing:
                logger.info(
                    f"⏭️ 跳过（已存在）: {file_name} → "
                    f"doc_id={existing.id}, doc_uuid={existing.doc_uuid[:8]}..."
                )
                return {
                    "status": "skipped",
                    "doc_id": existing.id,
                    "doc_uuid": existing.doc_uuid,
                }

        # 4. 构造记录
        doc = UserDocument(
            user_id=1,
            file_name=file_name,
            file_type=data["file_type"],
            source_channel=data.get("source_channel", "file"),
            file_path=file_path,
            file_size=data.get("file_size"),
            status="active",
            meta={
                "parsed_at": data.get("parsed_at"),   # 只保留 parsed_at
            },
        )

        # 用 JSON 的 created_at 作为数据库记录的创建时间
        created_at = _parse_datetime(data.get("created_at"))
        if created_at:
            doc.created_at = created_at

        session.add(doc)
        session.flush()

        doc_id = doc.id
        doc_uuid = doc.doc_uuid

    logger.info(
        f"✅ 入库: {file_name} → "
        f"doc_id={doc_id}, doc_uuid={doc_uuid[:8]}..."
    )

    return {
        "status": "inserted",
        "doc_id": doc_id,
        "doc_uuid": doc_uuid,
    }


# ============================================================
# 批量入口
# ============================================================
def load_all_parsed_files(
    parsed_dir: Optional[str] = None,
    skip_existing: bool = True,
) -> Dict[str, Dict]:
    """
    批量加载所有解析好的 JSON 到 PG

    Args:
        parsed_dir: JSON 目录（默认 data/output/user_files_parsed/）
        skip_existing: 已存在的文件是否跳过

    Returns:
        {文件名: {"status": ..., "doc_id": ..., ...}}
    """
    if parsed_dir is None:
        parsed_dir = DEFAULT_PARSED_DIR
    else:
        parsed_dir = Path(parsed_dir)

    if not parsed_dir.exists():
        logger.error(f"目录不存在: {parsed_dir}")
        return {}

    # 1. 查找所有 JSON
    json_files = sorted(parsed_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"目录下没有 JSON: {parsed_dir}")
        return {}

    logger.info(f"发现 {len(json_files)} 个 JSON 文件")

    # 2. 逐个处理
    results = {}
    for json_file in json_files:
        try:
            result = _load_single_json(
                json_path=json_file,
                skip_existing=skip_existing,
            )
            results[json_file.name] = result
        except Exception as e:
            logger.error(f"处理失败: {json_file.name} - {e}")
            results[json_file.name] = {"status": "failed", "error": str(e)}

    return results


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 测试参数
    # ================================================
    PARSED_DIR = None       # None 表示用默认目录
    SKIP_EXISTING = True
    # ================================================

    print("=" * 60)
    print("批量加载解析 JSON → PostgreSQL")
    print("=" * 60)
    print(f"JSON 目录: {PARSED_DIR or DEFAULT_PARSED_DIR}")
    print(f"跳过已存在: {SKIP_EXISTING}")
    print("=" * 60)

    results = load_all_parsed_files(
        parsed_dir=PARSED_DIR,
        skip_existing=SKIP_EXISTING,
    )

    print("\n" + "=" * 60)
    print(f"✅ 批量加载完成: {len(results)} 个 JSON")
    print("=" * 60)

    # 统计
    inserted = 0
    skipped = 0
    failed = 0

    for filename, info in results.items():
        status = info.get("status")
        if status == "inserted":
            print(f"  ✅ {filename}: doc_id={info['doc_id']}")
            inserted += 1
        elif status == "skipped":
            print(f"  ⏭️  {filename}: 已存在 (doc_id={info['doc_id']})")
            skipped += 1
        else:
            print(f"  ❌ {filename}: {info.get('error', '未知错误')}")
            failed += 1

    print("\n" + "-" * 60)
    print(f"总计: 插入 {inserted} 个, 跳过 {skipped} 个, 失败 {failed} 个")
    print("-" * 60)