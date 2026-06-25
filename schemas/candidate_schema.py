from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from schemas.cache_schema import TaskInfoSchema
from schemas.user_schema import UserSchema


class ResumeSchema(BaseModel):
    id: str = Field(..., description="简历ID")
    file_path: str = Field(..., description="简历存储路径")
    uploader: UserSchema = Field(..., description="简历上传者")

    model_config = ConfigDict(from_attributes=True)


class ResumeUploadRespSchema(BaseModel):
    resume: ResumeSchema | None = Field(..., description="简历信息")


class ResumePaseSchema(BaseModel):
    resume_id: str = Field(..., description="简历ID")


class ResumeParseTaskRespSchema(BaseModel):
    task_id: str = Field(..., description="任务ID")


class ResumeParseTaskInfoRespSchema(TaskInfoSchema):
    pass
