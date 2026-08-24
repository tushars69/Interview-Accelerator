import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    jd_text: Mapped[str] = mapped_column(Text)
    resume_text: Mapped[str] = mapped_column(Text)

    role_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    resume_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    job_fit: Mapped[dict] = mapped_column(JSON, default=dict)

    # Live interview state machine
    current_level: Mapped[str] = mapped_column(String, default="screening")
    difficulty: Mapped[str] = mapped_column(String, default="standard")
    questions_asked_this_level: Mapped[int] = mapped_column(Integer, default=0)
    performance_running_score: Mapped[float] = mapped_column(Integer, default=60)
    topics_covered: Mapped[list] = mapped_column(JSON, default=list)
    claims_to_probe: Mapped[list] = mapped_column(JSON, default=list)
    interview_complete: Mapped[bool] = mapped_column(default=False)
    pending_question: Mapped[str] = mapped_column(Text, default="")

    turns: Mapped[list["InterviewTurn"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="InterviewTurn.turn_index"
    )
    report: Mapped["InterviewReport"] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("interview_sessions.id"))
    turn_index: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    assessment: Mapped[str] = mapped_column(Text, default="")
    good_points: Mapped[list] = mapped_column(JSON, default=list)
    improvement_points: Mapped[list] = mapped_column(JSON, default=list)
    ideal_direction: Mapped[str] = mapped_column(Text, default="")
    answer_quality_score: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped["InterviewSession"] = relationship(back_populates="turns")


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("interview_sessions.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)

    session: Mapped["InterviewSession"] = relationship(back_populates="report")
