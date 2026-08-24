# 🎯 AI Interview Accelerator

An AI-powered Interview Accelerator that takes a **Job Description + Resume** and turns
them into a fully personalised, adaptive, voice-based mock interview — followed by a
detailed performance report and preparation plan.

Built for the AI Product Engineer Intern — Interview Accelerator Challenge (Assignment 3).

---

## ✨ What it does

1. **Understands the role** — extracts responsibilities, required/preferred skills,
   competencies, keywords, and qualifications from a pasted or uploaded JD.
2. **Understands the candidate** — analyses the resume specifically against that JD:
   strengths, gaps, weak areas, and resume claims worth probing in the interview.
3. **Scores Job Fit** — a 0–100% match score with strong/partial/missing breakdowns.
4. **Runs a 3-level adaptive AI interview** — Screening → Competency → Deep-Dive —
   entirely by voice (speak the question, answer by mic), with questions generated
   dynamically from the transcript so far, not a fixed script.
5. **Generates a full performance report** — overall score, 7 competency scores,
   question-by-question feedback, strengths, weaknesses, a prioritised preparation
   plan, and a final readiness verdict (🔴/🟠/🟡/🟢).

---

## 🏗️ Architecture

```
interview-accelerator/
├── backend/                  FastAPI service — all intelligence lives here
│   └── app/
│       ├── core/              config + the single Groq client wrapper
│       ├── models/            Pydantic schemas (API contracts)
│       ├── prompts/           every LLM prompt template, centralised
│       ├── services/          analysis, interview engine, voice, reporting
│       ├── db/                SQLAlchemy models + SQLite persistence
│       ├── routers/           /analyze  /interview  /voice  /report
│       └── main.py            FastAPI app entrypoint
├── frontend/                  Streamlit UI — presentation + orchestration only
│   ├── streamlit_app.py       5 screens: Dashboard → Role → Candidate → Interview → Results
│   └── utils/                 api_client.py (HTTP calls), styling.py (custom theme)
└── pyproject.toml             single Poetry project for both services
```

**Why FastAPI + Streamlit, not one framework:** the backend is the part that needs to
be correct, testable, and stateful (interview logic, DB, prompt engineering) — Streamlit
is not a good place for that. Keeping it as a real REST API also means the same backend
could power a React frontend, a CLI, or a recruiter dashboard later without any changes.

---

## 🤖 AI / LLM approach

Everything runs on **Groq** — one API key gives you a chat/reasoning model, Whisper
speech-to-text, and PlayAI text-to-speech, which kept the stack to a single provider.

- **Chat/reasoning:** `llama-3.3-70b-versatile` for analysis, interview turns, and the
  final report (70B for reasoning quality on multi-step judgement tasks); a smaller
  `llama-3.1-8b-instant` is wired in as a configurable "fast" model if you want to trade
  quality for latency anywhere.
- **Structured output:** every analytical call uses Groq's `response_format:
  {"type": "json_object"}` and a strict schema in the system prompt, parsed straight
  into Pydantic models — no regex-scraping of free text.
- **Prompt design:** all prompts live in `backend/app/prompts/templates.py`. Each one is
  explicitly given the *actual* JD/resume/transcript content and told what "personalised,
  not generic" means with a concrete before/after example — this is what stops the model
  from defaulting to "Tell me about yourself."

## 🎙️ Voice implementation

- **Speech-to-text:** the browser records the candidate's answer via Streamlit's native
  `st.audio_input` mic widget (no extra JS needed) → the WAV bytes are POSTed to
  `/voice/transcribe` → Groq Whisper (`whisper-large-v3-turbo`) returns the transcript,
  which is shown back to the candidate as an **editable** text box before submitting
  (so a bad transcription never silently corrupts an answer).
- **Text-to-speech:** each new interview question is sent to `/voice/speak` → Groq's
  PlayAI TTS model returns WAV audio → played back in the browser with `st.audio(...,
  autoplay=True)`, so the question is spoken the moment it appears.
- **Fallback:** a "Voice mode" toggle in the sidebar lets you switch to pure text
  (typed answers) instantly — useful for demoing without a working mic, or for
  accessibility.

## 🧠 Dynamic questioning logic

The interview is a small state machine (`backend/app/services/interview_engine.py`)
layered under an LLM that owns the judgement calls:

```
screening → competency → deep_dive → complete
```

On every turn, the LLM is given: the JD analysis, the resume analysis, the **full
transcript so far**, the topics already covered, resume claims still to probe, and the
current adaptive difficulty — then asked, in one JSON call, to:

1. Assess the previous answer (good points / gaps / an ideal-answer direction / a 0–10 score).
2. Decide the next question — following up on a weak/vague answer, probing an unverified
   resume claim, or moving to a new relevant topic — always referencing something
   specific from the candidate's actual background.
3. Recommend a difficulty adjustment (`easy` / `standard` / `hard`) for the next question.
4. Flag whether this interview level feels sufficiently covered.

**The level-transition policy itself is deterministic code, not left to the LLM:**
never advance before `MIN_QUESTIONS_PER_LEVEL`, always advance by
`MAX_QUESTIONS_PER_LEVEL`, and advance early only if both the minimum is met *and* the
LLM says the level is sufficiently covered. This keeps interview length predictable
while still letting the AI decide *when it's actually ready* to move on — e.g. it will
stay in Deep-Dive longer if you keep giving vague answers to "how did you measure that?"

## 📊 Evaluation methodology

- Each answer gets an immediate 0–10 quality score and structured feedback at the time
  it's given (stored on the transcript turn) — so feedback is grounded in what actually
  happened, not reconstructed after the fact.
- At the end, a single report-generation call receives the **entire scored transcript**
  plus the original JD/resume/fit analysis, and produces: an overall 0–100 score, 7
  competency scores (Role Fit, Technical Knowledge, Problem Solving, Communication,
  Confidence, Depth of Understanding, Behavioural Fit), strengths, weaknesses, and a
  prioritised preparation plan.
- Question-level feedback in the report is **not** re-generated by the LLM — it's pulled
  directly from the per-turn assessments captured during the interview, guaranteeing the
  report can't contradict what was actually said.
- Readiness is threshold-based off `overall_score` (< 40 Not Ready, 40–59 Needs
  Preparation, 60–79 Interview Ready, 80+ Strong Candidate) so the label is always
  consistent with the number shown next to it.

## 🔑 Key technical decisions

- **One provider (Groq), three capabilities** — simplest possible setup for the person
  running this: one API key, no juggling OpenAI + a separate TTS vendor + a separate STT vendor.
- **SQLite via SQLAlchemy** for session/transcript/report persistence — gives real
  interview history (bonus feature, visible in the sidebar) with zero infra setup.
- **Deterministic level-transition policy wrapping LLM judgement** (see above) — the
  single biggest reliability lever for an assignment that's graded partly on "does the
  complete flow actually work."
- **Editable STT transcript before submission** — protects the interview from a single
  bad transcription derailing the adaptive logic.
- **All prompts centralised in one file** — makes the AI behaviour auditable and easy to
  tune without touching business logic.

---

## 🚀 Setup & running locally

### 1. Install dependencies

```bash
# From the project root
poetry install
```

(No Poetry? `pip install -r requirements.txt` works too — see below.)

### 2. Add your Groq API key

```bash
cp backend/.env.example backend/.env
# then edit backend/.env and paste your key from https://console.groq.com/keys
```

### 3. Run the backend (terminal 1)

```bash
cd backend
poetry run uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive API docs.

### 4. Run the frontend (terminal 2)

```bash
cd frontend
poetry run streamlit run streamlit_app.py
```

Visit `http://localhost:8501`.

> If your backend runs somewhere other than `localhost:8000`, set
> `BACKEND_URL=http://your-host:port` before launching Streamlit.

### Without Poetry

```bash
pip install fastapi "uvicorn[standard]" python-multipart pydantic pydantic-settings \
    python-dotenv groq sqlalchemy pdfplumber python-docx requests streamlit \
    streamlit-lottie plotly pandas
```
then run the same two commands above with `python -m uvicorn ...` / `python -m streamlit ...`.

---

## 🗺️ User journey

Upload/paste JD → Upload/paste Resume → Role Analysis → Candidate Analysis + Job Fit
→ Start Interview → Screening → Competency → Deep-Dive (voice throughout, adaptive
difficulty) → Performance Report → Preparation Plan → Readiness Score.

## 🎁 Bonus features implemented

- AI-generated prioritised preparation plan
- Interview history sidebar (across sessions, persisted in SQLite)
- Adaptive question difficulty based on running performance
- Editable live transcription (real-time-feeling STT correction)
- File upload for JD/Resume (PDF, DOCX, TXT) in addition to paste
- Fallback text-based interview mode alongside voice

## 📌 Not yet implemented (left as future work)

- Video interview / webcam capture (explicitly a bonus in the brief; this submission
  focuses on a strong voice-first implementation instead, as the brief recommends).
- Live deployment — this repo is ready to deploy as-is (FastAPI backend + Streamlit
  frontend, both stateless besides SQLite) to any host that runs Python; deploying it
  requires your own hosting account so it isn't done in this build.
