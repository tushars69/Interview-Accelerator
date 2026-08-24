from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import InterviewSession
from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.services import analysis_service
from app.services.file_parser import extract_text

router = APIRouter(prefix="/analyze", tags=["analysis"])


@router.post("/extract-text")
async def extract_text_from_file(file: UploadFile = File(...)) -> dict:
    """Used by the frontend when the user uploads a JD/resume file instead of pasting text."""
    contents = await file.read()
    try:
        text = extract_text(file.filename, contents)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}") from exc
    if not text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in file.")
    return {"text": text}


@router.post("", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)) -> AnalyzeResponse:
    """
    Runs Step 1 (role analysis) + Step 2 (candidate analysis) + Job Fit scoring,
    then creates a new interview session row to hold all downstream state.
    """
    if not request.jd_text.strip() or not request.resume_text.strip():
        raise HTTPException(status_code=400, detail="Both jd_text and resume_text are required.")

    role_analysis, resume_analysis, job_fit = analysis_service.run_full_analysis(
        request.jd_text, request.resume_text
    )

    session = InterviewSession(
        jd_text=request.jd_text,
        resume_text=request.resume_text,
        role_analysis=role_analysis.model_dump(),
        resume_analysis=resume_analysis.model_dump(),
        job_fit=job_fit.model_dump(),
        claims_to_probe=list(resume_analysis.resume_claims_to_probe),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return AnalyzeResponse(
        session_id=session.id,
        role_analysis=role_analysis,
        resume_analysis=resume_analysis,
        job_fit=job_fit,
    )


@router.get("/{session_id}", response_model=AnalyzeResponse)
def get_analysis(session_id: str, db: Session = Depends(get_db)) -> AnalyzeResponse:
    session = db.get(InterviewSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return AnalyzeResponse(
        session_id=session.id,
        role_analysis=session.role_analysis,
        resume_analysis=session.resume_analysis,
        job_fit=session.job_fit,
    )
