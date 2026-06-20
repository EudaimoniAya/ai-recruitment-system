from pydantic import BaseModel, EmailStr, Field


class UserLoginSchema(BaseModel):
    email: EmailStr = Field(..., description="邮箱账号")
    password: str = Field(..., description="密码", min_length=6, max_length=20)
