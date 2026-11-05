"""
upload.py - 用户文件上传入口

职责:
1. 接收源文件路径
2. 复制到 data/user_uploads/{user_id}/
3. 调用对应 parser（生成 JSON）
4. 将parser解析到的关键信息入库

不负责:
- 文件解析（由 parsers/ 负责）
"""

import sys
from pathlib import Path

# 兼容直接运行
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import shutil
from typing import Optional

from loguru import logger

# 绝对导入
from user_manager.parsers import pdf_parser, txt_parser, docx_parser,image_parser
from user_manager.pg_data_manager.database import get_session
from user_manager.pg_data_manager.orm_models import UserDocument

# 配置
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "data" / "user_uploads"


# ============================================================
# 辅助函数
# ============================================================
def _resolve_filename(user_dir: Path, filename: str) -> Path:
    """
    解决同名文件（加编号）

    例：
        The Economist.pdf     → The Economist.pdf
        The Economist.pdf     → The Economist_1.pdf
        The Economist.pdf     → The Economist_2.pdf
    """
    stem = Path(filename).stem
    suffix = Path(filename).suffix

    target = user_dir / filename
    counter = 1

    while target.exists():
        target = user_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    return target


def _dispatch_parser(file_path: str):
    """
    根据扩展名选择 parser

    Returns:
        parser 函数（parse_pdf / parse_txt / parse_docx）
    """
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        return pdf_parser.parse_pdf
    elif suffix in (".txt", ".md", ".markdown"):
        return txt_parser.parse_txt
    elif suffix in (".doc", ".docx"):
        return docx_parser.parse_docx
    elif suffix in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"):
        return image_parser.parse_image
    else:
        raise ValueError(f"不支持的文件类型: {suffix}")


# ============================================================
# 主函数
# ============================================================
def upload_file(
    source_path: str,
    user_id: int = 1,
    title: Optional[str] = None,
) -> Optional[UserDocument]:
    """
    上传用户文件（完整流程）

    1. 复制到用户目录
    2. 解析
    3. 直接入库（file_path 用复制后路径）
    """
    # 1. 校验
    source = Path(source_path)
    if not source.exists():
        logger.error(f"源文件不存在: {source_path}")
        return None
    if not source.is_file():
        logger.error(f"不是文件: {source_path}")
        return None

    logger.info("=" * 60)
    logger.info(f"上传文件: {source.name}")
    logger.info(f"  用户: {user_id}")
    logger.info(f"  源路径: {source_path}")
    logger.info("=" * 60)

    # 2. 复制到用户目录
    user_dir = DEFAULT_UPLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    target_path = _resolve_filename(user_dir, source.name)
    shutil.copy2(source, target_path)
    logger.info(f"[1/3] 文件已复制: {target_path}")

    # 3. 解析（生成 JSON）
    try:
        parse_func = _dispatch_parser(str(target_path))
        parsed_result = parse_func(str(target_path), save_json=False)
        logger.info(f"[2/3] 解析完成: {parsed_result['file_name']}")
    except Exception as e:
        logger.error(f"解析失败: {e}")
        return None

    # 4. 构造meta
    file_type = parsed_result.get("file_type", "")
    meta = {
        "parsed_at": parsed_result.get("parsed_at"),
    }
    if file_type == "image":
        meta["ocr_text"] = parsed_result.get("ocr_text", "")
        meta["ocr_success"] = parsed_result.get("ocr_success")
        meta["image_width"] = parsed_result.get("image_width")
        meta["image_height"] = parsed_result.get("image_height")

    # 5.入库
    from datetime import datetime

    try:
        with get_session() as session:
            doc = UserDocument(
                user_id=user_id,
                file_name=parsed_result["file_name"],
                file_type=file_type,
                source_channel=parsed_result.get("source_channel", "file"),
                file_path=str(target_path),
                file_size=parsed_result.get("file_size"),
                status="active",
                meta=meta,
            )

            # 用 JSON 的 created_at
            if parsed_result.get("created_at"):
                try:
                    doc.created_at = datetime.fromisoformat(parsed_result["created_at"])
                except (ValueError, TypeError):
                    pass

            session.add(doc)
            session.flush()
            doc_id = doc.id
            doc_uuid = doc.doc_uuid

        logger.info(f"[3/3] 入库完成: doc_id={doc_id}, doc_uuid={doc_uuid[:8]}...")

    except Exception as e:
        logger.error(f"入库失败: {e}")
        return None

    # 6. 查询返回
    with get_session() as session:
        doc = session.query(UserDocument).filter_by(id=doc_id).first()

    if doc:
        logger.info(
            f"✅ 上传成功: {doc.file_name} → "
            f"doc_id={doc.id}, doc_uuid={doc.doc_uuid[:8]}..."
        )

    return doc

def upload_from_stream(
    file_obj,
    filename: str,
    user_id: int,
    title: Optional[str] = None,
) -> Optional[UserDocument]:
    """
    从文件流上传（FastAPI UploadFile 用）

    1. 落盘到临时文件
    2. 调 upload_file
    3. 删临时文件
    """
    import tempfile

    suffix = Path(filename).suffix
    tmp_path = None
    try:
        # 用原始文件名制作临时文件名，保留stem
        tmp_dir = Path(tempfile.mkdtemp())
        tmp_path = tmp_dir / filename
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        return upload_file(str(tmp_path), user_id=user_id, title=title)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()

# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 测试参数
    # ================================================
    SOURCE_PATH_A = "/mnt/e/英语/magazine/The Economist_20260926.pdf"
    SOURCE_PATH_B = "/mnt/e/英语/test_picture.png"
    USER_ID = 2
    # ================================================

    print("=" * 60)
    print("用户文件上传测试")
    print("=" * 60)
    print(f"源文件: {SOURCE_PATH_B}")
    print(f"用户 ID: {USER_ID}")
    print("=" * 60)

    doc = upload_file(SOURCE_PATH_B, user_id=USER_ID)

    print("\n" + "=" * 60)
    print("✅ 上传完成" if doc else "❌ 上传失败")
    print("=" * 60)

    if doc:
        print(f"doc_id: {doc.id}")
        print(f"doc_uuid: {doc.doc_uuid}")
        print(f"file_name: {doc.file_name}")
        print(f"file_path: {doc.file_path}")
        print(f"file_size: {doc.file_size}")
        print(f"created_at: {doc.created_at}")
        print(f"status: {doc.status}")