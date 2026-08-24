"""Thin service layer over the Groq STT/TTS calls, kept separate from
core.groq_client so routers never import the SDK-facing module directly."""
from __future__ import annotations

from app.core.groq_client import synthesize_speech, transcribe_audio


def speech_to_text(audio_bytes: bytes, filename: str = "answer.wav") -> str:
    return transcribe_audio(audio_bytes, filename=filename)


def text_to_speech(text: str, voice: str | None = None) -> bytes:
    return synthesize_speech(text, voice=voice)
