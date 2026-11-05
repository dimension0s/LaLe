"""
jwt_utils.py - JWT Token 工具
路径: /home/bina/LaLe/user_account_manager/jwt_utils.py

职责:
1. 创建 JWT Token
2. 解析 JWT Token
3. 提供 Token 有效期配置

说明:
- 使用 HS256 算法
- SECRET_KEY 从 .env 读取
- Token 默认有效期 7 天
"""

import os
import sys
from datetime import datetime, timedelta,timezone
from pathlib import Path
from typing import Dict, Optional

# ============================================================
# 兼容直接运行
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import jwt
from dotenv import load_dotenv
from loguru import logger


# ============================================================
# 配置
# ============================================================
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    logger.warning(
        "⚠️ 未设置 JWT_SECRET_KEY，使用默认密钥（仅开发用）"
    )
    SECRET_KEY = "dev-secret-key-change-me"

ALGORITHM = "HS256"
EXPIRE_DAYS = 7


# ============================================================
# 创建 Token
# ============================================================
def create_token(user_id: int, user_uuid: str) -> str:
    """
    创建 JWT Token

    Args:
        user_id: 用户 ID（整数）
        user_uuid: 用户 UUID

    Returns:
        JWT Token 字符串
    """
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "user_uuid": user_uuid,
        "iat": now,
        "exp": now + timedelta(days=EXPIRE_DAYS),
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(
        f"✅ Token 已创建: user_id={user_id}, "
        f"user_uuid={user_uuid[:8]}..., "
        f"有效期 {EXPIRE_DAYS} 天"
    )
    return token


# ============================================================
# 解析 Token
# ============================================================
def decode_token(token: str) -> Optional[Dict]:
    """
    解析 JWT Token

    Args:
        token: JWT Token 字符串

    Returns:
        解析后的 payload 字典，失败返回 None
    """
    if not token:
        logger.warning("Token 为空")
        return None

    # 去掉 "Bearer " 前缀
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(
            f"Token 解析成功: user_id={payload.get('user_id')}, "
            f"user_uuid={str(payload.get('user_uuid', ''))[:8]}..."
        )
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Token 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token 无效: {e}")
        return None


# ============================================================
# 便捷函数
# ============================================================
def get_user_id_from_token(token: str) -> Optional[int]:
    """从 Token 获取 user_id"""
    payload = decode_token(token)
    if payload:
        return payload.get("user_id")
    return None


def get_user_uuid_from_token(token: str) -> Optional[str]:
    """从 Token 获取 user_uuid"""
    payload = decode_token(token)
    if payload:
        return payload.get("user_uuid")
    return None


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("JWT Token 测试")
    print("=" * 60)
    print(f"SECRET_KEY: {SECRET_KEY[:10]}..." if SECRET_KEY else "未设置")
    print(f"ALGORITHM: {ALGORITHM}")
    print(f"EXPIRE_DAYS: {EXPIRE_DAYS}")
    print("=" * 60)

    # 1. 创建 Token
    print("\n[1] 创建 Token:")
    token = create_token(user_id=1, user_uuid="test-uuid-1234-5678")
    print(f"  {token[:50]}...")

    # 2. 解析 Token
    print("\n[2] 解析 Token:")
    payload = decode_token(token)
    if payload:
        print(f" user_id: {payload.get('user_id')}")
        print(f" user_uuid: {payload.get('user_uuid')}")
        print(f" iat: {payload.get('iat')}")
        print(f" exp: {payload.get('exp')}")

    # 3. 无效 Token
    print("\n[3] 无效 Token:")
    result = decode_token("invalid.token.here")
    print(f" 结果: {result}")

    # 4. Bearer 前缀
    print("\n[4] Bearer 前缀:")
    result = decode_token(f"Bearer {token}")
    if result:
        print(f"  user_id: {result.get('user_id')}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)