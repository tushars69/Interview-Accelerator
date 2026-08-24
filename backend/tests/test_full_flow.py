"""
End-to-end test of the whole backend pipeline with Groq calls mocked out,
so it runs offline and deterministically in CI.

Run with:  poetry run pytest backend/tests -v
"""
from __future__ import annotations

import itertools
import os
from unittest.mock import patch

os.environ.setdefault("GROQ_API_KEY", "test_key_for_ci")

import pytest
from fastapi.testclient import TestClient

from app.main import app

FAKE_ROLE = {
    "role_title": "AI Engineer Intern",
    "seniority_level": "Intern",
    "key_responsibilities": ["Build RAG pipelines"],
    "required_skills": ["Python", "RAG", "APIs"],
    "preferred_skills": ["Cloud"],
    "technical_competencies": ["ML"],
    "behavioural_competencies": ["Communication"],
    "experience_expectations": "0-1 yrs",
    "important_keywords": ["RAG"],
    "important_concepts": ["Embeddings"],
    "key_qualifications": ["CS degree"],
}

FAKE_RESUME = {
    "candidate_name": "Test Candidate",
    "key_skills": ["Python", "RAG"],
    "relevant_experience": ["ML Intern"],
    "relevant_projects": ["RAG chatbot"],
    "relevant_achievements": ["Improved accuracy 18%"],
    "strengths_vs_jd": ["Python"],
    "missing_skills": ["Cloud"],
    "weak_or_insufficient_areas": ["System design"],
    "resume_claims_to_probe": ["improved accuracy by 18%"],
    "preparation_focus_areas": ["System design"],
}

FAKE_FIT = {
    "score_percent": 78,
    "strong_match": ["Python"],
    "partial_match": ["ML"],
    "missing_or_weak": ["Cloud"],
    "rationale": "Good fit overall.",
}

FAKE_REPORT = {
    "overall_score": 72,
    "competency_scores": [{"name": "Role Fit", "score": 70, "note": "ok"}],
    "strengths": ["Good Python fundamentals"],
    "weaknesses": ["Weak system design"],
    "preparation_gaps": [{"priority": 1, "topic": "System Design", "review_points": ["Scalability"]}],
    "readiness": "interview_ready",
    "readiness_label": "🟡 Interview Ready",
    "readiness_summary": "Solid candidate but needs system design prep.",
}


def _make_fake_chat_json():
    counter = itertools.count()

    def fake_chat_json(system_prompt: str, user_prompt: str, **kwargs):
        if "role analyst" in system_prompt:
            return FAKE_ROLE
        if "expert technical interviewer preparing" in system_prompt:
            return FAKE_RESUME
        if "scoring how well a candidate" in system_prompt:
            return FAKE_FIT
        if "compiling a final interview performance report" in system_prompt:
            return FAKE_REPORT
        n = next(counter)
        return {
            "answer_assessment": None if "N/A" in user_prompt else "Reasonable but lacked metrics",
            "answer_good_points": ["Clear structure"],
            "answer_improvement_points": ["Add numbers"],
            "answer_ideal_direction": "Should quantify impact",
            "answer_quality_score": 7,
            "next_question": f"Fake dynamic question #{n}",
            "next_question_topic_tag": f"topic_{n}",
            "is_followup_on_previous": False,
            "recommended_difficulty_after_this": "standard",
            "level_feels_sufficiently_covered": n % 3 == 2,
        }

    return fake_chat_json


@pytest.fixture()
def client():
    fake = _make_fake_chat_json()
    with patch("app.services.analysis_service.chat_json", side_effect=fake), patch(
        "app.services.interview_engine.chat_json", side_effect=fake
    ), patch("app.services.report_generator.chat_json", side_effect=fake):
        with TestClient(app) as c:
            yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["groq_key_configured"] is True


def test_analyze_requires_both_fields(client):
    r = client.post("/analyze", json={"jd_text": "", "resume_text": ""})
    assert r.status_code == 400


def test_analyze_creates_session(client):
    r = client.post(
        "/analyze",
        json={"jd_text": "AI Engineer Intern needing Python, RAG, APIs", "resume_text": "Built RAG chatbot"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["job_fit"]["score_percent"] == 78
    assert body["role_analysis"]["role_title"] == "AI Engineer Intern"
    assert body["session_id"]


def test_full_interview_reaches_completion_and_report(client):
    r = client.post(
        "/analyze",
        json={"jd_text": "AI Engineer Intern needing Python, RAG, APIs", "resume_text": "Built RAG chatbot"},
    )
    session_id = r.json()["session_id"]

    r = client.post("/interview/start", json={"session_id": session_id})
    assert r.status_code == 200
    assert r.json()["level"] == "screening"

    levels_seen = set()
    complete = False
    for i in range(25):
        r = client.post("/interview/answer", json={"session_id": session_id, "answer_text": f"Answer {i}"})
        assert r.status_code == 200
        data = r.json()
        levels_seen.add(data["level"])
        if data["interview_complete"]:
            complete = True
            break
    assert complete, "Interview should reach completion within 25 turns"
    assert levels_seen == {"screening", "competency", "deep_dive"}

    r = client.get(f"/interview/{session_id}/transcript")
    assert r.status_code == 200
    assert len(r.json()) >= 9  # at least min_questions_per_level * 3 levels

    r = client.post("/report", json={"session_id": session_id})
    assert r.status_code == 200
    report = r.json()
    assert report["overall_score"] == 72
    assert report["readiness"] == "interview_ready"
    assert len(report["question_feedback"]) == len(r_transcript := client.get(f"/interview/{session_id}/transcript").json())


def test_history_endpoint_lists_sessions(client):
    client.post("/analyze", json={"jd_text": "JD text here", "resume_text": "Resume text here"})
    r = client.get("/report/history/all")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_answer_without_starting_interview_returns_404(client):
    r = client.post("/interview/answer", json={"session_id": "does-not-exist", "answer_text": "hi"})
    assert r.status_code == 404


def test_empty_answer_rejected(client):
    r = client.post(
        "/analyze",
        json={"jd_text": "AI Engineer Intern needing Python, RAG, APIs", "resume_text": "Built RAG chatbot"},
    )
    session_id = r.json()["session_id"]
    client.post("/interview/start", json={"session_id": session_id})
    r = client.post("/interview/answer", json={"session_id": session_id, "answer_text": "   "})
    assert r.status_code == 400
