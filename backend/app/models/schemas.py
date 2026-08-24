from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

InterviewLevel = Literal["screening", "competency", "deep_dive"]
Readiness = Literal["not_ready", "needs_preparation", "interview_ready", "strong_candidate"]


# ---------------------------------------------------------------------------
# Step 1 — Role (JD) analysis
# ---------------------------------------------------------------------------
class RoleAnalysis(BaseModel):
    role_title: str
    seniority_level: str = ""
    key_responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    technical_competencies: list[str] = Field(default_factory=list)
    behavioural_competencies: list[str] = Field(default_factory=list)
    experience_expectations: str = ""
    important_keywords: list[str] = Field(default_factory=list)
    important_concepts: list[str] = Field(default_factory=list)
    key_qualifications: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Step 2 — Candidate (resume) analysis
# ---------------------------------------------------------------------------
class ResumeAnalysis(BaseModel):
    candidate_name: str = ""
    key_skills: list[str] = Field(default_factory=list)
    relevant_experience: list[str] = Field(default_factory=list)
    relevant_projects: list[str] = Field(default_factory=list)
    relevant_achievements: list[str] = Field(default_factory=list)
    strengths_vs_jd: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    weak_or_insufficient_areas: list[str] = Field(default_factory=list)
    resume_claims_to_probe: list[str] = Field(default_factory=list)
    preparation_focus_areas: list[str] = Field(default_factory=list)


class JobFit(BaseModel):
    score_percent: int = Field(ge=0, le=100)
    strong_match: list[str] = Field(default_factory=list)
    partial_match: list[str] = Field(default_factory=list)
    missing_or_weak: list[str] = Field(default_factory=list)
    rationale: str = ""


class AnalyzeRequest(BaseModel):
    jd_text: str
    resume_text: str


class AnalyzeResponse(BaseModel):
    session_id: str
    role_analysis: RoleAnalysis
    resume_analysis: ResumeAnalysis
    job_fit: JobFit


# ---------------------------------------------------------------------------
# Interview turns
# ---------------------------------------------------------------------------
class TranscriptTurn(BaseModel):
    level: InterviewLevel
    question: str
    answer: str | None = None
    assessment: str | None = None
    good_points: list[str] = Field(default_factory=list)
    improvement_points: list[str] = Field(default_factory=list)
    ideal_direction: str | None = None
    answer_quality_score: int | None = Field(default=None, ge=0, le=10)


class StartInterviewRequest(BaseModel):
    session_id: str


class InterviewTurnResponse(BaseModel):
    session_id: str
    level: InterviewLevel
    level_progress: str  # e.g. "Question 2 of ~4"
    question: str
    question_number_overall: int
    difficulty: str  # "easy" | "standard" | "hard"
    interview_complete: bool = False
    topics_covered: list[str] = Field(default_factory=list)


class AnswerRequest(BaseModel):
    session_id: str
    answer_text: str


class ReportRequest(BaseModel):
    session_id: str


class CompetencyScore(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    note: str = ""


class QuestionFeedback(BaseModel):
    question: str
    answer: str
    assessment: str
    what_was_good: list[str]
    what_could_be_better: list[str]
    ideal_direction: str


class PreparationItem(BaseModel):
    priority: int
    topic: str
    review_points: list[str] = Field(default_factory=list)


class PerformanceReport(BaseModel):
    session_id: str
    overall_score: int = Field(ge=0, le=100)
    competency_scores: list[CompetencyScore]
    question_feedback: list[QuestionFeedback]
    strengths: list[str]
    weaknesses: list[str]
    preparation_gaps: list[PreparationItem]
    readiness: Readiness
    readiness_label: str
    readiness_summary: str
