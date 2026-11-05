"""
recycle.py - 回收站管理（支持文档 + 笔记 + 整合）
路径: /home/bina/LaLe/user_manager/recycle.py

职责:
1. 删除（软删除，放入回收站）
2. 恢复
3. 清理过期（物理删除）
4. 查看回收站列表

支持类型:
- user_document: 用户文档
- user_note: 用户笔记
- integration: 整合笔记
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from user_manager.pg_data_manager.orm_models import (
    UserDocument,
    UserNote,
    Integration,
    RecycleBin,
    UserVocabulary,
)

# 兼容直接运行
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from user_manager.pg_data_manager.database import get_session
from user_manager.pg_data_manager.orm_models import (
    UserDocument,
    UserNote,
    Integration,
    RecycleBin,
)


# ============================================================
# 配置
# ============================================================
RECYCLE_BIN_DAYS = 15


# ============================================================
# 通用：删除
# ============================================================
def _add_to_recycle_bin(
    session,
    user_id: int,
    file_type: str,
    file_id: int,
) -> RecycleBin:
    """添加到回收站"""
    deleted_at = datetime.now()
    expires_at = deleted_at + timedelta(days=RECYCLE_BIN_DAYS)

    record = RecycleBin(
        user_id=user_id,
        file_type=file_type,
        file_id=file_id,
        deleted_at=deleted_at,
        expires_at=expires_at,
    )
    session.add(record)
    return record


def _restore_from_recycle_bin(
    session,
    user_id: int,
    file_type: str,
    file_id: int,
) -> bool:
    """从回收站移除记录"""
    result = session.query(RecycleBin).filter_by(
        user_id=user_id,
        file_type=file_type,
        file_id=file_id,
    ).delete()
    return result > 0


# ============================================================
# 1. 删除文档
# ============================================================
def delete_document(doc_id: int, user_id: int) -> bool:
    """删除文档（软删除）"""
    logger.info(f"删除文档: doc_id={doc_id}, user_id={user_id}")

    with get_session() as session:
        doc = session.query(UserDocument).filter_by(
            id=doc_id,
            user_id=user_id,
        ).first()

        if not doc:
            logger.error(f"文档不存在: doc_id={doc_id}, user_id={user_id}")
            return False

        if doc.status == "deleted":
            logger.warning(f"文档已在回收站: doc_id={doc_id}")
            return False

        # 检查是否已有回收站记录
        existing = session.query(RecycleBin).filter_by(
            user_id=user_id,
            file_type="user_document",
            file_id=doc_id,
        ).first()
        if existing:
            logger.warning(f"文档已在回收站: doc_id={doc_id}")
            return False

        # 更新 status
        doc.status = "deleted"
        doc.updated_at = datetime.now()

        # 添加回收站记录
        record = _add_to_recycle_bin(session, user_id, "user_document", doc_id)

        logger.info(
            f"✅ 文档已删除: {doc.file_name} → "
            f"回收站（保留至 {record.expires_at.strftime('%Y-%m-%d %H:%M:%S')}）"
        )

    return True


# ============================================================
# 2. 删除笔记
# ============================================================
def delete_note(note_uuid: str, user_id: int) -> bool:
    """删除笔记（软删除）"""
    logger.info(f"删除笔记: note_uuid={note_uuid[:8]}..., user_id={user_id}")

    with get_session() as session:
        note = session.query(UserNote).filter_by(
            note_uuid=note_uuid,
            user_id=user_id,
        ).first()

        if not note:
            logger.error(f"笔记不存在: note_uuid={note_uuid}")
            return False

        if note.status == "deleted":
            logger.warning(f"笔记已在回收站: note_uuid={note_uuid[:8]}...")
            return False

        # 检查是否已有回收站记录
        existing = session.query(RecycleBin).filter_by(
            user_id=user_id,
            file_type="user_note",
            file_id=note.id,
        ).first()
        if existing:
            logger.warning(f"笔记已在回收站: note_uuid={note_uuid[:8]}...")
            return False

        # 更新 status
        note.status = "deleted"
        note.updated_at = datetime.now()

        # 添加回收站记录
        record = _add_to_recycle_bin(session, user_id, "user_note", note.id)

        logger.info(
            f"✅ 笔记已删除: note_uuid={note_uuid[:8]}... → "
            f"回收站（保留至 {record.expires_at.strftime('%Y-%m-%d %H:%M:%S')}）"
        )

    return True


# ============================================================
# 3. 删除整合笔记
# ============================================================
def delete_integration(integration_uuid: str, user_id: int) -> bool:
    """删除整合笔记（软删除）"""
    logger.info(f"删除整合: integration_uuid={integration_uuid[:8]}..., user_id={user_id}")

    with get_session() as session:
        integ = session.query(Integration).filter_by(
            integration_uuid=integration_uuid,
            user_id=user_id,
        ).first()

        if not integ:
            logger.error(f"整合不存在: integration_uuid={integration_uuid}")
            return False

        if integ.status == "deleted":
            logger.warning(f"整合已在回收站: {integration_uuid[:8]}...")
            return False

        # 检查是否已有回收站记录
        existing = session.query(RecycleBin).filter_by(
            user_id=user_id,
            file_type="integration",
            file_id=integ.id,
        ).first()
        if existing:
            logger.warning(f"整合已在回收站: {integration_uuid[:8]}...")
            return False

        # 更新 status
        integ.status = "deleted"
        integ.updated_at = datetime.now()

        # **恢复原笔记的"未整合"状态**
        source_note_ids = integ.source_note_ids or []
        if source_note_ids:
            session.query(UserNote).filter(
                UserNote.note_uuid.in_(source_note_ids),
                UserNote.user_id == user_id,
            ).update(
                {"is_integrated": False, "updated_at": datetime.now()},
                synchronize_session=False,
            )
            logger.info(f"  → 恢复 {len(source_note_ids)} 条原笔记的未整合状态")

        # 添加回收站记录
        record = _add_to_recycle_bin(session, user_id, "integration", integ.id)

        logger.info(
            f"✅ 整合已删除: {integration_uuid[:8]}... → "
            f"回收站（保留至 {record.expires_at.strftime('%Y-%m-%d %H:%M:%S')}）"
        )

    return True

# ============================================================
# 3.5 删除生词
# ============================================================
def delete_vocabulary(vocab_uuid: str, user_id: int) -> bool:
    """删除生词（软删除）"""
    logger.info(f"删除生词: vocab_uuid={vocab_uuid[:8]}..., user_id={user_id}")

    with get_session() as session:
        vocab = session.query(UserVocabulary).filter_by(
            vocab_uuid=vocab_uuid,
            user_id=user_id,
        ).first()

        if not vocab:
            logger.error(f"生词不存在: vocab_uuid={vocab_uuid}")
            return False

        if vocab.status == "deleted":
            logger.warning(f"生词已在回收站: {vocab_uuid[:8]}...")
            return False

        existing = session.query(RecycleBin).filter_by(
            user_id=user_id,
            file_type="user_vocabulary",
            file_id=vocab.id,
        ).first()
        if existing:
            logger.warning(f"生词已在回收站: {vocab_uuid[:8]}...")
            return False

        vocab.status = "deleted"
        vocab.updated_at = datetime.now()

        record = _add_to_recycle_bin(session, user_id, "user_vocabulary", vocab.id)

        logger.info(
            f"✅ 生词已删除: {vocab_uuid[:8]}... → "
            f"回收站（保留至 {record.expires_at.strftime('%Y-%m-%d %H:%M:%S')}）"
        )

    return True


# ============================================================
# 6.5 恢复生词
# ============================================================
def restore_vocabulary(vocab_uuid: str, user_id: int) -> bool:
    """恢复生词"""
    logger.info(f"恢复生词: vocab_uuid={vocab_uuid[:8]}..., user_id={user_id}")

    with get_session() as session:
        # 兼容数字 ID 和 UUID 两种形式
        if str(vocab_uuid).isdigit():
            vocab = session.query(UserVocabulary).filter_by(
                id=int(vocab_uuid),
                user_id=user_id,
            ).first()
        else:
            vocab = session.query(UserVocabulary).filter_by(
                vocab_uuid=str(vocab_uuid),
                user_id=user_id,
            ).first()

        if not vocab:
            logger.error(f"生词不存在: vocab_uuid={vocab_uuid}")
            return False

        if vocab.status != "deleted":
            logger.warning(f"生词不在回收站: {vocab_uuid[:8]}...")
            return False

        # 检查恢复后是否会与现有 active 记录冲突（部分唯一索引）
        conflict = session.query(UserVocabulary).filter_by(
            user_id=user_id,
            word=vocab.word,
            status="active",
        ).first()
        if conflict:
            logger.error(
                f"❌ 恢复失败：生词本中已有 active 的 {vocab.word!r} "
                f"(vocab_uuid={conflict.vocab_uuid[:8]}...)"
            )
            return False

        vocab.status = "active"
        vocab.updated_at = datetime.now()

        _restore_from_recycle_bin(session, user_id, "user_vocabulary", vocab.id)

        logger.info(f"✅ 生词已恢复: {vocab_uuid[:8]}...")

    return True


# ============================================================
# 4. 恢复文档
# ============================================================
def restore_document(doc_id: str, user_id: int) -> bool:
    """恢复文档（兼容数字 ID 和 UUID）"""
    logger.info(f"收到恢复文档请求: doc_id={doc_id}, user_id={user_id}")
    with get_session() as session:
        if str(doc_id).isdigit():
            doc = session.query(UserDocument).filter_by(id=int(doc_id), user_id=user_id).first()
        else:
            doc = session.query(UserDocument).filter_by(doc_uuid=str(doc_id), user_id=user_id).first()

        if not doc:
            return False
        if doc.status != "deleted":
            return False

        doc.status = "active"
        doc.updated_at = datetime.now()
        _restore_from_recycle_bin(session, user_id, "user_document", doc.id)
    return True


# ============================================================
# 5. 恢复笔记
# ============================================================
def restore_note(note_uuid: str, user_id: int) -> bool:
    """恢复笔记（兼容数字 ID 和 UUID）"""
    with get_session() as session:
        if str(note_uuid).isdigit():
            note = session.query(UserNote).filter_by(id=int(note_uuid), user_id=user_id).first()
        else:
            note = session.query(UserNote).filter_by(note_uuid=str(note_uuid), user_id=user_id).first()

        if not note:
            return False
        if note.status != "deleted":
            return False

        note.status = "active"
        note.updated_at = datetime.now()
        _restore_from_recycle_bin(session, user_id, "user_note", note.id)
    return True


# ============================================================
# 6. 恢复整合
# ============================================================
def restore_integration(integration_uuid: str, user_id: int) -> bool:
    """恢复整合笔记（兼容数字 ID 和 UUID）"""
    # 👇 兼容数字 ID：如果是纯数字，就不截取前8位
    log_id = integration_uuid[:8] if not str(integration_uuid).isdigit() else integration_uuid
    logger.info(f"恢复整合: integration_uuid={log_id}..., user_id={user_id}")

    with get_session() as session:
        # 👇 核心修改：判断传入的是数字还是 UUID
        if str(integration_uuid).isdigit():
            # 如果全是数字，按主键 ID 查询
            integ = session.query(Integration).filter_by(
                id=int(integration_uuid),
                user_id=user_id,
            ).first()
        else:
            # 如果不是纯数字，按 UUID 查询
            integ = session.query(Integration).filter_by(
                integration_uuid=str(integration_uuid),
                user_id=user_id,
            ).first()

        if not integ:
            logger.error(f"整合不存在: integration_uuid={integration_uuid}")
            return False

        if integ.status != "deleted":
            logger.warning(f"整合不在回收站: {log_id}...")
            return False

        # 更新 status
        integ.status = "active"
        integ.updated_at = datetime.now()

        # **恢复原笔记的"已整合"状态**
        source_note_ids = integ.source_note_ids or []
        if source_note_ids:
            session.query(UserNote).filter(
                UserNote.note_uuid.in_(source_note_ids),
                UserNote.user_id == user_id,
            ).update(
                {"is_integrated": True, "updated_at": datetime.now()},
                synchronize_session=False,
            )
            logger.info(f"  → 恢复 {len(source_note_ids)} 条原笔记的已整合状态")

        # 从回收站移除
        _restore_from_recycle_bin(session, user_id, "integration", integ.id)

        logger.info(f"✅ 整合已恢复: {log_id}...")

    return True


# ============================================================
# 7. 清理过期（物理删除）
# ============================================================
def cleanup_expired() -> Dict[str, int]:
    """
    清理过期（物理删除）

    对每条过期记录：
        1. 删除文件（如果是文档）
        2. 删除数据库记录
        3. 删除回收站记录
    """
    now = datetime.now()
    stats = {"total": 0, "deleted": 0, "failed": 0}

    logger.info(f"开始清理过期（当前时间: {now}）")

    with get_session() as session:
        expired_records = session.query(RecycleBin).filter(
            RecycleBin.expires_at < now
        ).all()

        stats["total"] = len(expired_records)

        if not expired_records:
            logger.info("没有过期记录")
            return stats

        logger.info(f"发现 {len(expired_records)} 个过期记录")

        for record in expired_records:
            try:
                if record.file_type == "user_document":
                    _cleanup_user_document(session, record)
                elif record.file_type == "user_note":
                    _cleanup_user_note(session, record)
                elif record.file_type == "integration":
                    _cleanup_integration(session, record)
                elif record.file_type == "user_vocabulary":
                    _cleanup_user_vocabulary(session, record)
                else:
                    logger.warning(f"未知类型: {record.file_type}")
                    session.delete(record)
                stats["deleted"] += 1
            except Exception as e:
                logger.error(
                    f"清理失败: file_type={record.file_type}, "
                    f"file_id={record.file_id} - {e}"
                )
                stats["failed"] += 1

        logger.info(
            f"✅ 清理完成: 总数 {stats['total']}, "
            f"成功 {stats['deleted']}, 失败 {stats['failed']}"
        )

    return stats


def _cleanup_user_document(session, record: RecycleBin):
    """清理单个文档"""
    doc = session.query(UserDocument).filter_by(id=record.file_id).first()
    if not doc:
        logger.warning(f"文档不存在: doc_id={record.file_id}")
        session.delete(record)
        return

    # 删除文件
    file_path = Path(doc.file_path)
    if file_path.exists():
        try:
            file_path.unlink()
            logger.info(f"  文件已删除: {file_path}")
        except Exception as e:
            logger.warning(f"  文件删除失败: {file_path} - {e}")

    # 删除 user_documents 记录
    session.delete(doc)
    # 删除 recycle_bin 记录
    session.delete(record)

    logger.info(f"  ✅ 彻底删除文档: {doc.file_name}")


def _cleanup_user_note(session, record: RecycleBin):
    """清理单个笔记"""
    note = session.query(UserNote).filter_by(id=record.file_id).first()
    if not note:
        logger.warning(f"笔记不存在: note_id={record.file_id}")
        session.delete(record)
        return

    session.delete(note)
    session.delete(record)

    logger.info(f"  ✅ 彻底删除笔记: {note.note_uuid[:8]}...")


def _cleanup_integration(session, record: RecycleBin):
    """清理单个整合"""
    integ = session.query(Integration).filter_by(id=record.file_id).first()
    if not integ:
        logger.warning(f"整合不存在: integration_id={record.file_id}")
        session.delete(record)
        return

    session.delete(integ)
    session.delete(record)

    logger.info(f"  ✅ 彻底删除整合: {integ.integration_uuid[:8]}...")

def _cleanup_user_vocabulary(session, record: RecycleBin):
    """清理单个生词（无文件，只删数据库记录）"""
    vocab = session.query(UserVocabulary).filter_by(id=record.file_id).first()
    if not vocab:
        logger.warning(f"生词不存在: vocab_id={record.file_id}")
        session.delete(record)
        return

    session.delete(vocab)
    session.delete(record)

    logger.info(f"  ✅ 彻底删除生词: {vocab.word!r}")


# ============================================================
# 8. 查看回收站
# ============================================================
def list_recycle_bin(user_id: int) -> List[Dict]:
    """查看回收站列表"""
    now = datetime.now()
    result = []

    with get_session() as session:
        records = session.query(RecycleBin).filter(
            RecycleBin.user_id == user_id,
        ).order_by(
            RecycleBin.deleted_at.desc()
        ).all()

        for record in records:
            days_left = (record.expires_at - now).days

            # 查询实际信息
            file_name = ""
            file_type_label = ""
            preview_text = ""

            if record.file_type == "user_document":
                doc = session.query(UserDocument).filter_by(id=record.file_id).first()
                if doc:
                    file_name = doc.file_name
                    file_type_label = "文档"
                    # 从 meta 中提取 OCR 预览
                    if doc.meta and isinstance(doc.meta, dict):
                        ocr_text = doc.meta.get("ocr_text", "")
                        preview_text = ocr_text[:500] if ocr_text else "暂不支持文本预览"
            elif record.file_type == "user_note":
                note = session.query(UserNote).filter_by(id=record.file_id).first()
                if note:
                    file_name = f"[{note.note_type}] {note.note_uuid[:8]}..."
                    file_type_label = "笔记"
                    preview_text = note.content[:500]  # 笔记直接截取前500字
            elif record.file_type == "integration":
                integ = session.query(Integration).filter_by(id=record.file_id).first()
                if integ:
                    file_name = f"[整合] {integ.integration_uuid[:8]}..."
                    file_type_label = "整合"
                    preview_text = integ.content[:500]
            elif record.file_type == "user_vocabulary":
                vocab = session.query(UserVocabulary).filter_by(id=record.file_id).first()
                if vocab:
                    file_name = vocab.word
                    file_type_label = "生词"
                    preview_text = vocab.word_info

            result.append({
                "recycle_id": record.id,
                "file_type": record.file_type,
                "file_type_label": file_type_label,
                "file_id": record.file_id,
                "file_name": file_name,
                "preview_text": preview_text,
                "deleted_at": record.deleted_at.isoformat(),
                "expires_at": record.expires_at.isoformat(),
                "days_left": max(days_left, 0),
            })

    logger.info(f"回收站列表: user_id={user_id}, {len(result)} 项")
    return result

def permanent_delete(file_type: str, file_id: int) -> bool:
    """彻底物理删除（从数据库移除）"""
    with get_session() as session:
        if file_type == "user_document":
            obj = session.query(UserDocument).filter_by(id=file_id).first()
        elif file_type == "user_note":
            obj = session.query(UserNote).filter_by(id=file_id).first()
        elif file_type == "integration":
            obj = session.query(Integration).filter_by(id=file_id).first()
        elif file_type == "user_vocabulary":
            obj = session.query(UserVocabulary).filter_by(id=file_id).first()
        else:
            return False

        if obj:
            session.delete(obj)
            # 同时删掉回收站的关联记录
            session.query(RecycleBin).filter_by(
                file_type=file_type, file_id=file_id
            ).delete()
            return True
    return False

def cancel_integration(integration_uuid: str, user_id: int) -> bool:
    """取消合并（物理删除整合记录，并恢复原笔记状态）"""
    with get_session() as session:
        integ = session.query(Integration).filter_by(
            integration_uuid=integration_uuid, user_id=user_id, status="active"
        ).first()

        if not integ:
            return False

        # 恢复原笔记的 is_integrated 状态
        source_note_ids = integ.source_note_ids or []
        if source_note_ids:
            session.query(UserNote).filter(
                UserNote.note_uuid.in_(source_note_ids),
                UserNote.user_id == user_id,
            ).update({"is_integrated": False, "updated_at": datetime.now()}, synchronize_session=False)

        # 物理删除整合记录
        session.delete(integ)
        logger.info(f"✅ 已取消合并: {integration_uuid[:8]}...")
    return True

# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    ACTION = "restore_note"       # "list" / "cleanup" / "delete_doc" / "delete_note" / "restore_doc" / "restore_note"
    USER_ID = 1
    DOC_ID = 1
    NOTE_UUID = "db2c128e-a967-4776-9929-b226385429fc"
    INTEGRATION_UUID = ""

    print("=" * 60)
    print(f"回收站操作: {ACTION}")
    print("=" * 60)

    if ACTION == "list":
        items = list_recycle_bin(USER_ID)
        print(f"回收站共 {len(items)} 项:")
        for item in items:
            print(
                f"  [{item['file_type_label']}] {item['file_name']} "
                f"(剩 {item['days_left']} 天)"
            )

    elif ACTION == "cleanup":
        stats = cleanup_expired()
        print(f"清理统计: {stats}")

    elif ACTION == "delete_doc":
        print(f"结果: {delete_document(DOC_ID, USER_ID)}")

    elif ACTION == "delete_note":
        print(f"结果: {delete_note(NOTE_UUID, USER_ID)}")

    elif ACTION == "delete_integration":
        print(f"结果: {delete_integration(INTEGRATION_UUID, USER_ID)}")

    elif ACTION == "restore_doc":
        print(f"结果: {restore_document(DOC_ID, USER_ID)}")

    elif ACTION == "restore_note":
        print(f"结果: {restore_note(NOTE_UUID, USER_ID)}")

    elif ACTION == "restore_integration":
        print(f"结果: {restore_integration(INTEGRATION_UUID, USER_ID)}")

    else:
        print(f"未知操作: {ACTION}")


