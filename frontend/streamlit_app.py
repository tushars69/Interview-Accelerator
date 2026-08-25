"""
AI Interview Accelerator — Streamlit frontend.

Screens (driven by st.session_state.stage):
    dashboard -> role_analysis -> candidate_analysis -> interview -> results

Talks to the FastAPI backend (see ../backend) for every piece of intelligence;
this file is presentation + orchestration only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

sys.path.append(str(Path(__file__).parent))
from utils import api_client as api
from utils.styling import ACCENT, DANGER, PRIMARY, SUCCESS, WARNING, chips, hero, inject_custom_css, stepper

st.set_page_config(
    page_title="Interview Accelerator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_custom_css()

DEFAULTS = {
    "stage": "dashboard",
    "session_id": None,
    "role_analysis": None,
    "resume_analysis": None,
    "job_fit": None,
    "current_turn": None,
    "interview_log": [],
    "report": None,
    "last_question_audio": None,
    "last_spoken_question": None,
    "_tts_quota_exhausted": False,
    "voice_mode": True,
    "video_mode": False,
}
for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


def reset_all() -> None:
    for key, default in DEFAULTS.items():
        st.session_state[key] = default


def goto_stage(stage: str) -> None:
    st.session_state.stage = stage
    st.rerun()


# ---------------------------------------------------------------------------
# Sidebar — backend status, history, restart
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎯 Interview Accelerator")
    st.caption("AI-powered interview prep, built on Groq.")

    try:
        health = api.health_check()
        if health.get("groq_key_configured"):
            st.success("Backend connected · Groq key detected", icon="✅")
        else:
            st.warning("Backend connected, but GROQ_API_KEY is missing.", icon="⚠️")
    except Exception:  # noqa: BLE001
        st.error("Backend not reachable at " + api.BACKEND_URL, icon="🔴")
        st.caption("Start it with: `poetry run uvicorn app.main:app --reload` from `backend/`.")

    st.markdown("---")
    st.session_state.voice_mode = st.toggle("🎙️ Voice mode", value=st.session_state.voice_mode)
    st.caption("When on, the AI speaks questions aloud and you can answer by mic.")

    st.session_state.video_mode = st.toggle("📹 Video mode", value=st.session_state.video_mode)
    st.caption("Shows your live camera next to the AI interviewer during the interview")
    st.markdown("---")
    if st.button("🔄 Start a new candidate", use_container_width=True):
        reset_all()
        st.rerun()

    st.markdown("---")
    st.markdown("#### 📚 Interview History")
    try:
        history = api.get_history()
        if not history:
            st.caption("No interviews yet.")
        for h in history[:6]:
            score = h.get("overall_score")
            score_str = f"{score}/100" if score is not None else "in progress"
            st.markdown(
                f"**{h.get('role_title', 'Role')}**  \n"
                f"Fit {h.get('job_fit_percent', '–')}% · Score {score_str}"
            )
            st.caption(h.get("readiness_label") or "")
    except Exception:  # noqa: BLE001
        st.caption("History unavailable (backend offline).")


# ---------------------------------------------------------------------------
# Screen: Dashboard — JD + Resume input
# ---------------------------------------------------------------------------
def render_dashboard() -> None:
    hero(
        "AI Interview Accelerator",
        "Paste or upload your Job Description and Resume — the AI will analyse the role, "
        "score your fit, and run a full adaptive mock interview with voice.",
    )
    stepper("dashboard")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown('<div class="card"><h4>📄 Job Description</h4>', unsafe_allow_html=True)
        jd_file = st.file_uploader("Upload JD file", type=["pdf", "docx", "txt"], key="jd_file")
        if jd_file is not None:
            file_sig = f"{jd_file.name}_{jd_file.size}"
            if st.session_state.get("_jd_file_sig") != file_sig:
                try:
                    extracted = api.extract_text_from_file(jd_file.name, jd_file.getvalue())
                    st.session_state["_jd_file_sig"] = file_sig
                    st.session_state["jd_text_area"] = extracted  # populate the text box directly
                    st.success(f"Extracted {len(extracted)} characters from {jd_file.name}")
                except api.ApiError as e:
                    st.error(f"Could not read file: {e}")
        jd_text = st.text_area(
            "...or paste the Job Description here",
            height=220,
            key="jd_text_area",
            placeholder="Paste the full job description text...",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card"><h4>📋 Your Resume</h4>', unsafe_allow_html=True)
        resume_file = st.file_uploader("Upload Resume file", type=["pdf", "docx", "txt"], key="resume_file")
        if resume_file is not None:
            file_sig = f"{resume_file.name}_{resume_file.size}"
            if st.session_state.get("_resume_file_sig") != file_sig:
                try:
                    extracted = api.extract_text_from_file(resume_file.name, resume_file.getvalue())
                    st.session_state["_resume_file_sig"] = file_sig
                    st.session_state["resume_text_area"] = extracted  # populate the text box directly
                    st.success(f"Extracted {len(extracted)} characters from {resume_file.name}")
                except api.ApiError as e:
                    st.error(f"Could not read file: {e}")
        resume_text = st.text_area(
            "...or paste your Resume here",
            height=220,
            key="resume_text_area",
            placeholder="Paste your full resume text...",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.session_state.jd_text = jd_text
    st.session_state.resume_text = resume_text

    st.write("")
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        disabled = not (jd_text and jd_text.strip() and resume_text and resume_text.strip())
        if st.button("🚀 Analyse Role & Resume", use_container_width=True, disabled=disabled):
            with st.spinner("Analysing job description and resume with AI..."):
                try:
                    result = api.analyze(jd_text, resume_text)
                except api.ApiError as e:
                    st.error(f"Analysis failed: {e}")
                    return
            st.session_state.session_id = result["session_id"]
            st.session_state.role_analysis = result["role_analysis"]
            st.session_state.resume_analysis = result["resume_analysis"]
            st.session_state.job_fit = result["job_fit"]
            goto_stage("role_analysis")
        if disabled:
            st.caption("Add both a Job Description and a Resume to continue.")


# ---------------------------------------------------------------------------
# Screen: Role Analysis (Step 1)
# ---------------------------------------------------------------------------
def render_role_analysis() -> None:
    hero("Step 1 · Understanding the Role", "Here's what the AI extracted from the Job Description.")
    stepper("role_analysis")

    ra = st.session_state.role_analysis
    if not ra:
        st.warning("No analysis found — start from the dashboard.")
        if st.button("← Back to Dashboard"):
            goto_stage("dashboard")
        return

    st.markdown(
        f'<div class="card"><h4>🧭 {ra.get("role_title", "Role")}</h4>'
        f'<p>{ra.get("seniority_level", "")} · {ra.get("experience_expectations", "")}</p></div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="card"><h4>✅ Required Skills</h4>' + chips(ra.get("required_skills", [])) + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>⭐ Preferred Skills</h4>' + chips(ra.get("preferred_skills", [])) + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>🛠️ Technical Competencies</h4>' + chips(ra.get("technical_competencies", [])) + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>🤝 Behavioural Competencies</h4>' + chips(ra.get("behavioural_competencies", [])) + "</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card"><h4>📌 Key Responsibilities</h4>', unsafe_allow_html=True)
        for item in ra.get("key_responsibilities", []):
            st.markdown(f"- {item}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card"><h4>🔑 Important Keywords</h4>' + chips(ra.get("important_keywords", [])) + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>💡 Important Concepts</h4>' + chips(ra.get("important_concepts", [])) + "</div>", unsafe_allow_html=True)

        st.markdown('<div class="card"><h4>🎓 Key Qualifications</h4>', unsafe_allow_html=True)
        for item in ra.get("key_qualifications", []):
            st.markdown(f"- {item}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Back", use_container_width=True):
            goto_stage("dashboard")
    with c2:
        if st.button("Continue to Candidate Fit →", use_container_width=True):
            goto_stage("candidate_analysis")


# ---------------------------------------------------------------------------
# Screen: Candidate Analysis + Job Fit (Step 2)
# ---------------------------------------------------------------------------
def fit_gauge(score: int) -> go.Figure:
    color = SUCCESS if score >= 75 else WARNING if score >= 50 else DANGER
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "%", "font": {"size": 44, "color": "white"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "white"},
                "bar": {"color": color},
                "bgcolor": "rgba(255,255,255,0.05)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 50], "color": "rgba(255,107,107,0.15)"},
                    {"range": [50, 75], "color": "rgba(253,203,110,0.15)"},
                    {"range": [75, 100], "color": "rgba(0,184,148,0.15)"},
                ],
            },
        )
    )
    fig.update_layout(
        height=260,
        margin=dict(l=20, r=20, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
    )
    return fig


def render_candidate_analysis() -> None:
    hero("Step 2 · Understanding You", "Your resume, benchmarked directly against this role.")
    stepper("candidate_analysis")

    resa = st.session_state.resume_analysis
    fit = st.session_state.job_fit
    if not resa or not fit:
        st.warning("No analysis found — start from the dashboard.")
        if st.button("← Back to Dashboard"):
            goto_stage("dashboard")
        return

    col1, col2 = st.columns([1, 1.3], gap="large")
    with col1:
        st.markdown('<div class="card"><h4>🎯 Your Job Fit</h4>', unsafe_allow_html=True)
        st.plotly_chart(fit_gauge(fit.get("score_percent", 0)), use_container_width=True, config={"displayModeBar": False})
        st.caption(fit.get("rationale", ""))
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card"><h4>🟢 Strong Match</h4>' + chips(fit.get("strong_match", []), "strong") + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>🟡 Partial Match</h4>' + chips(fit.get("partial_match", []), "partial") + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>🔴 Missing / Weak</h4>' + chips(fit.get("missing_or_weak", []), "missing") + "</div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2, gap="large")
    with col3:
        st.markdown('<div class="card"><h4>💪 Strengths vs JD</h4>' + chips(resa.get("strengths_vs_jd", []), "strong") + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>🚀 Relevant Projects</h4>', unsafe_allow_html=True)
        for item in resa.get("relevant_projects", []):
            st.markdown(f"- {item}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="card"><h4>⚠️ Weak / Insufficient Areas</h4>' + chips(resa.get("weak_or_insufficient_areas", []), "missing") + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>🔍 Claims We\'ll Probe In The Interview</h4>', unsafe_allow_html=True)
        for item in resa.get("resume_claims_to_probe", []):
            st.markdown(f"- {item}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Back", use_container_width=True):
            goto_stage("role_analysis")
    with c2:
        if st.button("🎤 Start AI Interview →", use_container_width=True):
            with st.spinner("Preparing your personalised interview..."):
                try:
                    turn = api.start_interview(st.session_state.session_id)
                except api.ApiError as e:
                    st.error(f"Could not start interview: {e}")
                    return
            st.session_state.current_turn = turn
            st.session_state.interview_log = []
            goto_stage("interview")


# ---------------------------------------------------------------------------
# Screen: Interview (Steps 3-9)
# ---------------------------------------------------------------------------
LEVEL_LABELS = {"screening": "Screening Interview", "competency": "Competency Interview", "deep_dive": "Deep-Dive Interview"}
DIFFICULTY_EMOJI = {"easy": "🟢 Easier", "standard": "🟡 Standard", "hard": "🔴 Harder"}


def render_video_panel() -> None:
    """
    Cosmetic video-call UI: a live self-view of the candidate's camera next
    to a simple animated 'AI Interviewer' panel. Pure browser-side — the
    video never leaves the page, nothing is recorded/uploaded/analysed, so
    this has zero effect on any Groq API quota.

    Requires a secure context (localhost or https) for camera permission,
    same restriction as the microphone used elsewhere in this app.
    """
    html = """
    <div class="video-panel-wrap">
      <div class="ai-interviewer-panel">
        <div style="width:64px; height:64px; border-radius:50%; background:rgba(255,255,255,0.08);
                    display:flex; align-items:center; justify-content:center; font-size:32px;
                    animation:pulseGlow 2.2s ease-in-out infinite;">🤖</div>
        <div style="color:#EDEBFF; font-weight:600; margin-top:10px; font-size:0.92rem;">AI Interviewer</div>
        <div style="display:flex; align-items:center; gap:6px; margin-top:4px;">
          <span style="width:7px; height:7px; border-radius:50%; background:#00CEC9; display:inline-block;
                       animation:blink 1.6s ease-in-out infinite;"></span>
          <span style="color:#9BF6DF; font-size:0.75rem;">Live</span>
        </div>
      </div>
      <div class="candidate-video-panel">
        <video id="candidateSelfView" autoplay playsinline muted></video>
        <div id="camStatus"></div>
      </div>
    </div>
    <style>
      html, body { margin:0; padding:0; }
      .video-panel-wrap {
        display:flex; flex-wrap:wrap; gap:14px; font-family:'Inter',sans-serif;
        width:100%; box-sizing:border-box;
      }
      .ai-interviewer-panel {
        flex:1 1 240px; background:linear-gradient(135deg, rgba(108,92,231,0.25), rgba(0,206,201,0.15));
        border:1px solid rgba(108,92,231,0.4); border-radius:16px; padding:18px;
        display:flex; flex-direction:column; align-items:center; justify-content:center;
        aspect-ratio:16/9; box-sizing:border-box;
      }
      .candidate-video-panel {
        flex:1 1 240px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.1);
        border-radius:16px; padding:8px; display:flex; align-items:center; justify-content:center;
        overflow:hidden; position:relative; aspect-ratio:16/9; box-sizing:border-box;
      }
      .candidate-video-panel video {
        width:100%; height:100%; object-fit:cover; border-radius:12px; background:#0A0A12;
      }
      #camStatus {
        position:absolute; bottom:14px; left:14px; color:#FFB3B3;
        font-size:0.78rem; font-family:'Inter',sans-serif;
      }
      @media (max-width: 480px) {
        .ai-interviewer-panel, .candidate-video-panel { flex-basis:100%; aspect-ratio:4/3; }
      }
      @keyframes pulseGlow {
        0%, 100% { box-shadow: 0 0 0 0 rgba(0,206,201,0.35); }
        50% { box-shadow: 0 0 0 10px rgba(0,206,201,0); }
      }
      @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
      }
    </style>
    <script>
      (function() {
        const statusEl = document.getElementById('camStatus');
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          statusEl.innerText = 'Camera needs localhost or https to work.';
          return;
        }
        navigator.mediaDevices.getUserMedia({ video: true, audio: false })
          .then(function(stream) {
            const video = document.getElementById('candidateSelfView');
            video.srcObject = stream;
          })
          .catch(function(err) {
            statusEl.innerText = 'Camera unavailable: ' + err.message;
          });
      })();
    </script>
    """
    components.html(html, height=280)

    question = turn["question"]
    st.markdown(f'<div class="ai-question">🤖 <b>Interviewer:</b> {question}</div>', unsafe_allow_html=True)

    # --- Voice: speak the question aloud (once per new question). If TTS
    # hit a hard quota (daily/rate limit), stop retrying for the rest of the
    # session instead of showing the same error on every single question —
    # STT (recording your answer) uses a separate quota and is unaffected. ---
    tts_quota_exhausted = st.session_state.get("_tts_quota_exhausted", False)

    if (
        st.session_state.voice_mode
        and not tts_quota_exhausted
        and st.session_state.last_spoken_question != question
        and st.session_state.get("_tts_failed_for") != question
    ):
        try:
            audio_bytes = api.speak_text(question)
            st.session_state.last_question_audio = audio_bytes
            st.session_state.last_spoken_question = question
        except api.ApiError as e:
            st.session_state.last_question_audio = None
            st.session_state["_tts_failed_for"] = question  # don't retry this same question again
            error_text = str(e).lower()
            if "tokens per day" in error_text or "rate_limit_exceeded" in error_text:
                st.session_state["_tts_quota_exhausted"] = True
                st.info(
                    "🔇 Today's voice-output quota has been used up — questions will show as text "
                    "only for the rest of this session (you can still record your answers by mic). "
                    "This resets automatically; toggle Voice mode off/on later to check."
                )
            else:
                st.warning(f"Voice synthesis unavailable ({e}) — you can still answer by text.")

    if st.session_state.voice_mode and st.session_state.last_question_audio:
        st.audio(st.session_state.last_question_audio, format="audio/wav", autoplay=True)

    st.markdown("#### Your Answer")
    answer_key = f"answer_box_{turn['question_number_overall']}"

    if st.session_state.voice_mode:
        audio_value = st.audio_input(
            "🎙️ Record your answer",
            key=f"audio_input_{turn['question_number_overall']}",  # fresh recorder widget per question
        )
        st.caption("Click the mic to start, click it again (now showing ⏹️) to stop and auto-transcribe.")
        if audio_value is not None:
            audio_bytes = audio_value.getvalue()
            audio_sig = f"{len(audio_bytes)}_{hash(audio_bytes) & 0xffffffff}"
            if st.session_state.get("_last_audio_sig") != audio_sig:
                with st.spinner("Transcribing your answer..."):
                    try:
                        transcribed = api.transcribe_audio("answer.wav", audio_bytes)
                        st.session_state["_last_audio_sig"] = audio_sig
                        st.session_state[answer_key] = transcribed  # populate the text box directly
                    except api.ApiError as e:
                        st.error(f"Transcription failed: {e}")

    answer_text = st.text_area(
        "Transcript (edit if needed, or just type your answer here instead of using voice)",
        height=140,
        key=answer_key,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        submit = st.button("✅ Submit Answer", use_container_width=True, disabled=not answer_text.strip())
    with col2:
        skip = st.button("⏭️ Skip Question", use_container_width=True)

    if submit or skip:
        final_answer = answer_text.strip() if submit else "(candidate skipped this question)"
        with st.spinner("AI is evaluating your answer and preparing the next question..."):
            try:
                new_turn = api.submit_answer(st.session_state.session_id, final_answer)
            except api.ApiError as e:
                st.error(f"Could not submit answer: {e}")
                return
        st.session_state.interview_log.append({"level": level, "question": question, "answer": final_answer})
        st.session_state.current_turn = new_turn
        st.session_state.last_question_audio = None
        st.session_state.pop("_tts_failed_for", None)

        if new_turn["interview_complete"]:
            with st.spinner("Generating your performance report..."):
                try:
                    report = api.generate_report(st.session_state.session_id)
                    st.session_state.report = report
                except api.ApiError as e:
                    st.error(f"Report generation failed: {e}")
                    return
            goto_stage("results")
        else:
            st.rerun()

    if st.session_state.interview_log:
        with st.expander(f"📝 Transcript so far ({len(st.session_state.interview_log)} answered)"):
            for i, turn_log in enumerate(st.session_state.interview_log, start=1):
                st.markdown(f"**Q{i} ({LEVEL_LABELS.get(turn_log['level'], turn_log['level'])}):** {turn_log['question']}")
                st.markdown(f"*Your answer:* {turn_log['answer']}")
                st.markdown("---")


# ---------------------------------------------------------------------------
# Screen: Results (Step 4)
# ---------------------------------------------------------------------------
READINESS_COLOR = {
    "not_ready": DANGER,
    "needs_preparation": WARNING,
    "interview_ready": ACCENT,
    "strong_candidate": SUCCESS,
}


def competency_radar(scores: list[dict]) -> go.Figure:
    names = [s["name"] for s in scores]
    values = [s["score"] for s in scores]
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(r=values + [values[0]], theta=names + [names[0]], fill="toself", line=dict(color=PRIMARY))
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], color="white"),
            bgcolor="rgba(0,0,0,0)",
            angularaxis=dict(color="white"),
        ),
        showlegend=False,
        height=380,
        margin=dict(l=40, r=40, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
    )
    return fig


def render_results() -> None:
    hero("Your Interview Performance Report", "A full breakdown of how you did, and exactly what to prepare next.")
    stepper("results")

    report = st.session_state.report
    if not report:
        st.warning("No report available yet.")
        if st.button("← Back to Dashboard"):
            goto_stage("dashboard")
        return

    color = READINESS_COLOR.get(report["readiness"], PRIMARY)
    st.markdown(
        f'<div class="readiness-banner" style="border-color:{color}; color:{color};">'
        f'{report["readiness_label"]}</div>',
        unsafe_allow_html=True,
    )
    st.caption(report.get("readiness_summary", ""))

    col1, col2 = st.columns([1, 1.4], gap="large")
    with col1:
        st.markdown('<div class="card"><h4>🏆 Overall Score</h4>', unsafe_allow_html=True)
        st.plotly_chart(fit_gauge(report["overall_score"]), use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card"><h4>📊 Competency Breakdown</h4>', unsafe_allow_html=True)
        st.plotly_chart(competency_radar(report["competency_scores"]), use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2, gap="large")
    with col3:
        st.markdown('<div class="card"><h4>💪 Strengths</h4>', unsafe_allow_html=True)
        for s in report.get("strengths", []):
            st.markdown(f"- {s}")
        st.markdown("</div>", unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="card"><h4>⚠️ Weaknesses</h4>', unsafe_allow_html=True)
        for w in report.get("weaknesses", []):
            st.markdown(f"- {w}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card"><h4>🗂️ Preparation Plan</h4>', unsafe_allow_html=True)
    for gap in sorted(report.get("preparation_gaps", []), key=lambda g: g["priority"]):
        st.markdown(f"**Priority {gap['priority']} — {gap['topic']}**")
        for point in gap.get("review_points", []):
            st.markdown(f"  - {point}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### 🔎 Question-by-Question Feedback")
    for i, qf in enumerate(report.get("question_feedback", []), start=1):
        with st.expander(f"Q{i}: {qf['question'][:90]}{'...' if len(qf['question']) > 90 else ''}"):
            st.markdown(f"**Your answer:** {qf['answer']}")
            st.markdown(f"**Assessment:** {qf['assessment']}")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**✅ What was good**")
                for g in qf.get("what_was_good", []):
                    st.markdown(f"- {g}")
            with c2:
                st.markdown("**🔧 What could be better**")
                for b in qf.get("what_could_be_better", []):
                    st.markdown(f"- {b}")
            st.info(f"**Ideal direction:** {qf['ideal_direction']}")

    st.write("")
    if st.button("🔄 Start a New Interview", use_container_width=True):
        reset_all()
        st.rerun()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
STAGE_RENDERERS = {
    "dashboard": render_dashboard,
    "role_analysis": render_role_analysis,
    "candidate_analysis": render_candidate_analysis,
    "interview": render_interview,
    "results": render_results,
}
STAGE_RENDERERS.get(st.session_state.stage, render_dashboard)()