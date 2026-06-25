from typing import Any, Literal
from pydantic import EmailStr, BaseModel

from schemas.agent_schema import AgentCandidateSchema


class InviteInfoSchema(BaseModel):
    email: EmailStr
    department_id: str
    invite_code: str


class DingTalkTokenInfoSchema(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str


class TaskInfoSchema(BaseModel):
    task_id: str
    status: Literal["pending", "done", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = None
