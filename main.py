import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# 尽早加载 .env，避免 router/agent 导入 LangChain 时还未注入 LangSmith 环境变量
load_dotenv(Path(__file__).resolve().parent / ".env")

# Windows 下 psycopg 异步模式不支持 ProactorEventLoop，需切换为 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.user_router import router as user_router
from routers.position_router import router as position_router
from routers.candidate_router import router as candidate_router
from routers.dashboard_router import router as dashboard_router
import uvicorn
from settings import settings
from redis import asyncio as aioredis
from core.cache import init_redis
from contextlib import asynccontextmanager
from scheduler import start_email_polling


@asynccontextmanager
async def lifespan(_: FastAPI):
    redis = aioredis.from_url(
        f"redis://{settings.redis_host}:{settings.redis_port}",
        encoding="utf8",
        decode_responses=True,
    )
    init_redis(redis)
    bot, scheduler = await start_email_polling()
    yield
    await redis.aclose()
    if bot.is_connected:
        await bot.close()
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(user_router)
app.include_router(position_router)
app.include_router(candidate_router)
app.include_router(dashboard_router)


def main():
    # loop="none" 让 uvicorn 使用系统 event loop policy，避免 Windows 上强制 ProactorEventLoop
    uvicorn.run("main:app", host="127.0.0.1", port=8000, loop="none", reload=True)


if __name__ == "__main__":
    main()
