"""
search_notes.py - 文件 + 笔记查询（合并 documents.py）
路径: /home/bina/LaLe/user_manager/search_notes.py
"""

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from user_manager.pg_data_manager.orm_models import UserVocabulary

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from user_manager.pg_data_manager.database import get_session
from user_manager.pg_data_manager.orm_models import (
    UserDocument, UserNote, Integration,
)

# ============================================================
# 配置
# ============================================================
NOTE_TYPES = ["translation", "grammar", "terminology", "phrase"]
NOTE_TYPE_LABELS = {
    "translation": "翻译",
    "grammar": "语法",
    "terminology": "术语",
    "phrase": "词组",
    "integration": "整合",
}


# ============================================================
# 1. 统一搜索
# ============================================================
def search(
        keyword: str,
        user_id: int,
        search_type: str = "all",
        limit: int = 20,
) -> Dict:
    """
    统一搜索（文件 + 笔记）

    Returns:
        {
            "files": [...],       # 文件列表（每个含 file_name）
            "notes": [...],       # 笔记列表（每个含 file_name）
            "total_files": ...,
            "total_notes": ...,
        }
    """
    if not keyword or not keyword.strip():
        return {"files": [], "notes": [], "total_files": 0, "total_notes": 0}

    keyword = keyword.strip()
    logger.info(f"搜索: keyword={keyword!r}, user_id={user_id}, type={search_type}")

    result = {
        "files": [],
        "notes": [],
        "total_files": 0,
        "total_notes": 0,
    }

    with get_session() as session:
        # 1. 搜索文件
        if search_type in ("file", "all"):
            files = session.query(UserDocument).filter(
                UserDocument.user_id == user_id,
                UserDocument.status == "active",
                UserDocument.file_name.ilike(f"%{keyword}%"),
            ).order_by(
                UserDocument.created_at.desc()
            ).limit(limit).all()

            result["files"] = [_doc_to_dict(f) for f in files]
            result["total_files"] = len(result["files"])

        # 2. 搜索笔记（JOIN 文件表，含 file_name）
        if search_type in ("note", "all"):
            rows = session.query(UserNote, UserDocument).join(
                UserDocument,
                UserNote.document_id == UserDocument.id,
            ).filter(
                UserNote.user_id == user_id,
                UserNote.status == "active",
                UserNote.content.ilike(f"%{keyword}%"),
            ).order_by(
                UserNote.created_at.desc()
            ).limit(limit).all()

            result["notes"] = [
                _note_to_dict(note, doc)
                for note, doc in rows
            ]
            result["total_notes"] = len(result["notes"])

    logger.info(
        f"搜索完成: 文件 {result['total_files']} 项, "
        f"笔记 {result['total_notes']} 项"
    )
    return result


# ============================================================
# 2. 文档查询
# ============================================================
def list_documents(
        user_id: int,
        include_deleted: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
) -> List[Dict]:
    """查看用户的文件列表"""
    with get_session() as session:
        query = session.query(UserDocument).filter_by(user_id=user_id)
        if not include_deleted:
            query = query.filter(UserDocument.status == "active")
        query = query.order_by(UserDocument.created_at.desc())
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        docs = query.all()
        result = [_doc_to_dict(doc) for doc in docs]

    logger.info(f"文档列表: user_id={user_id}, 返回 {len(result)} 项")
    return result


def get_document(doc_id: int, user_id: int) -> Optional[Dict]:
    """查看文档详情"""
    with get_session() as session:
        doc = session.query(UserDocument).filter_by(
            id=doc_id, user_id=user_id,
        ).first()
        return _doc_to_dict(doc) if doc else None


def get_document_by_uuid(doc_uuid: str, user_id: int) -> Optional[Dict]:
    """按 UUID 查看文档（路由用）"""
    with get_session() as session:
        doc = session.query(UserDocument).filter_by(
            doc_uuid=doc_uuid, user_id=user_id,
        ).first()
        return _doc_to_dict(doc) if doc else None


def count_documents(user_id: int, include_deleted: bool = False) -> int:
    """统计文档数量"""
    with get_session() as session:
        query = session.query(UserDocument).filter_by(user_id=user_id)
        if not include_deleted:
            query = query.filter(UserDocument.status == "active")
        return query.count()


# ============================================================
# 3. 笔记查询
# ============================================================
def list_notes_grouped(
        document_id: int,
        user_id: int,
        include_integration: bool = True,
) -> Dict:
    """
    按模块分组返回笔记（按日期聚合）

    Returns:
        {
            "document": {...},         # 当前文档信息
            "translation": [...],       # 翻译模块的日期分组
            "grammar": [...],
            "terminology": [...],
            "phrase": [...],
            "integration": [...],
        }
    """
    logger.info(f"笔记分组: document_id={document_id}, user_id={user_id}")

    result = {
        "document": None,
    }
    for note_type in NOTE_TYPES:
        result[note_type] = []

    with get_session() as session:
        # 1. 校验文档归属
        doc = session.query(UserDocument).filter_by(
            id=document_id,
            user_id=user_id,
            status="active",
        ).first()
        if not doc:
            logger.error(f"文档不存在或不属于该用户: document_id={document_id}")
            return result

        # 2. 加文档信息
        result["document"] = {
            "doc_id": doc.id,
            "doc_uuid": doc.doc_uuid,
            "file_name": doc.file_name,
            "file_type": doc.file_type,
        }

        # 3. 查询所有笔记（排除被整合的）
        notes = session.query(UserNote).filter(
            UserNote.document_id == document_id,
            UserNote.user_id == user_id,
            UserNote.status == "active",
            UserNote.is_integrated == False,
        ).order_by(
            UserNote.created_at.desc()
        ).all()

        # 4. 按模块 + 日期分组
        grouped = defaultdict(lambda: defaultdict(list))
        for note in notes:
            date_str = note.created_at.strftime("%Y-%m-%d")
            grouped[note.note_type][date_str].append(note.note_uuid)

        # 5. 转成列表格式
        for note_type, date_map in grouped.items():
            if note_type not in result:
                result[note_type] = []
            for date_str, uuids in sorted(date_map.items(), reverse=True):
                result[note_type].append({
                    "date": date_str,
                    "count": len(uuids),
                    "note_uuids": uuids,
                })

        # 6. 整合笔记
        if include_integration:
            integrations = session.query(Integration).filter(
                Integration.document_id == document_id,
                Integration.user_id == user_id,
                Integration.status == "active",
            ).order_by(
                Integration.created_at.desc()
            ).all()

            integration_grouped = defaultdict(list)
            for integ in integrations:
                date_str = integ.created_at.strftime("%Y-%m-%d")
                integration_grouped[date_str].append(integ.integration_uuid)

            result["integration"] = []
            for date_str, uuids in sorted(integration_grouped.items(), reverse=True):
                result["integration"].append({
                    "date": date_str,
                    "count": len(uuids),
                    "integration_uuids": uuids,
                })

    total = sum(len(v) for k, v in result.items() if k != "document")
    logger.info(f"笔记分组完成: {total} 个日期格子")
    return result


def list_notes_by_date(
        document_id: int,
        note_type: str,
        date: str,
        user_id: int,
) -> List[Dict]:
    """
    查看某日期某模块下的所有笔记（点击日期格子时）

    Returns:
        笔记列表（含 file_name）
    """
    try:
        start = datetime.strptime(date, "%Y-%m-%d")
        end = start + timedelta(days=1)
    except ValueError:
        logger.error(f"无效日期: {date!r}")
        return []

    with get_session() as session:
        # 查询文档（用于填充 file_name）
        doc = session.query(UserDocument).filter_by(
            id=document_id, user_id=user_id,
        ).first()

        notes = session.query(UserNote).filter(
            UserNote.document_id == document_id,
            UserNote.user_id == user_id,
            UserNote.note_type == note_type,
            UserNote.status == "active",
            UserNote.created_at >= start,
            UserNote.created_at < end,
        ).order_by(
            UserNote.created_at.desc()
        ).all()

        return [_note_to_dict(n, doc) for n in notes]


def get_note(note_id: int, user_id: int) -> Optional[Dict]:
    """查看笔记详情（含 file_name）"""
    with get_session() as session:
        row = session.query(UserNote, UserDocument).join(
            UserDocument,
            UserNote.document_id == UserDocument.id,
        ).filter(
            UserNote.id == note_id,
            UserNote.user_id == user_id,
        ).first()

        if not row:
            return None
        note, doc = row
        return _note_to_dict(note, doc)


def get_note_by_uuid(note_uuid: str, user_id: int) -> Optional[Dict]:
    """按 UUID 查看笔记（路由用，含 file_name）"""
    with get_session() as session:
        row = session.query(UserNote, UserDocument).join(
            UserDocument,
            UserNote.document_id == UserDocument.id,
        ).filter(
            UserNote.note_uuid == note_uuid,
            UserNote.user_id == user_id,
        ).first()

        if not row:
            return None
        note, doc = row
        return _note_to_dict(note, doc)


def count_notes(user_id: int, document_id: int = None) -> int:
    """统计笔记数量"""
    with get_session() as session:
        query = session.query(UserNote).filter(
            UserNote.user_id == user_id,
            UserNote.status == "active",
        )
        if document_id:
            query = query.filter(UserNote.document_id == document_id)
        return query.count()


# ============================================================
# 辅助函数
# ============================================================
def _doc_to_dict(doc: UserDocument) -> Dict:
    """UserDocument → Dict"""
    return {
        "doc_id": doc.id,
        "doc_uuid": doc.doc_uuid,
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "source_channel": doc.source_channel,
        "file_path": doc.file_path,
        "file_size": doc.file_size,
        "status": doc.status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def _note_to_dict(note: UserNote, doc: UserDocument = None) -> Dict:
    """UserNote → Dict（含文件信息）"""
    return {
        "note_id": note.id,
        "note_uuid": note.note_uuid,
        "user_id": note.user_id,
        "document_id": note.document_id,
        "file_name": doc.file_name if doc else None,  # ← 新增
        "note_type": note.note_type,
        "note_type_label": NOTE_TYPE_LABELS.get(note.note_type, note.note_type),
        "content": note.content,
        "content_size": note.content_size,
        "is_integrated": note.is_integrated,
        "status": note.status,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }

def _integration_to_dict(integ: Integration, doc: UserDocument = None) -> Dict:
    """Integration → Dict"""
    return {
        "integration_id": integ.id,
        "integration_uuid": integ.integration_uuid,
        "user_id": integ.user_id,
        "document_id": integ.document_id,
        "file_name": doc.file_name if doc else None,
        "source_modules": integ.source_modules or [],
        "source_note_ids": integ.source_note_ids or [],
        "content": integ.content,
        "content_size": integ.content_size,
        "status": integ.status,
        "created_at": integ.created_at.isoformat() if integ.created_at else None,
        "updated_at": integ.updated_at.isoformat() if integ.updated_at else None,
    }

def list_integrations(document_id: int, user_id: int) -> List[Dict]:
    """某文档下的整合列表"""
    with get_session() as session:
        doc = session.query(UserDocument).filter_by(
            id=document_id, user_id=user_id,
        ).first()
        integrations = session.query(Integration).filter(
            Integration.document_id == document_id,
            Integration.user_id == user_id,
            Integration.status == "active",
        ).order_by(Integration.created_at.desc()).all()
        return [_integration_to_dict(i, doc) for i in integrations]


def get_integration_by_uuid(integration_uuid: str, user_id: int) -> Optional[Dict]:
    """按 UUID 查整合详情"""
    with get_session() as session:
        row = session.query(Integration, UserDocument).join(
            UserDocument,
            Integration.document_id == UserDocument.id,
        ).filter(
            Integration.integration_uuid == integration_uuid,
            Integration.user_id == user_id,
        ).first()
        if not row:
            return None
        integ, doc = row
        return _integration_to_dict(integ, doc)

def count_notes(user_id: int) -> int:
    """统计活跃笔记数"""
    with get_session() as session:
        return session.query(UserNote).filter_by(
            user_id=user_id, status="active"
        ).count()

def count_vocabulary(user_id: int) -> int:
    """统计活跃生词数"""
    with get_session() as session:
        return session.query(UserVocabulary).filter_by(
            user_id=user_id, status="active"
        ).count()


def list_all_notes(user_id: int, limit: int = 100, offset: int = 0) -> Dict:
    """获取用户的所有活跃笔记（按时间倒序）"""
    from user_manager.pg_data_manager.orm_models import UserNote, UserDocument
    with get_session() as session:
        query = session.query(UserNote, UserDocument).join(
            UserDocument, UserNote.document_id == UserDocument.id
        ).filter(
            UserNote.user_id == user_id,
            UserNote.status == "active",
        ).order_by(
            UserNote.created_at.desc()
        )

        total = query.count()
        rows = query.offset(offset).limit(limit).all()

        items = [_note_to_dict(note, doc) for note, doc in rows]
        return {"items": items, "total": total}

# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    ACTION = "grouped"   # 可选项：grouped,search
    USER_ID = 1
    KEYWORD = "Economist"
    DOCUMENT_ID = 1
    NOTE_TYPE = "translation"
    DATE = "2026-10-15"
    NOTE_ID = 1

    print("=" * 60)
    print(f"查询: {ACTION}")
    print("=" * 60)

    if ACTION == "search":
        result = search(KEYWORD, USER_ID)
        print(f"\n文件: {result['total_files']} 项")
        for f in result["files"]:
            print(f"  [{f['doc_id']}] {f['file_name']}")
        print(f"\n笔记: {result['total_notes']} 项")
        for n in result["notes"]:
            print(
                f"  [{n['note_id']}] {n['note_type_label']} "
                f"({n['file_name']}) - {n['content'][:50]}..."
            )

    elif ACTION == "list_docs":
        docs = list_documents(USER_ID)
        print(f"共 {len(docs)} 项:")
        for doc in docs:
            print(f"  [{doc['doc_id']}] {doc['file_name']}")

    elif ACTION == "grouped":
        result = list_notes_grouped(DOCUMENT_ID, USER_ID)
        import json

        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif ACTION == "by_date":
        notes = list_notes_by_date(DOCUMENT_ID, NOTE_TYPE, DATE, USER_ID)
        print(f"共 {len(notes)} 条:")
        for n in notes:
            print(f"  [{n['note_id']}] ({n['file_name']}) {n['content'][:100]}...")

    elif ACTION == "get_note":
        note = get_note(NOTE_ID, USER_ID)
        if note:
            import json

            print(json.dumps(note, ensure_ascii=False, indent=2))
        else:
            print(f"笔记不存在: note_id={NOTE_ID}")

    else:
        print(f"未知操作: {ACTION}")