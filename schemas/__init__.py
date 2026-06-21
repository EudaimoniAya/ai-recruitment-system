from typing import Literal
from pydantic import BaseModel, Field


class ResponseSchema(BaseModel):
    result: Literal["success", "fail"] = Field("success", description="响应消息")
