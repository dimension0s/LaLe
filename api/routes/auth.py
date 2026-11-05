"""
auth 路由（不需要登录）
"""

from fastapi import APIRouter

from api.response import ok, fail
from api.schemas.auth import LoginRequest, SendCodeRequest
from user_account_manager import auth


router = APIRouter()


@router.post("/send_code")
def send_code(req: SendCodeRequest):
    result = auth.send_code(req.phone_number)
    if not result:
        return fail(400, "发送验证码失败（手机号格式错误）")
    return ok()


@router.post("/login")
def login(req: LoginRequest):
    result = auth.login(req.phone_number, req.code)
    if result is None:
        return fail(400, "登录失败")
    return ok(data=result)


@router.post("/logout")
def logout(authorization: str = ""):
    # JWT 无状态，登出仅记录日志；前端删除 token 即可
    auth.logout(authorization)
    return ok()