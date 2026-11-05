"""
vocabulary.py - 生词本业务层
路径: /home/bina/LaLe/user_manager/vocabulary.py

职责:
1. 加入生词本（word 归一化、唯一性检查）
2. 生词本列表（摘要）、详情（完整 word_info）
3. 删除（软删除进回收站，由 recycle.py 接管）
4. 检查单词是否已在生词本（供查词接口用）
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from user_manager.pg_data_manager.database import get_session
from user_manager.pg_data_manager.orm_models import UserVocabulary


# ============================================================
# 1. 加入生词本
# ============================================================
def add_vocabulary(
    user_id: int,
    word: str,
    word_info: Dict,
) -> Optional[UserVocabulary]:
    """
    加入生词本

    Args:
        user_id: 用户 ID
        word: 单词拼写（入库前 lower + strip）
        word_info: 单词详细信息（牛津词条 dict + 可选 source_context）

    Returns:
        UserVocabulary 或 None（已存在/参数非法）
    """
    if not user_id:
        logger.error("❌ user_id 不能为空")
        return None

    if not word or not word.strip():
        logger.error("❌ word 不能为空")
        return None

    word = word.strip().lower()

    if len(word) > 100:
        logger.error(f"❌ word 过长（最多 100 字符）: {word!r}")
        return None

    if not word_info or not isinstance(word_info, dict):
        logger.error("❌ word_info 必须是非空 dict")
        return None

    logger.info(f"加入生词本: user_id={user_id}, word={word!r}")

    with get_session() as session:
        # 查是否已在生词本
        existing = session.query(UserVocabulary).filter_by(
            user_id=user_id,
            word=word,
            status="active",
        ).first()

        if existing:
            logger.warning(f"⚠️ 单词已在生词本: {word!r} (vocab_uuid={existing.vocab_uuid[:8]}...)")
            return None

        vocab = UserVocabulary(
            user_id=user_id,
            word=word,
            word_info=word_info,
            status="active",
        )
        session.add(vocab)
        session.flush()

        vocab_id = vocab.id
        vocab_uuid = vocab.vocab_uuid

    logger.info(f"✅ 生词已入库: vocab_uuid={vocab_uuid[:8]}..., word={word!r}, id={vocab_id}")

    with get_session() as session:
        return session.query(UserVocabulary).filter_by(id=vocab_id).first()


# ============================================================
# 2. 检查单词是否已在生词本（供查词接口用）
# ============================================================
def is_in_vocabulary(user_id: int, word: str) -> bool:
    """检查单词是否已在生词本（只读，轻量 SELECT 1）"""
    if not user_id or not word:
        return False

    word = word.strip().lower()

    with get_session() as session:
        exists = session.query(UserVocabulary.id).filter_by(
            user_id=user_id,
            word=word,
            status="active",
        ).first()
        return exists is not None

def get_vocabulary_by_word(user_id: int, word: str) -> Optional[UserVocabulary]:
    """
    按单词查生词本记录（供 lookup 用）

    Returns:
        UserVocabulary 或 None
    """
    if not user_id or not word:
        return None

    word = word.strip().lower()

    with get_session() as session:
        return session.query(UserVocabulary).filter_by(
            user_id=user_id,
            word=word,
            status="active",
        ).first()


# ============================================================
# 3. 生词本列表（摘要）
# ============================================================
def list_vocabulary(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> Dict:
    """
    生词本列表（按创建时间倒序）

    Returns:
        {
            "items": [...],
            "total": int,
        }
    """
    with get_session() as session:
        query = session.query(UserVocabulary).filter_by(
            user_id=user_id,
            status="active",
        ).order_by(
            UserVocabulary.created_at.desc()
        )

        total = query.count()
        records = query.offset(offset).limit(limit).all()

        items = [_vocab_to_summary(v) for v in records]

    logger.info(f"生词本列表: user_id={user_id}, 返回 {len(items)}/{total} 项")
    return {"items": items, "total": total}


# ============================================================
# 4. 生词详情（完整 word_info）
# ============================================================
def get_vocabulary(vocab_uuid: str, user_id: int) -> Optional[Dict]:
    """生词详情（含完整 word_info）"""
    with get_session() as session:
        vocab = session.query(UserVocabulary).filter_by(
            vocab_uuid=vocab_uuid,
            user_id=user_id,
            status="active",
        ).first()

        if not vocab:
            return None

        return _vocab_to_dict(vocab)


# ============================================================
# 辅助函数
# ============================================================
def _vocab_to_summary(vocab: UserVocabulary) -> Dict:
    """列表摘要（不含完整 word_info）"""
    info = vocab.word_info or {}
    senses = info.get("senses") or []
    first_meaning = ""
    if senses:
        first_meaning = senses[0].get("translation") or senses[0].get("definition") or ""

    return {
        "vocab_uuid": vocab.vocab_uuid,
        "word": vocab.word,
        "phonetic_uk": info.get("phonetic_uk") or info.get("phonetic") or "",
        "phonetic_us": info.get("phonetic_us") or "",
        "pos": info.get("pos") or [],
        "first_meaning": first_meaning,
        "created_at": vocab.created_at.isoformat() if vocab.created_at else None,
    }


def _vocab_to_dict(vocab: UserVocabulary) -> Dict:
    """详情（完整 word_info）"""
    return {
        "vocab_uuid": vocab.vocab_uuid,
        "user_id": vocab.user_id,
        "word": vocab.word,
        "word_info": vocab.word_info or {},
        "status": vocab.status,
        "created_at": vocab.created_at.isoformat() if vocab.created_at else None,
        "updated_at": vocab.updated_at.isoformat() if vocab.updated_at else None,
    }