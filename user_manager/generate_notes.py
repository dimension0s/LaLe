"""
generate_notes.py - 生成笔记
路径: /home/bina/LaLe/user_manager/generate_notes.py

职责:
- 添加笔记（对应前端的"加入笔记"）
- 校验 user_id + document_id 归属
- 入库 user_notes

不负责:
- 笔记查询（由 search_notes.py 负责）
- 笔记整合（由 integrate_notes.py 负责）
- 删除/恢复（由 recycle.py 负责）
"""

import sys
from pathlib import Path
from typing import Optional

# ============================================================
# 兼容直接运行：把项目根加入 sys.path
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from user_manager.pg_data_manager.database import get_session
from user_manager.pg_data_manager.orm_models import (
    UserDocument,
    UserNote,
)

# ============================================================
# 支持的笔记类型
# ============================================================
VALID_NOTE_TYPES = {
    "translation",  # 翻译
    "grammar",  # 语法
    "terminology",  # 术语
    "phrase",  # 词组/搭配
}


# ============================================================
# 添加笔记（唯一对外接口）
# ============================================================
def add_note(
        document_id: int,
        note_type: str,
        content: str,
        user_id: int,
) -> Optional[UserNote]:
    """
    添加笔记（入库）

    Args:
        document_id: 所属文档 ID
        note_type: 笔记类型（translation / grammar / terminology / phrase）
        content: markdown 内容
        user_id: 用户 ID（必传，确保数据隔离）

    Returns:
        UserNote 或 None（失败）
    """
    # 1. 参数校验
    if not user_id:
        logger.error("❌ user_id 不能为空")
        return None

    if not document_id:
        logger.error("❌ document_id 不能为空")
        return None

    if not note_type or note_type not in VALID_NOTE_TYPES:
        logger.error(
            f"❌ 无效的 note_type: {note_type!r}，"
            f"支持: {VALID_NOTE_TYPES}"
        )
        return None

    if not content or not content.strip():
        logger.error("❌ content 不能为空")
        return None

    content = content.strip()

    logger.info("=" * 60)
    logger.info(f"添加笔记")
    logger.info(f"  user_id: {user_id}")
    logger.info(f"  document_id: {document_id}")
    logger.info(f"  note_type: {note_type}")
    logger.info(f"  content_size: {len(content.encode('utf-8'))} 字节")
    logger.info("=" * 60)

    # 2. 校验 document 归属
    with get_session() as session:
        doc = session.query(UserDocument).filter_by(
            id=document_id,
            user_id=user_id,  # ← 关键：校验归属
            status="active",  # ← 只允许对活跃文档添加笔记
        ).first()

        if not doc:
            logger.error(
                f"❌ 文档不存在或不属于该用户: "
                f"document_id={document_id}, user_id={user_id}"
            )
            return None

        logger.info(f"  → 校验通过: 文档 {doc.file_name!r}")

        # 3. 构造笔记
        note = UserNote(
            user_id=user_id,
            document_id=document_id,
            note_type=note_type,
            content=content,
            content_size=len(content.encode("utf-8")),
            is_integrated=False,
            status="active",
        )
        session.add(note)
        session.flush()

        note_id = note.id
        note_uuid = note.note_uuid

    logger.info(
        f"✅ 笔记已入库: note_uuid={note_uuid[:8]}..., "
        f"user_id={user_id}, document_id={document_id}, "
        f"type={note_type}, note_id={note_id}"
    )

    # 4. 返回
    with get_session() as session:
        return session.query(UserNote).filter_by(id=note_id).first()

def update_note_content(note_uuid: str, user_id: int, content: str) -> bool:
    """更新笔记内容"""
    if not content or not content.strip():
        logger.error("❌ 笔记内容不能为空")
        return False

    content = content.strip()
    with get_session() as session:
        note = session.query(UserNote).filter_by(
            note_uuid=note_uuid, user_id=user_id, status="active"
        ).first()

        if not note:
            return False

        note.content = content
        note.content_size = len(content.encode("utf-8"))
        logger.info(f"✅ 笔记已更新: note_uuid={note_uuid[:8]}...")
    return True


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 测试参数
    # ================================================
    USER_ID = 1
    DOCUMENT_ID = 1
    NOTE_TYPE = "translation"

    # 测试内容（模拟功能模块的产出）
    CONTENT = """## 翻译

**原文**：The president has used tariffs to usurp Congress's taxing powers.

**译文**：总统利用关税篡夺了国会的征税权。
"""
    # ================================================

    print("=" * 60)
    print("添加笔记测试")
    print("=" * 60)
    print(f"user_id: {USER_ID}")
    print(f"document_id: {DOCUMENT_ID}")
    print(f"note_type: {NOTE_TYPE}")
    print("=" * 60)

    note = add_note(
        document_id=DOCUMENT_ID,
        note_type=NOTE_TYPE,
        content=CONTENT,
        user_id=USER_ID,
    )

    print("\n" + "=" * 60)
    print("✅ 添加成功" if note else "❌ 添加失败")
    print("=" * 60)

    if note:
        print(f"note_id: {note.id}")
        print(f"note_uuid: {note.note_uuid}")
        print(f"user_id: {note.user_id}")
        print(f"document_id: {note.document_id}")
        print(f"note_type: {note.note_type}")
        print(f"content_size: {note.content_size}")
        print(f"is_integrated: {note.is_integrated}")
        print(f"status: {note.status}")
        print(f"created_at: {note.created_at}")