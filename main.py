import asyncio
import sys

# Windows 下 psycopg 异步模式不支持 ProactorEventLoop，需切换为 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.user_router import router as user_router
import uvicorn

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(user_router)


def main():
    # loop="none" 让 uvicorn 使用系统 event loop policy，避免 Windows 上强制 ProactorEventLoop
    uvicorn.run(app, host="127.0.0.1", port=8000, loop="none")


if __name__ == "__main__":
    main()
