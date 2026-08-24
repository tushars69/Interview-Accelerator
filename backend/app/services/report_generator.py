from __future__ import annotations

import json

from app.core.groq_client import chat_json
from app.db.models import InterviewSession
from app.models.schemas import PerformanceReport
from app.prompts import templates as t

READINESS_LABELS = {
    "not_ready": "🔴 Not Ready",
    "needs_preparation": "🟠 Needs Preparation",
    "interview_ready": "🟡 Interview Ready",
    "strong_candidate": "🟢 Strong Candidate",
}


def _transcript_json(session: InterviewSession) -> list[dict]:
    return [
        {
            "level": turn.level,
            "question": turn.question,
            "answer": turn.answer,
            "assessment": turn.assessment,
            "good_points": turn.good_points,
            "improvement_points": turn.improvement_points,
            "ideal_direction": turn.ideal_direction,
            "answer_quality_score": turn.answer_quality_score,
        }
        for turn in session.turns
    ]


def generate_report(session: InterviewSession) -> PerformanceReport:
    transcript = _transcript_json(session)

    user_prompt = t.REPORT_USER.format(
        role_analysis_json=json.dumps(session.role_analysis),
        resume_analysis_json=json.dumps(session.resume_analysis),
        job_fit_json=json.dumps(session.job_fit),
        transcript_json=json.dumps(transcript),
    )
    data = chat_json(t.REPORT_SYSTEM, user_prompt, temperature=0.3, max_tokens=3000)

    # Question-level feedback comes straight from the transcript we already have
    # (not re-derived by the LLM) so it's guaranteed to match what actually happened.
    question_feedback = [
        {
            "question": turn.question,
            "answer": turn.answer or "(no answer recorded)",
            "assessment": turn.assessment or "",
            "what_was_good": turn.good_points or [],
            "what_could_be_better": turn.improvement_points or [],
            "ideal_direction": turn.ideal_direction or "",
        }
        for turn in session.turns
        if turn.answer
    ]

    readiness = data.get("readiness", "needs_preparation")
    report = PerformanceReport(
        session_id=session.id,
        overall_score=int(data.get("overall_score", 50)),
        competency_scores=data.get("competency_scores", []),
        question_feedback=question_feedback,
        strengths=data.get("strengths", []),
        weaknesses=data.get("weaknesses", []),
        preparation_gaps=data.get("preparation_gaps", []),
        readiness=readiness,
        readiness_label=data.get("readiness_label") or READINESS_LABELS.get(readiness, readiness),
        readiness_summary=data.get("readiness_summary", ""),
    )
    return report
