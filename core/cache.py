from redis.asyncio import Redis
from core.single import SingletonMeta
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


class InviteInfoSchema(BaseModel):
    email: EmailStr
    department_id: str
    invite_code: str


class HRCache(metaclass=SingletonMeta):
    invite_prefix = "invite:"

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
