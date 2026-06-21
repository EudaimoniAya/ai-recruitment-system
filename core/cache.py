from fastapi_cache import FastAPICache
from core.single import SingletonMeta
from settings import settings
from fastapi_cache.backends.redis import RedisBackend
from pydantic import BaseModel, EmailStr


class InviteInfoSchema(BaseModel):
    email: EmailStr
    department_id: str
    invite_code: str


class HRCache(metaclass=SingletonMeta):
    invite_prefix = "invite:"

    def __init__(self):
        self.cache_backend: RedisBackend = FastAPICache.get_backend()

    async def set(self, key, value, ex: int):
        await self.cache_backend.set(key, value, expire=ex if ex else None)

    async def get(self, key):
        value = await self.cache_backend.get(key)
        return value

    async def delete(self, key):
        await self.cache_backend.clear(key)

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
