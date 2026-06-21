import random
import string
from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from core.cache import HRCache, InviteInfoSchema
from models import AsyncSession
from models.user import UserModel, UserStatus
from repository.user_repo import DepartmentRepo, UserRepo
from dependencies import (
    get_cache_instance,
    get_session_instance,
    get_auth_handler,
    AuthHandler,
    get_super_user,
)
from schemas import ResponseSchema
from schemas.user_schema import UserInviteSchema, UserLoginSchema, UserLoginRespSchema
from tasks import send_invite_email_task

router = APIRouter(prefix="/user", tags=["users"])


@router.post("/login", summary="登录", response_model=UserLoginRespSchema)
async def login(
    login_data: UserLoginSchema,
    session: AsyncSession = Depends(get_session_instance),
    auth_handler: AuthHandler = Depends(get_auth_handler),
):
    # 开启事务
    async with session.begin():
        # 1. 获取用户
        user_repo = UserRepo(session)
        user: UserModel = await user_repo.get_by_email(str(login_data.email))
        if not user:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="该用户不存在！")
        # 2. 验证密码是否正确
        if not user.check_password(login_data.password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="邮箱或密码错误！")
        # 3. 判断员工状态
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail="该员工状态不可用，请联系管理员！"
            )
        # 4. 生成JWToken
        tokens = auth_handler.encode_login_token(user.id)
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "user": user,
        }


@router.post(
    "/invite",
    summary="邀请用户，会给指定的用户邮箱发送邮件",
    response_model=ResponseSchema,
)
async def invite_user(
    invite_data: UserInviteSchema,
    session: AsyncSession = Depends(get_session_instance),
    cache: HRCache = Depends(get_cache_instance),
    _: UserModel = Depends(get_super_user),
):
    async with session.begin():
        user_repo = UserRepo(session)
        user = await user_repo.get_by_email(str(invite_data.email))
        if user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已存在！"
            )
        department_repo = DepartmentRepo(session)
        department = await department_repo.get_by_id(
            department_id=invite_data.department_id
        )
        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="该部门不存在！"
            )
    # 生成6位数字验证码
    invite_code = "".join(random.sample(string.digits, 6))
    # 先发送邮件，成功后再写入缓存
    sent = await send_invite_email_task(
        str(invite_data.email),
        invite_code,
        department.name,
    )
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="邀请邮件发送失败，请检查 MAIL_USERNAME / MAIL_FROM 配置是否一致，或稍后重试",
        )
    invite_info = InviteInfoSchema(
        email=invite_data.email,
        department_id=invite_data.department_id,
        invite_code=invite_code,
    )
    await cache.set_invite_info(invite_info)
    return ResponseSchema()
