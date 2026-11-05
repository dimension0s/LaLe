from pydantic import BaseModel, Field


class UpdateNicknameRequest(BaseModel):
    nickname: str = Field(..., max_length=100)


class UpdateAvatarRequest(BaseModel):
    avatar_url: str = Field(..., max_length=500)


class BindEmailRequest(BaseModel):
    email: str = Field(..., max_length=200)


class BindWechatRequest(BaseModel):
    wechat_openid: str = Field(..., max_length=200)