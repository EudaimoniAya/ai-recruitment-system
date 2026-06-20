from fastapi import APIRouter, Request

router = APIRouter(prefix="/user", tags=["users"])


@router.post("/login", summary="登录")
async def login(request: Request):
    return {"message": "Hello, World!"}
