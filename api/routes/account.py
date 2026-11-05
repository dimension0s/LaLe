"""
account 路由（全部需要登录）
"""

from fastapi import APIRouter, Depends,File, UploadFile
import shutil
import uuid
from pathlib import Path
from loguru import logger
from user_account_manager.pg_data_manager.database import get_session
from user_account_manager.pg_data_manager.orm_models import UserAccount

from api.dependencies import get_current_user_id
from api.response import ok, fail
from api.schemas.account import (
    BindEmailRequest, BindWechatRequest,
    UpdateAvatarRequest, UpdateNicknameRequest,
)
from user_account_manager import account
from pydantic import BaseModel

# 计算项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AVATAR_DIR = PROJECT_ROOT / "data" / "user_avatars"


router = APIRouter()

class SendEmailCodeRequest(BaseModel):
    email: str

class VerifyEmailRequest(BaseModel):
    email: str
    code: str

@router.post("/email/send_code")
def send_email_code(req: SendEmailCodeRequest, user_id: int = Depends(get_current_user_id)):
    if account.send_email_code(req.email):
        return ok(msg="验证码已发送")
    return fail(400, "发送失败，请检查邮箱格式")

@router.post("/email/verify")
def verify_email(req: VerifyEmailRequest, user_id: int = Depends(get_current_user_id)):
    if account.verify_and_bind_email(user_id, req.email, req.code):
        return ok(msg="邮箱绑定成功")
    return fail(400, "验证码错误或已过期")

@router.get("")
def get_account(user_id: int = Depends(get_current_user_id)):
    info = account.get_account(user_id)
    if info is None:
        return fail(404, "用户不存在")
    return ok(data=info)


@router.patch("/nickname")
def update_nickname(
    req: UpdateNicknameRequest,
    user_id: int = Depends(get_current_user_id),
):
    if not account.update_nickname(user_id, req.nickname):
        return fail(400, "修改昵称失败")
    return ok()


@router.patch("/avatar")
def update_avatar(
    req: UpdateAvatarRequest,
    user_id: int = Depends(get_current_user_id),
):
    if not account.update_avatar(user_id, req.avatar_url):
        return fail(400, "修改头像失败")
    return ok()

@router.post("/avatar/upload")
async def upload_avatar(
        file: UploadFile = File(...),
        user_id: int = Depends(get_current_user_id),
):
    """上传本地头像文件"""
    # 1. 校验文件格式
    allowed_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_exts:
        return fail(400, f"不支持的头像格式，仅支持 {', '.join(allowed_exts)}")

    # 2. 生成唯一文件名防止覆盖
    file_name = f"{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = AVATAR_DIR / file_name

    # 3. 保存文件
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"❌ 头像保存失败: {e}")
        return fail(500, "文件保存失败")

    # 4. 构造访问 URL（假设后端运行在 localhost:8000）
    # 注意：生产环境请替换为你的真实域名，或者写进环境变量
    avatar_url = f"http://localhost:8000/avatars/{file_name}"

    # 5. 更新数据库
    with get_session() as session:
        user = session.query(UserAccount).filter_by(id=user_id, status="active").first()
        if not user:
            return fail(404, "用户不存在")

        user.avatar_url = avatar_url
        logger.info(f"✅ 用户 {user_id} 头像已更新: {avatar_url}")

    return ok(data={"avatar_url": avatar_url}, msg="头像上传成功")

@router.post("/email")
def bind_email(
    req: BindEmailRequest,
    user_id: int = Depends(get_current_user_id),
):
    if not account.bind_email(user_id, req.email):
        return fail(400, "绑定邮箱失败（格式错误或已被占用）")
    return ok()


@router.post("/wechat")
def bind_wechat(
    req: BindWechatRequest,
    user_id: int = Depends(get_current_user_id),
):
    if not account.bind_wechat(user_id, req.wechat_openid):
        return fail(400, "绑定微信失败（已被占用）")
    return ok()


@router.delete("")
def delete_account(user_id: int = Depends(get_current_user_id)):
    if not account.delete_account(user_id):
        return fail(400, "注销失败")
    return ok(msg="账户已注销")

