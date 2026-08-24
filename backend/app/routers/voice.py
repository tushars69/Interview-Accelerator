from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.groq_client import GroqError
from app.services import voice_service

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")
    try:
        text = voice_service.speech_to_text(audio_bytes, filename=file.filename or "answer.wav")
    except GroqError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"text": text}


class SpeakRequest(BaseModel):
    text: str
    voice: str | None = None


@router.post("/speak")
def speak(request: SpeakRequest) -> Response:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text cannot be empty.")
    try:
        audio_bytes = voice_service.text_to_speech(request.text, voice=request.voice)
    except GroqError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=audio_bytes, media_type="audio/wav")
