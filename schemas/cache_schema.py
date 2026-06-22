from pydantic import EmailStr, BaseModel


class InviteInfoSchema(BaseModel):
    email: EmailStr
    department_id: str
    invite_code: str


class DingTalkTokenInfoSchema(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
