from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import InterviewReport, InterviewSession
from app.models.schemas import PerformanceReport, ReportRequest
from app.services import report_generator

router = APIRouter(prefix="/report", tags=["report"])


@router.post("", response_model=PerformanceReport)
def generate(request: ReportRequest, db: Session = Depends(get_db)) -> PerformanceReport:
    session = db.get(InterviewSession, request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    if not session.turns:
        raise HTTPException(status_code=400, detail="No interview turns to evaluate yet.")

    report = report_generator.generate_report(session)

    existing = db.execute(
        select(InterviewReport).where(InterviewReport.session_id == session.id)
    ).scalar_one_or_none()
    if existing:
        existing.report_json = report.model_dump()
    else:
        db.add(InterviewReport(session_id=session.id, report_json=report.model_dump()))
    db.commit()

    return report


@router.get("/{session_id}", response_model=PerformanceReport)
def get_report(session_id: str, db: Session = Depends(get_db)) -> PerformanceReport:
    existing = db.execute(
        select(InterviewReport).where(InterviewReport.session_id == session_id)
    ).scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Report not found. Generate it first.")
    return PerformanceReport(**existing.report_json)


@router.get("/history/all")
def history(db: Session = Depends(get_db)) -> list[dict]:
    """Bonus feature: interview history across sessions, for a simple progress-tracking view."""
    sessions = db.execute(select(InterviewSession).order_by(InterviewSession.created_at.desc())).scalars().all()
    out = []
    for s in sessions:
        role_title = (s.role_analysis or {}).get("role_title", "Untitled role")
        fit = (s.job_fit or {}).get("score_percent")
        report = db.execute(
            select(InterviewReport).where(InterviewReport.session_id == s.id)
        ).scalar_one_or_none()
        out.append(
            {
                "session_id": s.id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "role_title": role_title,
                "job_fit_percent": fit,
                "interview_complete": s.interview_complete,
                "overall_score": (report.report_json or {}).get("overall_score") if report else None,
                "readiness_label": (report.report_json or {}).get("readiness_label") if report else None,
            }
        )
    return out
