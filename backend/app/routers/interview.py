from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import InterviewSession
from app.models.schemas import AnswerRequest, InterviewTurnResponse, StartInterviewRequest
from app.services import interview_engine

router = APIRouter(prefix="/interview", tags=["interview"])


def _get_session_or_404(db: Session, session_id: str) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    return session


@router.post("/start", response_model=InterviewTurnResponse)
def start(request: StartInterviewRequest, db: Session = Depends(get_db)) -> InterviewTurnResponse:
    session = _get_session_or_404(db, request.session_id)
    return interview_engine.start_interview(db, session)


@router.post("/answer", response_model=InterviewTurnResponse)
def answer(request: AnswerRequest, db: Session = Depends(get_db)) -> InterviewTurnResponse:
    session = _get_session_or_404(db, request.session_id)
    if not request.answer_text.strip():
        raise HTTPException(status_code=400, detail="answer_text cannot be empty.")
    return interview_engine.submit_answer(db, session, request.answer_text)


@router.get("/{session_id}/transcript")
def get_transcript(session_id: str, db: Session = Depends(get_db)) -> list[dict]:
    session = _get_session_or_404(db, session_id)
    return [
        {
            "level": turn.level,
            "question": turn.question,
            "answer": turn.answer,
            "assessment": turn.assessment,
            "answer_quality_score": turn.answer_quality_score,
        }
        for turn in session.turns
    ]
