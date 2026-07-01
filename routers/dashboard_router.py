from fastapi import APIRouter, Depends
from models import AsyncSession
from dependencies import get_session_instance, get_current_user
from models.user import UserModel
from repository.candidate_repo import CandidateRepo
from datetime import datetime, timedelta, time

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/candidate/7d", summary="获取最近7天系统中新增候选人的数量")
async def get_7d_candidate(
    session: AsyncSession = Depends(get_session_instance),
    _: UserModel = Depends(get_current_user),
):
    async with session.begin():
        candidate_repo = CandidateRepo(session)
        now = datetime.now()
        today = now.date()
        # 含今天在内共 7 天：从 6 天前的 0 点 到 明天 0 点（不含）
        start_time = datetime.combine(today - timedelta(days=6), time.min)
        end_time = datetime.combine(today + timedelta(days=1), time.min)
        rows = await candidate_repo.candidate_count(
            start_time=start_time,
            end_time=end_time,
        )
        day_counts = {day: count for day, count in rows}
        result = []
        for x in range(7):
            day_x = (start_time + timedelta(days=x)).date()
            result.append(
                {
                    "day": day_x.isoformat(),
                    "count": day_counts.get(day_x, 0),
                }
            )
        return result
