from redis.asyncio import Redis
from core.single import SingletonMeta
from schemas.cache_schema import (
    DingTalkTokenInfoSchema,
    InviteInfoSchema,
    TaskInfoSchema,
)
from settings import settings
from pydantic import BaseModel, EmailStr

_redis: Redis | None = None


def init_redis(redis: Redis) -> None:
    """在应用 lifespan 中初始化 Redis 连接"""
    global _redis
    _redis = redis


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis 尚未初始化，请先调用 init_redis()")
    return _redis


class HRCache(metaclass=SingletonMeta):
    invite_prefix = "invite:"
    dingtalk_prefix = "dingtalk:"
    task_prefix = "task:"
    email_last_uid_key = "email:last_uid"

    def __init__(self):
        self.redis = get_redis()

    async def set(self, key, value, ex: int):
        await self.redis.set(key, value, ex=ex if ex else None)

    async def get(self, key):
        return await self.redis.get(key)

    async def delete(self, key):
        await self.redis.delete(key)

    async def set_invite_info(self, invite_info: InviteInfoSchema):
        key = f"{self.invite_prefix}{invite_info.email}"
        await self.set(
            key, invite_info.model_dump_json(), ex=settings.invite_code_expire
        )

    async def get_invite_info(self, email: str) -> InviteInfoSchema | None:
        invite_info_json = await self.get(f"{self.invite_prefix}{email}")
        if invite_info_json:
            return InviteInfoSchema.model_validate_json(invite_info_json)
        return None

    async def delete_invite_info(self, email: str):
        await self.delete(key=f"{self.invite_prefix}{email}")

    async def set_dingtalk_info(self, dingtalk_info: DingTalkTokenInfoSchema):
        key = f"{self.dingtalk_prefix}{dingtalk_info.user_id}"
        await self.set(key, dingtalk_info.model_dump_json(), ex=60 * 60 * 24 * 29)

    async def get_dingtalk_info(self, user_id: str):
        key = f"{self.dingtalk_prefix}{user_id}"
        value = await self.get(key)
        return DingTalkTokenInfoSchema.model_validate_json(value)

    async def set_task_info(self, task_info: TaskInfoSchema):
        key = f"{self.task_prefix}{task_info.task_id}"
        await self.set(key, task_info.model_dump_json(), ex=60 * 60)

    async def get_task_info(self, task_id: str) -> TaskInfoSchema | None:
        key = f"{self.task_prefix}{task_id}"
        task_json = await self.get(key)
        if task_json is not None:
            task_info = TaskInfoSchema.model_validate_json(task_json)
            return task_info
        return None

    async def set_email_last_uid(self, last_uid: int, *, ex: int | None = None) -> None:
        await self.set(self.email_last_uid_key, str(int(last_uid)), ex=ex or 0)

    async def get_email_last_uid(self) -> int | None:
        value = await self.get(self.email_last_uid_key)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
