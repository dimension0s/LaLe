"""
auth.py - 用户认证（登录/登出/验证码）
路径: /home/bina/LaLe/user_account_manager/auth.py

职责:
1. 发送验证码（开发：固定 123456）
2. 验证码登录（首次登录自动创建）
3. 从 Token 获取用户
4. 登出（JWT 无状态）

开发模式:
- .env 中 AUTH_DEV_MODE=true → 跳过验证码校验
- 前端只需传手机号
- 生产环境 AUTH_DEV_MODE=false → 正常校验验证码
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# ============================================================
# 兼容直接运行
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from loguru import logger

from user_account_manager.jwt_utils import (
    create_token,
    decode_token,
)
from user_account_manager.pg_data_manager.database import get_session
from user_account_manager.pg_data_manager.orm_models import UserAccount


# ============================================================
# 配置
# ============================================================
# 加载 .env（确保 AUTH_DEV_MODE 读取到）
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# 开发模式（跳过验证码）
AUTH_DEV_MODE = os.getenv("AUTH_DEV_MODE", "false").lower() == "true"

# 固定验证码（开发阶段）
FIXED_CODE = "123456"


# ============================================================
# 辅助：手机号脱敏
# ============================================================
def _mask_phone(phone: str) -> str:
    """手机号脱敏：138****8000"""
    if not phone or len(phone) < 7:
        return "***"
    return f"{phone[:3]}****{phone[-4:]}"


# ============================================================
# 1. 发送验证码
# ============================================================
def send_code(phone_number: str) -> bool:
    """
    发送验证码（开发：固定 123456）

    Args:
        phone_number: 手机号

    Returns:
        是否成功
    """
    if not phone_number:
        logger.error("❌ 手机号不能为空")
        return False

    phone_number = phone_number.strip()

    # 简单校验：11 位数字
    if not phone_number.isdigit() or len(phone_number) != 11:
        logger.error(f"❌ 手机号格式错误: {_mask_phone(phone_number)!r}")
        return False

    if AUTH_DEV_MODE:
        logger.info(
            f"📱 发送验证码到 {_mask_phone(phone_number)}: "
            f"{FIXED_CODE}（开发阶段固定）"
        )
    else:
        # 生产阶段：调用短信 API（待实现）
        logger.warning("⚠️ 生产阶段短信发送未实现")

    return True


# ============================================================
# 2. 登录
# ============================================================
def login(
    phone_number: str,
    code: Optional[str] = None,
) -> Optional[Dict]:
    """
    验证码登录（首次登录自动创建）

    Args:
        phone_number: 手机号
        code: 验证码（开发模式可省略）

    Returns:
        {"token": "...", "user": {...}, "is_new_user": bool} 或 None
    """
    # 1. 参数校验
    if not phone_number or not phone_number.strip():
        logger.error("❌ 手机号不能为空")
        return None

    phone_number = phone_number.strip()

    logger.info("=" * 60)
    logger.info("登录")
    logger.info(f" 手机号: {_mask_phone(phone_number)}")
    logger.info(f" 开发模式: {AUTH_DEV_MODE}")
    logger.info("=" * 60)

    # 2. 验证码校验
    if AUTH_DEV_MODE:
        # 开发模式：跳过验证码
        logger.info("🔧 开发模式：跳过验证码校验")
    else:
        # 生产模式：必须校验验证码
        if not code or not code.strip():
            logger.error("❌ 验证码不能为空")
            return None

        if code.strip() != FIXED_CODE:
            logger.error(f"❌ 验证码错误: {code!r}")
            return None

    # 3. 查用户 / 首次创建（先校验，后写库）
    with get_session() as session:
        user = session.query(UserAccount).filter_by(
            phone_number=phone_number,
        ).first()

        is_new_user = False

        if user:
            # 老用户：先校验状态，异常则在修改任何字段前退出
            if user.status != "active":
                logger.error(f"❌ 用户状态异常: {user.status}")
                return None      # 未修改任何字段，commit 空事务，安全
            user.last_login_at = datetime.now()
        else:
            # 新用户：默认 active，直接创建
            logger.info("  首次登录，自动创建用户")
            user = UserAccount(
                phone_number=phone_number,
                nickname=f"用户{phone_number[-4:]}",
                avatar_url="",
                status="active",
                last_login_at=datetime.now(),
            )
            session.add(user)
            is_new_user = True

        # 4. 所有校验通过，统一 flush 拿自增 id
        session.flush()

        # 5. 收集信息（此时 user.id 必有值）
        user_id = user.id
        user_uuid = user.user_uuid
        user_data = _user_to_dict(user)

    # 6. 生成 Token
    token = create_token(user_id, user_uuid)

    logger.info(
        f"✅ 登录成功: user_id={user_id}, "
        f"user_uuid={user_uuid[:8]}..., "
        f"{'新用户' if is_new_user else '老用户'}"
    )

    return {
        "token": token,
        "user": user_data,
        "is_new_user": is_new_user,
    }


# ============================================================
# 3. 从 Token 获取用户
# ============================================================
def get_user_by_token(token: str) -> Optional[Dict]:
    """
    从 Token 获取用户信息

    Args:
        token: JWT Token

    Returns:
        用户字典，失败返回 None
    """
    payload = decode_token(token)
    if not payload:
        return None

    user_id = payload.get("user_id")
    if not user_id:
        logger.warning("Token 中没有 user_id")
        return None

    # 类型校验：JWT payload 反序列化后应为 int，防御性强转
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        logger.warning(f"Token 中 user_id 非法: {user_id!r}")
        return None

    with get_session() as session:
        user = session.query(UserAccount).filter_by(
            id=user_id,
            status="active",
        ).first()

        if not user:
            logger.warning(f"用户不存在或状态异常: user_id={user_id}")
            return None

        return _user_to_dict(user)


# ============================================================
# 4. 登出
# ============================================================
def logout(token: str) -> bool:
    """
    登出（JWT 无状态，客户端删 Token 即可）

    Args:
        token: JWT Token

    Returns:
        始终 True
    """
    payload = decode_token(token)
    if payload:
        logger.info(f"用户登出: user_id={payload.get('user_id')}")
    else:
        logger.warning("登出时 Token 无效")

    return True


# ============================================================
# 辅助函数
# ============================================================
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
    # ================================================
    # 测试参数
    # ================================================
    PHONE_NUMBER = "13800138000"
    # ================================================

    print("=" * 60)
    print("用户认证测试")
    print("=" * 60)
    print(f"开发模式: {AUTH_DEV_MODE}")
    print("=" * 60)

    # 1. 发送验证码
    print("\n[1] 发送验证码:")
    result = send_code(PHONE_NUMBER)
    print(f"  结果: {result}")

    # 2. 登录（开发模式不传 code）
    print("\n[2] 登录（一键登录）:")
    if AUTH_DEV_MODE:
        login_result = login(PHONE_NUMBER)   # 不传 code
    else:
        login_result = login(PHONE_NUMBER, FIXED_CODE)

    if login_result:
        print(f"  Token: {login_result['token'][:50]}...")
        print(f"  用户 ID: {login_result['user']['id']}")
        print(f"  手机号: {_mask_phone(login_result['user']['phone_number'])}")
        print(f"  昵称: {login_result['user']['nickname']}")
        print(f"  新用户: {login_result['is_new_user']}")

        token = login_result["token"]

        # 3. 从 Token 获取用户
        print("\n[3] 从 Token 获取用户:")
        user = get_user_by_token(token)
        if user:
            print(f"  user_id: {user['id']}")
            print(f"  nickname: {user['nickname']}")
            print(f"  phone_number: {_mask_phone(user['phone_number'])}")

        # 4. 登出
        print("\n[4] 登出:")
        result = logout(token)
        print(f" 结果: {result}")
    else:
        print(" ❌登录失败")

    # 5. 再次登录（老用户）
    print("\n[5] 再次登录（老用户）:")
    if AUTH_DEV_MODE:
        login_result2 = login(PHONE_NUMBER)
    else:
        login_result2 = login(PHONE_NUMBER, FIXED_CODE)

    if login_result2:
        print(f"  新用户: {login_result2['is_new_user']}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)