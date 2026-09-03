"""Thin wrapper around `requests` calls to the FastAPI backend so the
Streamlit UI code never constructs raw HTTP calls inline."""
from __future__ import annotations

import os

import requests
import streamlit as st


def _get_backend_url() -> str:
    # Streamlit Cloud "Secrets" values land in st.secrets, NOT in os.environ,
    # so check secrets first and fall back to a real env var, then localhost.
    try:
        if "BACKEND_URL" in st.secrets:
            return st.secrets["BACKEND_URL"]
    except Exception:
        pass
    return os.environ.get("BACKEND_URL", "http://localhost:8000")


BACKEND_URL = _get_backend_url()
TIMEOUT = 90  # LLM calls (esp. analysis + report) can take a little while


class ApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _raise_for_status(resp: requests.Response) -> None:
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:  # noqa: BLE001
            detail = resp.text
        raise ApiError(str(detail), status_code=resp.status_code)


def health_check() -> dict:
    resp = requests.get(f"{BACKEND_URL}/health", timeout=10)
    _raise_for_status(resp)
    return resp.json()


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    resp = requests.post(
        f"{BACKEND_URL}/analyze/extract-text",
        files={"file": (filename, file_bytes)},
        timeout=TIMEOUT,
    )
    _raise_for_status(resp)
    return resp.json()["text"]


def analyze(jd_text: str, resume_text: str) -> dict:
    resp = requests.post(
        f"{BACKEND_URL}/analyze",
        json={"jd_text": jd_text, "resume_text": resume_text},
        timeout=TIMEOUT,
    )
    _raise_for_status(resp)
    return resp.json()


def start_interview(session_id: str) -> dict:
    resp = requests.post(f"{BACKEND_URL}/interview/start", json={"session_id": session_id}, timeout=TIMEOUT)
    _raise_for_status(resp)
    return resp.json()


def submit_answer(session_id: str, answer_text: str) -> dict:
    resp = requests.post(
        f"{BACKEND_URL}/interview/answer",
        json={"session_id": session_id, "answer_text": answer_text},
        timeout=TIMEOUT,
    )
    _raise_for_status(resp)
    return resp.json()


def get_transcript(session_id: str) -> list[dict]:
    resp = requests.get(f"{BACKEND_URL}/interview/{session_id}/transcript", timeout=TIMEOUT)
    _raise_for_status(resp)
    return resp.json()


def transcribe_audio(filename: str, audio_bytes: bytes) -> str:
    resp = requests.post(
        f"{BACKEND_URL}/voice/transcribe",
        files={"file": (filename, audio_bytes, "audio/wav")},
        timeout=TIMEOUT,
    )
    _raise_for_status(resp)
    return resp.json()["text"]


def speak_text(text: str, voice: str | None = None) -> bytes:
    payload = {"text": text}
    if voice:
        payload["voice"] = voice
    resp = requests.post(f"{BACKEND_URL}/voice/speak", json=payload, timeout=TIMEOUT)
    _raise_for_status(resp)
    return resp.content


def generate_report(session_id: str) -> dict:
    resp = requests.post(f"{BACKEND_URL}/report", json={"session_id": session_id}, timeout=TIMEOUT)
    _raise_for_status(resp)
    return resp.json()


def get_history() -> list[dict]:
    resp = requests.get(f"{BACKEND_URL}/report/history/all", timeout=TIMEOUT)
    _raise_for_status(resp)
    return resp.json()