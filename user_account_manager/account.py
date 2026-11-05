"""
account.py - 用户账号管理
路径: /home/bina/LaLe/user_account_manager/account.py

职责:
1. 查看账号信息
2. 修改昵称/头像
3. 绑定邮箱/微信
4. 注销账户（物理删除 + 文件清理）

不负责:
- 登录/登出（由 auth.py 负责）
- 数据管理（由 user_manager 负责）
"""

import shutil
import sys
from pathlib import Path
from typing import Dict, Optional
import random
import time
import os
import yagmail
from dotenv import load_dotenv

load_dotenv()
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# { email: {"code": "123456", "expires": 1690000000} }
EMAIL_CODE_CACHE = {}
# ============================================================
# 兼容直接运行
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from user_account_manager.pg_data_manager.database import get_session
from user_account_manager.pg_data_manager.orm_models import UserAccount

# 子表模型来自 user_manager（同库、不同 Base，但同一 engine）
from user_manager.pg_data_manager.orm_models import (
    UserDocument, UserNote, Integration, RecycleBin,
)


# ============================================================
# 配置
# ============================================================
USER_UPLOAD_DIR = PROJECT_ROOT / "data" / "user_uploads"


# ============================================================
# 1. 查看账号
# ============================================================
def get_account(user_id: int) -> Optional[Dict]:
    """查看账号信息（仅 active）"""
    with get_session() as session:
        user = session.query(UserAccount).filter_by(
            id=user_id,
            status="active",
        ).first()
        if not user:
            return None
        return _user_to_dict(user)


# ============================================================
# 2. 修改昵称
# ============================================================
def update_nickname(user_id: int, nickname: str) -> bool:
    """修改昵称"""
    if not nickname or not nickname.strip():
        logger.error("❌ 昵称不能为空")
        return False

    nickname = nickname.strip()
    if len(nickname) > 100:
        logger.error("❌ 昵称过长（最多 100 字符）")
        return False

    with get_session() as session:
        user = session.query(UserAccount).filter_by(
            id=user_id, status="active",
        ).first()
        if not user:
            logger.error(f"用户不存在: user_id={user_id}")
            return False

        user.nickname = nickname
        logger.info(f"✅ 昵称已修改: user_id={user_id}, nickname={nickname!r}")
    return True


# ============================================================
# 3. 修改头像
# ============================================================
def update_avatar(user_id: int, avatar_url: str) -> bool:
    """修改头像"""
    if not avatar_url or not avatar_url.strip():
        logger.error("❌ 头像 URL 不能为空")
        return False

    avatar_url = avatar_url.strip()

    with get_session() as session:
        user = session.query(UserAccount).filter_by(
            id=user_id, status="active",
        ).first()
        if not user:
            logger.error(f"用户不存在: user_id={user_id}")
            return False

        user.avatar_url = avatar_url
        logger.info(f"✅ 头像已修改: user_id={user_id}")
    return True


# ============================================================
# 4. 绑定邮箱
# ============================================================
def bind_email(user_id: int, email: str) -> bool:
    """绑定邮箱（应用层保证唯一，因 DB 无 unique 约束）"""
    if not email or not email.strip():
        logger.error("❌ 邮箱不能为空")
        return False

    email = email.strip()
    if "@" not in email or "." not in email:
        logger.error(f"❌ 邮箱格式错误: {email!r}")
        return False

    with get_session() as session:
        user = session.query(UserAccount).filter_by(
            id=user_id, status="active",
        ).first()
        if not user:
            logger.error(f"用户不存在: user_id={user_id}")
            return False

        occupied = session.query(UserAccount).filter(
            UserAccount.email == email,
            UserAccount.id != user_id,
        ).first()
        if occupied:
            logger.error(f"❌ 邮箱已被占用: {email!r} (user_id={occupied.id})")
            return False

        user.email = email
        logger.info(f"✅ 邮箱已绑定: user_id={user_id}, email={email!r}")
    return True


# ============================================================
# 5. 绑定微信
# ============================================================
def bind_wechat(user_id: int, wechat_openid: str) -> bool:
    """绑定微信（应用层保证唯一）"""
    if not wechat_openid or not wechat_openid.strip():
        logger.error("❌ 微信 OpenID 不能为空")
        return False

    wechat_openid = wechat_openid.strip()

    with get_session() as session:
        user = session.query(UserAccount).filter_by(
            id=user_id, status="active",
        ).first()
        if not user:
            logger.error(f"用户不存在: user_id={user_id}")
            return False

        occupied = session.query(UserAccount).filter(
            UserAccount.wechat_openid == wechat_openid,
            UserAccount.id != user_id,
        ).first()
        if occupied:
            logger.error(
                f"❌ 微信已被占用: {wechat_openid!r} (user_id={occupied.id})"
            )
            return False

        user.wechat_openid = wechat_openid
        logger.info(f"✅ 微信已绑定: user_id={user_id}")
    return True


# ============================================================
# 6. 注销账户（物理删除）
# ============================================================
def delete_account(user_id: int) -> bool:
    """
    注销账户（物理删除，不可恢复）

    顺序（先库后文件，库事务失败可回滚）：
        1. 同一事务内删除子表 → user_account，commit
        2. commit 成功后删除 data/user_uploads/{user_id}/

    删除顺序依据外键：
        user_notes.document_id → user_documents.id
        integration.document_id → user_documents.id
        所以 notes / integration 必须先于 documents 删；
        recycle_bin / user_account 无外键引用，位置任意。
    """
    logger.info("=" * 60)
    logger.info(f"注销账户: user_id={user_id}")
    logger.info("=" * 60)

    # ---------- 1. 数据库删除（同一事务） ----------
    with get_session() as session:
        user = session.query(UserAccount).filter_by(id=user_id).first()
        if not user:
            logger.error(f"❌ 用户不存在: user_id={user_id}")
            return False

        n = session.query(RecycleBin).filter_by(
            user_id=user_id,
        ).delete(synchronize_session=False)
        logger.info(f"  [1/4] 回收站记录已删除: {n} 条")

        n = session.query(Integration).filter_by(
            user_id=user_id,
        ).delete(synchronize_session=False)
        logger.info(f"  [2/4] 整合记录已删除: {n} 条")

        n = session.query(UserNote).filter_by(
            user_id=user_id,
        ).delete(synchronize_session=False)
        logger.info(f"  [3/4] 笔记已删除: {n} 条")

        n = session.query(UserDocument).filter_by(
            user_id=user_id,
        ).delete(synchronize_session=False)
        logger.info(f"       文档已删除: {n} 条")

        session.delete(user)
        logger.info(f"  [4/4] 用户记录已删除: user_id={user_id}")
        # with 退出时 commit；commit 失败会抛异常，不会走到删文件

    # ---------- 2. 文件系统删除（库已提交成功） ----------
    _safe_rmtree(USER_UPLOAD_DIR / str(user_id))

    logger.info(f"✅ 账户已注销: user_id={user_id}")
    return True


# ============================================================
# 7. 发送邮箱验证码
# ============================================================
def send_email_code(email: str) -> bool:
    """发送邮箱验证码"""
    # 简单的邮箱格式校验
    if not email or "@" not in email or "." not in email:
        logger.error(f"❌ 邮箱格式错误: {email}")
        return False

    # 生成 6 位数字验证码
    code = str(random.randint(100000, 999999))
    expires = time.time() + 300  # 5 分钟过期

    EMAIL_CODE_CACHE[email] = {"code": code, "expires": expires}
    logger.info(f"📧 验证码已生成: {email} -> {code}")

    # 如果配置了发件人，尝试真实发送；否则进入开发模式
    if EMAIL_USER and EMAIL_PASS:
        try:
            # yag = yagmail.SMTP(user=EMAIL_USER, password=EMAIL_PASS)
            yag = yagmail.SMTP(
                user=EMAIL_USER,
                password=EMAIL_PASS,
                host='smtp.qq.com',
                port=465,
                smtp_ssl=True  # 强制使用 SSL
            )
            yag.send(
                to=email,
                subject="【边读边记】邮箱绑定验证码",
                contents=f"您的验证码是：<strong>{code}</strong>，有效期 5 分钟。如非本人操作请忽略。"
            )
            logger.info(f"✅ 邮件已发送至: {email}")
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False
    else:
        # 开发模式：直接在控制台打印
        logger.warning(f"⚠️ 开发模式：未配置 EMAIL_USER/EMAIL_PASS，验证码为 -> {code}")

    return True


# ============================================================
# 8. 校验并绑定邮箱
# ============================================================
def verify_and_bind_email(user_id: int, email: str, code: str) -> bool:
    """校验验证码并绑定邮箱"""
    cached = EMAIL_CODE_CACHE.get(email)

    if not cached:
        logger.error(f"❌ 未找到该邮箱的验证码记录: {email}")
        return False

    if time.time() > cached["expires"]:
        logger.error(f"❌ 验证码已过期: {email}")
        del EMAIL_CODE_CACHE[email]
        return False

    if code.strip() != cached["code"]:
        logger.error(f"❌ 验证码错误: {email}")
        return False

    # 校验通过，清除缓存
    del EMAIL_CODE_CACHE[email]

    # 入库（复用之前的 bind_email 函数，但去掉格式校验，因为已经校验过了）
    with get_session() as session:
        user = session.query(UserAccount).filter_by(id=user_id, status="active").first()
        if not user:
            return False

        # 检查邮箱是否已被别人绑定
        occupied = session.query(UserAccount).filter(
            UserAccount.email == email,
            UserAccount.id != user_id,
        ).first()
        if occupied:
            logger.error(f"❌ 邮箱已被其他账号占用: {email}")
            return False

        user.email = email
        logger.info(f"✅ 邮箱验证通过并绑定成功: user_id={user_id}, email={email}")
    return True


# ============================================================
# 辅助函数
# ============================================================
def _safe_rmtree(target: Path) -> None:
    """安全删除目录：目标必须位于 USER_UPLOAD_DIR 之下"""
    if not target.exists():
        logger.info(f"  [files] 目录不存在: {target}")
        return

    try:
        root = USER_UPLOAD_DIR.resolve()
        resolved = target.resolve()
        if root not in resolved.parents:
            logger.error(
                f"  ⚠️ 拒绝删除越界路径: {resolved}（不在 {root} 之下）"
            )
            return
        shutil.rmtree(resolved)
        logger.info(f"  [files] 目录已删除: {resolved}")
    except Exception as e:
        logger.warning(f"  ⚠️ 目录删除失败: {target} - {e}")


def _user_to_dict(user: UserAccount) -> Dict:
    """UserAccount → Dict"""
    return {
        "id": user.id,
        "user_uuid": user.user_uuid,
        "phone_number": user.phone_number,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "email": user.email,
        "wechat_openid": user.wechat_openid,
        "status": user.status,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    USER_ID = 2
    ACTION = "delete"       # get / nickname / avatar / email / wechat / delete
    NEW_NICKNAME = "新昵称"
    NEW_AVATAR = "https://example.com/avatar.png"
    NEW_EMAIL = "test@example.com"
    NEW_WECHAT = "wx_openid_12345"

    print("=" * 60)
    print(f"账号操作: {ACTION}")
    print("=" * 60)

    if ACTION == "get":
        info = get_account(USER_ID)
        if info:
            import json
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print("❌ 用户不存在")
    elif ACTION == "nickname":
        print(f"结果: {update_nickname(USER_ID, NEW_NICKNAME)}")
    elif ACTION == "avatar":
        print(f"结果: {update_avatar(USER_ID, NEW_AVATAR)}")
    elif ACTION == "email":
        print(f"结果: {bind_email(USER_ID, NEW_EMAIL)}")
    elif ACTION == "wechat":
        print(f"结果: {bind_wechat(USER_ID, NEW_WECHAT)}")
    elif ACTION == "delete":
        print(f"结果: {delete_account(USER_ID)}")
    else:
        print(f"未知操作: {ACTION}")