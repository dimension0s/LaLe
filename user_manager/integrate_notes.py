"""
integrate_notes.py - 整合笔记
路径: /home/bina/LaLe/user_manager/integrate_notes.py

职责:
1. 接收多条笔记 UUID
2. 从 PG 读笔记内容
3. 调用 DeepSeek 整合（去重 + 综合 + 保留关键信息）
4. 入库 integration 表
5. 更新原笔记 is_integrated = True

不负责:
- 添加笔记（由 generate_notes.py 负责）
- 查询笔记（由 search_notes.py 负责）
- 删除/恢复（由 recycle.py 负责）
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================
# 兼容直接运行
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
from loguru import logger

from user_manager.pg_data_manager.database import get_session
from user_manager.pg_data_manager.orm_models import (
    UserDocument,
    UserNote,
    Integration,
)


# ============================================================
# 配置：DeepSeek 模型
# ============================================================
import os
from dotenv import load_dotenv

# 加载 .env
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_TEMPERATURE = 0.2
DEEPSEEK_MAX_TOKENS = 4096
DEEPSEEK_TIMEOUT = 90


# ============================================================
# 提示词
# ============================================================
INTEGRATE_SYSTEM_PROMPT = "你是一位笔记整理专家，擅长将多份笔记整合成一份简洁、完整、无重复的笔记。"

INTEGRATE_PROMPT_TEMPLATE = """请整合以下多份笔记，生成一份统一的笔记。

【整合要求】
1. **去重**：删除重复的内容
2. **综合**：合并相似的内容，提炼共同点
3. **保留关键信息**：不丢失任何重要信息
4. **保持 markdown 格式**：结构清晰
5. **按模块组织**：如果涉及多个模块（翻译/语法/术语/词组），分模块展示
6. **不要添加原文没有的信息**

【笔记列表】
{notes}

【输出要求】
直接输出整合后的 markdown 笔记，不要添加任何解释性文字。

【整合结果】
"""


# ============================================================
# 主函数
# ============================================================
def integrate_notes(
    note_uuids: List[str],
    user_id: int,
) -> Optional[Integration]:
    """
    整合多份笔记

    Args:
        note_uuids: 要整合的笔记 UUID 列表（至少 2 条）
        user_id: 用户 ID

    Returns:
        Integration 或 None
    """
    # 1. 参数校验
    if not user_id:
        logger.error("❌ user_id 不能为空")
        return None

    if not note_uuids or len(note_uuids) < 2:
        logger.error(f"❌ 至少需要 2 条笔记才能整合，当前: {len(note_uuids)}")
        return None

    # 去重
    note_uuids = list(set(note_uuids))
    if len(note_uuids) < 2:
        logger.error("❌ 去重后不足 2 条笔记")
        return None

    logger.info("=" * 60)
    logger.info(f"整合笔记")
    logger.info(f"  user_id: {user_id}")
    logger.info(f"  note_uuids: {len(note_uuids)} 条")
    logger.info("=" * 60)

    # 2. 从 PG 读笔记（核心修改：包含已合并的整合体并拆包）
    final_note_uuids = set(note_uuids)

    with get_session() as session:
        # 先查一遍传入的 UUID，如果是整合体，把底层的笔记 UUID 也都加进来
        from user_manager.pg_data_manager.orm_models import Integration
        integs = session.query(Integration).filter(
            Integration.integration_uuid.in_(note_uuids),
            Integration.user_id == user_id,
            Integration.status == "active"
        ).all()

        for integ in integs:
            if integ.source_note_ids:
                final_note_uuids.update(integ.source_note_ids)

        # 然后再去查真正的笔记
        notes = session.query(UserNote).filter(
            UserNote.note_uuid.in_(list(final_note_uuids)),
            UserNote.user_id == user_id,
            UserNote.status == "active",
        ).all()

        if len(notes) < 2:
            logger.error(f"❌ 有效笔记数量不足 2 条（共找到 {len(notes)} 条）")
            return None

        # 校验：所有笔记属于同一文档
        document_ids = {n.document_id for n in notes}
        if len(document_ids) != 1:
            logger.error(f"❌ 笔记属于不同文档: {document_ids}")
            return None

        document_id = document_ids.pop()

        # 校验：文档存在且属于该用户
        doc = session.query(UserDocument).filter_by(
            id=document_id,
            user_id=user_id,
            status="active",
        ).first()
        if not doc:
            logger.error(f"❌ 文档不存在或不属于该用户: document_id={document_id}")
            return None

        # 收集源信息
        source_modules = list({n.note_type for n in notes})
        source_note_uuids = [n.note_uuid for n in notes]
        notes_content = [
            {
                "note_type": n.note_type,
                "content": n.content,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notes
        ]

    logger.info(f"  → 文档: {doc.file_name}")
    logger.info(f"  → 模块: {source_modules}")

    # 3. 构造提示词
    notes_text = _format_notes_for_prompt(notes_content)
    prompt = INTEGRATE_PROMPT_TEMPLATE.format(notes=notes_text)

    # 4. 调用 DeepSeek
    try:
        start_time = time.monotonic()
        integrated_content = _call_deepseek(prompt)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(f"  → DeepSeek 调用完成: {elapsed_ms}ms, {len(integrated_content)} 字符")
    except Exception as e:
        logger.error(f"❌ DeepSeek 调用失败: {e}")
        return None

    if not integrated_content or not integrated_content.strip():
        logger.error("❌ 整合结果为空")
        return None

    integrated_content = integrated_content.strip()

    # 5. 入库
    try:
        with get_session() as session:
            # 清理旧数据：如果这次合并的源笔记，之前已经在某个整合体里了，就把旧整合体删掉，防止出现多张历史卡片
            from user_manager.pg_data_manager.orm_models import Integration
            existing_integs = session.query(Integration).filter(
                Integration.user_id == user_id,
                Integration.status == "active",
            ).all()

            for old in existing_integs:
                if set(old.source_note_ids).issubset(set(final_note_uuids)):
                    session.delete(old)

            # 创建新的 Integration
            integ = Integration(
                user_id=user_id,
                document_id=document_id,
                source_modules=source_modules,
                source_note_ids=source_note_uuids,
                content=integrated_content,
                content_size=len(integrated_content.encode("utf-8")),
                status="active",
            )
            session.add(integ)
            session.flush()

            integ_id = integ.id
            integ_uuid = integ.integration_uuid

            # 更新原笔记 is_integrated = True
            session.query(UserNote).filter(
                UserNote.note_uuid.in_(source_note_uuids),
                UserNote.user_id == user_id,
            ).update(
                {"is_integrated": True},
                synchronize_session=False,
            )

        logger.info(
            f"✅ 整合完成: integration_uuid={integ_uuid[:8]}..., "
            f"id={integ_id}, "
            f"来源 {len(source_note_uuids)} 条笔记, "
            f"模块 {source_modules}"
        )

    except Exception as e:
        logger.error(f"❌ 入库失败: {e}")
        return None

    # 6. 返回
    with get_session() as session:
        return session.query(Integration).filter_by(id=integ_id).first()


# ============================================================
# 辅助函数
# ============================================================
def _format_notes_for_prompt(notes_content: List[Dict]) -> str:
    """格式化笔记内容用于提示词"""
    lines = []
    for i, note in enumerate(notes_content, 1):
        lines.append(f"### 笔记 {i}（{note['note_type']}）")
        lines.append(note["content"])
        lines.append("")
    return "\n".join(lines)


def _call_deepseek(prompt: str) -> str:
    """调用 DeepSeek 模型"""
    if not DEEPSEEK_API_KEY:
        raise ValueError("未设置 DEEPSEEK_API_KEY")

    try:
        response = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": INTEGRATE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": DEEPSEEK_TEMPERATURE,
                "max_tokens": DEEPSEEK_MAX_TOKENS,
            },
            timeout=DEEPSEEK_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content
    except requests.exceptions.Timeout:
        raise RuntimeError("DeepSeek 调用超时")
    except requests.exceptions.RequestException as e:
        logger.error(f"DeepSeek 请求失败: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"响应内容: {e.response.text}")
        raise


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 测试参数
    # ================================================
    USER_ID = 1
    NOTE_UUIDS = [
        # 至少 2 条，从数据库查
        # psql -U lale_user -d user_files -h localhost -c "SELECT note_uuid FROM user_notes WHERE user_id=1;"
        "db2c128e-a967-4776-9929-b226385429fc",
        "d75f2757-8ba4-460a-bd95-8c8079a34b7c",
        "a2161012-4955-4e29-a433-317cfbe4494f"
    ]
    # ================================================

    print("=" * 60)
    print("整合笔记测试")
    print("=" * 60)
    print(f"user_id: {USER_ID}")
    print(f"note_uuids: {len(NOTE_UUIDS)} 条")
    for uuid in NOTE_UUIDS:
        print(f"  - {uuid}")
    print("=" * 60)

    integ = integrate_notes(NOTE_UUIDS, USER_ID)

    print("\n" + "=" * 60)
    print("✅ 整合成功" if integ else "❌ 整合失败")
    print("=" * 60)

    if integ:
        print(f"integration_id: {integ.id}")
        print(f"integration_uuid: {integ.integration_uuid}")
        print(f"user_id: {integ.user_id}")
        print(f"document_id: {integ.document_id}")
        print(f"source_modules: {integ.source_modules}")
        print(f"source_note_ids: {len(integ.source_note_ids)} 条")
        print(f"content_size: {integ.content_size}")
        print(f"status: {integ.status}")
        print(f"created_at: {integ.created_at}")
        print(f"\n整合内容:\n{integ.content}")