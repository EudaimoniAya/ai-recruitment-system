from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from . import BaseModel

if TYPE_CHECKING:
    from .user import UserModel
    from .candidate import CandidateModel


class InterviewResultEnum(str, enum.Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING = "PENDING"


class InterviewModel(BaseModel):
    __tablename__ = "interviews"

    scheduled_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[Optional[InterviewResultEnum]] = mapped_column(
        Enum(InterviewResultEnum)
    )

    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), unique=True)
    interviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))

    candidate: Mapped[CandidateModel] = relationship(back_populates="interview")
    interviewer: Mapped[UserModel] = relationship()
