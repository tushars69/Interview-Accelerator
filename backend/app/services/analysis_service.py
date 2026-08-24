from __future__ import annotations

import json

from app.core.groq_client import chat_json
from app.models.schemas import JobFit, ResumeAnalysis, RoleAnalysis
from app.prompts import templates as t


def analyze_role(jd_text: str) -> RoleAnalysis:
    data = chat_json(
        t.ROLE_ANALYSIS_SYSTEM,
        t.ROLE_ANALYSIS_USER.format(jd_text=jd_text),
        temperature=0.2,
        max_tokens=3500,
    )
    return RoleAnalysis(**data)


def analyze_resume(resume_text: str, role_analysis: RoleAnalysis) -> ResumeAnalysis:
    data = chat_json(
        t.RESUME_ANALYSIS_SYSTEM,
        t.RESUME_ANALYSIS_USER.format(
            role_analysis_json=role_analysis.model_dump_json(),
            resume_text=resume_text,
        ),
        temperature=0.3,
        max_tokens=4000,
    )
    return ResumeAnalysis(**data)


def score_job_fit(role_analysis: RoleAnalysis, resume_analysis: ResumeAnalysis) -> JobFit:
    data = chat_json(
        t.JOB_FIT_SYSTEM,
        t.JOB_FIT_USER.format(
            role_analysis_json=role_analysis.model_dump_json(),
            resume_analysis_json=resume_analysis.model_dump_json(),
        ),
        temperature=0.2,
        max_tokens=1500,
    )
    return JobFit(**data)


def run_full_analysis(jd_text: str, resume_text: str) -> tuple[RoleAnalysis, ResumeAnalysis, JobFit]:
    """Convenience pipeline used by the /analyze endpoint."""
    role_analysis = analyze_role(jd_text)
    resume_analysis = analyze_resume(resume_text, role_analysis)
    job_fit = score_job_fit(role_analysis, resume_analysis)
    return role_analysis, resume_analysis, job_fit
