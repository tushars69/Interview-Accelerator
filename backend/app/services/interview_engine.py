"""
The core adaptive interview engine.

State machine per session:
    screening -> competency -> deep_dive -> complete

Each turn:
  1. If there's a pending question the candidate just answered, ask the LLM to
     (a) assess that answer, (b) decide the next question, (c) say whether this
     level feels sufficiently covered, and (d) recommend a difficulty adjustment.
  2. Persist the completed turn (question+answer+assessment) to the transcript.
  3. Decide, in code (not just the LLM), whether to advance to the next level:
       - never before `min_questions_per_level` questions in this level
       - always by `max_questions_per_level` questions in this level
       - otherwise, advance early if the LLM says the level is sufficiently covered
  4. If advancing (or deep_dive is finished), either regenerate an opening
     question for the new level, or mark the interview complete.

This keeps the *policy* (when to move on) deterministic and auditable, while
letting the LLM own the *judgement* (was this answer good, what should we ask
next, how hard should we push).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.groq_client import chat_json
from app.db.models import InterviewSession, InterviewTurn
from app.models.schemas import InterviewTurnResponse
from app.prompts import templates as t

LEVEL_ORDER = ["screening", "competency", "deep_dive"]
LEVEL_LABELS = {
    "screening": "Screening Interview",
    "competency": "Competency Interview",
    "deep_dive": "Deep-Dive Interview",
}

settings = get_settings()


def _transcript_text(turns: list[InterviewTurn], max_full_turns: int = 4) -> str:
    """
    Render the interview transcript for the prompt, capped to the most
    recent `max_full_turns` in full detail. Without this cap, the prompt
    grows linearly with every question asked and eventually exceeds Groq's
    per-request token budget outright (a 413 "Request too large" — no
    amount of retrying fixes an oversized single request, unlike a
    transient rate limit). Older turns are condensed to a one-line note;
    `topics_covered` and `claims_to_probe` (already in the system prompt)
    carry forward what's been covered so context isn't actually lost.
    """
    if not turns:
        return "(interview has not started yet)"

    recent = turns[-max_full_turns:]
    older_count = len(turns) - len(recent)

    lines: list[str] = []
    if older_count:
        lines.append(
            f"({older_count} earlier question(s) in this interview are omitted here to keep "
            f"the prompt size bounded — see 'topics already covered' and 'resume claims still "
            f"to probe' above for what's already been asked.)"
        )
        lines.append("")

    for i, turn in enumerate(recent, start=older_count + 1):
        lines.append(f"[{i}] ({LEVEL_LABELS.get(turn.level, turn.level)})")
        lines.append(f"Q: {turn.question}")
        if turn.answer:
            lines.append(f"A: {turn.answer}")
            if turn.assessment:
                lines.append(f"(assessed quality: {turn.answer_quality_score}/10 — {turn.assessment})")
        lines.append("")
    return "\n".join(lines)


def _call_llm_for_turn(
    session: InterviewSession,
    level: str,
    transcript_text: str,
    latest_answer: str | None,
) -> dict:
    # Cap topics_covered too — it also grows one tag per question across a
    # long interview and gets embedded in every prompt; last 10 is plenty
    # context for "don't repeat this topic" without unbounded growth.
    recent_topics = session.topics_covered[-10:] if session.topics_covered else []

    system_prompt = t.INTERVIEW_SYSTEM.format(
        level_label=LEVEL_LABELS[level],
        level_instructions=t.LEVEL_INSTRUCTIONS[level],
        role_analysis_json=str(session.role_analysis),
        resume_analysis_json=str(session.resume_analysis),
        claims_to_probe=str(session.claims_to_probe),
        topics_covered=str(recent_topics),
        difficulty=session.difficulty,
    )
    user_prompt = t.INTERVIEW_USER.format(
        transcript_text=transcript_text,
        latest_answer=latest_answer or "N/A (this is the opening question of this stage)",
    )
    return chat_json(system_prompt, user_prompt, temperature=0.5, max_tokens=2000)


def _to_response(session: InterviewSession, question_number_overall: int) -> InterviewTurnResponse:
    idx_in_level = session.questions_asked_this_level
    return InterviewTurnResponse(
        session_id=session.id,
        level=session.current_level,
        level_progress=f"Question {idx_in_level} of ~{settings.max_questions_per_level} — {LEVEL_LABELS[session.current_level]}",
        question=session.pending_question,
        question_number_overall=question_number_overall,
        difficulty=session.difficulty,
        interview_complete=session.interview_complete,
        topics_covered=session.topics_covered,
    )


def start_interview(db: Session, session: InterviewSession) -> InterviewTurnResponse:
    session.current_level = "screening"
    session.difficulty = "standard"
    session.questions_asked_this_level = 0
    session.topics_covered = []
    session.interview_complete = False

    result = _call_llm_for_turn(session, "screening", _transcript_text([]), latest_answer=None)

    session.pending_question = result["next_question"]
    session.questions_asked_this_level = 1
    session.topics_covered = [result.get("next_question_topic_tag", "opening")]
    db.commit()
    db.refresh(session)

    return _to_response(session, question_number_overall=1)


def submit_answer(db: Session, session: InterviewSession, answer_text: str) -> InterviewTurnResponse:
    if session.interview_complete:
        return _to_response(session, question_number_overall=len(session.turns))

    prior_turns = session.turns
    transcript_text = _transcript_text(prior_turns)
    level_being_answered = session.current_level

    result = _call_llm_for_turn(session, level_being_answered, transcript_text, latest_answer=answer_text)

    # Persist the just-answered turn
    new_turn = InterviewTurn(
        session_id=session.id,
        turn_index=len(prior_turns),
        level=level_being_answered,
        question=session.pending_question,
        answer=answer_text,
        assessment=result.get("answer_assessment") or "",
        good_points=result.get("answer_good_points") or [],
        improvement_points=result.get("answer_improvement_points") or [],
        ideal_direction=result.get("answer_ideal_direction") or "",
        answer_quality_score=int(result.get("answer_quality_score") or 0),
    )
    db.add(new_turn)

    # Update rolling performance score (simple EMA) — drives report context, not gating
    q_score = new_turn.answer_quality_score or 6
    session.performance_running_score = round(0.6 * session.performance_running_score + 0.4 * (q_score * 10))

    # Difficulty adapts from LLM recommendation
    session.difficulty = result.get("recommended_difficulty_after_this", session.difficulty)

    # Remove a probed claim from the outstanding list if this answer addressed it
    if session.claims_to_probe and level_being_answered != "screening":
        session.claims_to_probe = session.claims_to_probe[1:] if len(session.claims_to_probe) > 3 else session.claims_to_probe

    questions_so_far_in_level = session.questions_asked_this_level
    sufficiently_covered = bool(result.get("level_feels_sufficiently_covered"))
    should_advance = questions_so_far_in_level >= settings.max_questions_per_level or (
        questions_so_far_in_level >= settings.min_questions_per_level and sufficiently_covered
    )

    current_level_idx = LEVEL_ORDER.index(level_being_answered)
    is_last_level = current_level_idx == len(LEVEL_ORDER) - 1

    if should_advance and is_last_level:
        # Interview finished entirely
        session.interview_complete = True
        session.pending_question = ""
        db.commit()
        db.refresh(session)
        return _to_response(session, question_number_overall=len(session.turns))

    if should_advance:
        # Move to next level and generate a fresh opening question for it
        next_level = LEVEL_ORDER[current_level_idx + 1]
        session.current_level = next_level
        session.questions_asked_this_level = 0
        session.difficulty = "standard"
        db.commit()
        db.refresh(session)

        transcript_text = _transcript_text(session.turns)
        next_result = _call_llm_for_turn(session, next_level, transcript_text, latest_answer=None)
        session.pending_question = next_result["next_question"]
        session.questions_asked_this_level = 1
        session.topics_covered = session.topics_covered + [next_result.get("next_question_topic_tag", next_level)]
        db.commit()
        db.refresh(session)
        return _to_response(session, question_number_overall=len(session.turns) + 1)

    # Same level continues
    session.pending_question = result["next_question"]
    session.questions_asked_this_level = questions_so_far_in_level + 1
    session.topics_covered = session.topics_covered + [result.get("next_question_topic_tag", level_being_answered)]
    db.commit()
    db.refresh(session)
    return _to_response(session, question_number_overall=len(session.turns) + 1)
