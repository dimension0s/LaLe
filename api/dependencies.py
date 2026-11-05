"""
dependencies.py - 路由层依赖
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from user_account_manager.jwt_utils import decode_token


# 声明 Bearer 安全方案（auto_error=False：自己处理缺头的情况，返回统一 401）
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> int:
    """从 Authorization: Bearer <token> 解析 user_id"""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Bearer Token",
        )

    token = credentials.credentials          # HTTPBearer 已剥掉 "Bearer "
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        )

    user_id = payload.get("user_id")
    try:
        return int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 中 user_id 非法",
        )