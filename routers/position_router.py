from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_current_user, get_session_instance
from models.user import UserModel
from repository.position_repo import PositionRepo
from schemas.position_schema import (
    PositionCreateSchema,
    PositionListRespSchema,
    PositionRespSchema,
)

router = APIRouter(prefix="/position", tags=["position"])


@router.post("/create", summary="创建职位", response_model=PositionRespSchema)
async def create_position(
    position_data: PositionCreateSchema,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_instance),
):
    async with session.begin():
        position_repo = PositionRepo(session=session)
        position_dict = position_data.model_dump()
        position_dict["creator_id"] = current_user.id
        position_dict["department_id"] = current_user.department.id
        position = await position_repo.create_position(position_dict)
        return {"position": position}


@router.get("/list", summary="职位列表", response_model=PositionListRespSchema)
async def get_position_list(
    page: int = 1,
    size: int = 10,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session_instance),
):
    async with session.begin():
        position_repo = PositionRepo(session=session)
        positions = await position_repo.get_possition_list(
            current_user, page=page, size=size
        )
        return {"positions": positions}
