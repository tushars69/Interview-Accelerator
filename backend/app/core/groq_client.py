"""
Single choke point for every call out to Groq.

Keeping all three capabilities (chat, STT, TTS) behind one client makes it
trivial to swap providers later (e.g. OpenAI/Gemini) — every service module
in app/services only ever talks to this file, never to the `groq` package
directly.
"""
from __future__ import annotations

import json
import logging
import re
import time
import wave
from io import BytesIO
from typing import Any

from groq import APIConnectionError, Groq, RateLimitError

from app.core.config import get_settings

logger = logging.getLogger("interview_accelerator.groq")

_settings = get_settings()
_client: Groq | None = None


def get_client() -> Groq:
    global _client
    if _client is None:
        if not _settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy backend/.env.example to backend/.env "
                "and add your key from https://console.groq.com/keys"
            )
        _client = Groq(api_key=_settings.groq_api_key)
    return _client


class GroqError(RuntimeError):
    """Raised when a Groq call fails or returns something unusable."""


def _extract_json(raw: str) -> dict[str, Any]:
    """
    LLMs occasionally wrap JSON in markdown fences or add stray preamble
    even when told not to. This strips that defensively before parsing.
    """
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the widest {...} span
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _supports_reasoning_effort(model_name: str) -> bool:
    """gpt-oss and qwen3 model families accept reasoning_effort; others error on it."""
    return "gpt-oss" in model_name or "qwen3" in model_name


def _unexpected_kwarg_from_error(exc: TypeError) -> str | None:
    """Parses '...got an unexpected keyword argument 'x'' out of a TypeError
    message so the caller knows exactly which kwarg to drop and retry
    without, rather than guessing."""
    match = re.search(r"unexpected keyword argument '(\w+)'", str(exc))
    return match.group(1) if match else None


def _seconds_to_wait(exc: RateLimitError, default: float = 20.0) -> float:
    """
    Groq's 429 message includes the exact wait time, e.g. "Please try again
    in 15.46s". Parse it so we wait exactly as long as needed rather than a
    blind guess — falls back to `default` if the message format changes.
    """
    message = str(exc)
    match = re.search(r"try again in ([\d.]+)s", message)
    if match:
        return float(match.group(1)) + 0.5  # small safety margin
    return default


def _call_with_rate_limit_retry(fn, *, max_retries: int = 2):
    """Retries a Groq call on 429 rate-limit errors (waiting exactly as long
    as Groq's own error message says to) and on transient connection drops
    (brief fixed backoff) — turns momentary blips into a slightly-slower
    request instead of a failed one."""
    attempt = 0
    while True:
        try:
            return fn()
        except RateLimitError as exc:
            attempt += 1
            if attempt > max_retries:
                raise
            wait_s = _seconds_to_wait(exc)
            logger.warning("Groq rate limit hit, retrying in %.1fs (attempt %d/%d)", wait_s, attempt, max_retries)
            time.sleep(wait_s)
        except APIConnectionError as exc:
            attempt += 1
            if attempt > max_retries:
                raise
            wait_s = 3.0 * attempt  # 3s, then 6s
            logger.warning(
                "Groq connection error (network unreachable?), retrying in %.1fs (attempt %d/%d): %s",
                wait_s, attempt, max_retries, exc,
            )
            time.sleep(wait_s)


def chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 4000,
    reasoning_effort: str = "low",
) -> dict[str, Any]:
    """
    Call the Groq chat model and force a JSON object back. Used for every
    structured task: JD analysis, resume analysis, fit scoring, interview
    turn generation, and report generation.

    reasoning_effort="low" keeps gpt-oss's internal "thinking" tokens short
    so they don't eat the max_tokens budget before the actual JSON answer is
    written (this is what caused "max completion tokens reached before
    generating a valid document" errors on longer prompts like resume
    analysis) — bump it to "medium"/"high" per-call if a task needs deeper
    reasoning and you raise max_tokens to match.
    """
    client = get_client()
    model_name = model or _settings.groq_chat_model
    kwargs: dict[str, Any] = dict(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    if _supports_reasoning_effort(model_name):
        kwargs["reasoning_effort"] = reasoning_effort
    try:
        response = _call_with_rate_limit_retry(lambda: client.chat.completions.create(**kwargs))
        raw = response.choices[0].message.content
        if not raw or not raw.strip():
            raise GroqError(
                "Model returned an empty response — it likely ran out of tokens while "
                "reasoning. Try raising max_tokens or lowering reasoning_effort for this call."
            )
        return _extract_json(raw)
    except GroqError:
        raise
    except TypeError as exc:
        # Guards against dependency drift: if the installed `groq` SDK
        # version predates a keyword argument we send (this exact bug hit
        # production once already — a stale requirements.txt shipped a much
        # older SDK than was tested locally), degrade gracefully by retrying
        # without it instead of hard-crashing every single request.
        bad_kwarg = _unexpected_kwarg_from_error(exc)
        if bad_kwarg and bad_kwarg in kwargs:
            logger.warning(
                "Installed groq SDK doesn't support '%s' — retrying without it. "
                "Consider upgrading the groq package.", bad_kwarg,
            )
            retry_kwargs = {k: v for k, v in kwargs.items() if k != bad_kwarg}
            try:
                response = _call_with_rate_limit_retry(lambda: client.chat.completions.create(**retry_kwargs))
                raw = response.choices[0].message.content
                if not raw or not raw.strip():
                    raise GroqError("Model returned an empty response on retry without the unsupported argument.")
                return _extract_json(raw)
            except GroqError:
                raise
            except Exception as retry_exc:  # noqa: BLE001
                logger.exception("Groq chat_json retry (without unsupported kwarg) also failed")
                raise GroqError(f"Chat completion failed: {retry_exc}") from retry_exc
        logger.exception("Groq chat_json call failed with a TypeError")
        raise GroqError(f"Chat completion failed: {exc}") from exc
    except RateLimitError as exc:
        logger.exception("Groq chat_json call failed after retries")
        raise GroqError(
            "Groq's free-tier rate limit was hit repeatedly. Wait a minute and try again, "
            "or upgrade at https://console.groq.com/settings/billing for higher limits."
        ) from exc
    except APIConnectionError as exc:
        logger.exception("Groq chat_json call failed after retries — connection unreachable")
        raise GroqError(
            "Couldn't reach Groq's servers after retrying — check your internet connection "
            "(wifi/VPN drop, firewall) and try again."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Groq chat_json call failed")
        raise GroqError(f"Chat completion failed: {exc}") from exc


def chat_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.6,
    max_tokens: int = 600,
) -> str:
    """Plain-text chat completion (used where free-form prose is fine)."""
    client = get_client()
    model_name = model or _settings.groq_chat_model
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Groq chat_text call failed")
        raise GroqError(f"Chat completion failed: {exc}") from exc


def transcribe_audio(audio_bytes: bytes, filename: str = "answer.wav") -> str:
    """Speech-to-text via Groq-hosted Whisper. Returns transcript text."""
    client = get_client()
    try:
        result = client.audio.transcriptions.create(
            file=(filename, BytesIO(audio_bytes)),
            model=_settings.groq_stt_model,
            response_format="json",
            language="en",
        )
        return result.text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Groq transcription failed")
        raise GroqError(f"Transcription failed: {exc}") from exc


def synthesize_speech(text: str, voice: str | None = None) -> bytes:
    """Text-to-speech via Groq-hosted Orpheus TTS. Returns WAV audio bytes.

    Orpheus enforces a hard 200-character input cap per call. Rather than
    truncating long questions (which silently cut off the actual "ask" and
    left only the resume-context preamble audible), long text is split into
    sentence-respecting chunks, synthesized separately, and the resulting
    WAV clips are concatenated into one continuous audio file — so the full
    question is always spoken, regardless of length.
    """
    client = get_client()
    chunks = _split_text_for_tts(text.strip(), limit=190)
    audio_parts: list[bytes] = []
    try:
        for chunk in chunks:
            response = client.audio.speech.create(
                model=_settings.groq_tts_model,
                voice=voice or _settings.groq_tts_voice,
                input=chunk,
                response_format="wav",
            )
            audio_parts.append(response.read())
        return _concat_wavs(audio_parts)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Groq TTS failed")
        raise GroqError(f"Speech synthesis failed: {exc}") from exc


def _split_text_for_tts(text: str, limit: int) -> list[str]:
    """Split text into chunks under `limit` chars, preferring to break at
    sentence boundaries, then word boundaries, so no chunk ever mid-cuts a
    word and each chunk reads naturally on its own."""
    if len(text) <= limit:
        return [text] if text else [""]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""

    def flush():
        nonlocal current
        if current:
            chunks.append(current)
            current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= limit:
            current = candidate
            continue
        flush()
        if len(sentence) <= limit:
            current = sentence
            continue
        # A single sentence is longer than the limit — split on words.
        for word in sentence.split(" "):
            candidate = f"{current} {word}".strip() if current else word
            if len(candidate) <= limit:
                current = candidate
            else:
                flush()
                current = word
    flush()
    return chunks or [text[:limit]]


def _concat_wavs(wav_parts: list[bytes]) -> bytes:
    """Stitch multiple WAV byte-strings (same format, from sequential TTS
    calls) into one continuous WAV file.

    Deliberately does NOT copy `nframes` from the source chunks into the
    output writer. Groq's TTS returns a streamed WAV whose header reports a
    placeholder/inaccurate frame count (since the final length isn't known
    while streaming) — passing that straight into `wave`'s writer via
    setparams() makes it trust the bogus count for the RIFF header size
    instead of computing it from actual bytes written, which can overflow
    struct.pack's 32-bit field entirely. Only the real format (channels,
    sample width, framerate) is carried over; frame count is left for
    `wave` to compute correctly from what's actually written.
    """
    if len(wav_parts) == 1:
        return wav_parts[0]

    with wave.open(BytesIO(wav_parts[0]), "rb") as first:
        nchannels = first.getnchannels()
        sampwidth = first.getsampwidth()
        framerate = first.getframerate()

    output = BytesIO()
    with wave.open(output, "wb") as out:
        out.setnchannels(nchannels)
        out.setsampwidth(sampwidth)
        out.setframerate(framerate)
        for part in wav_parts:
            with wave.open(BytesIO(part), "rb") as w:
                out.writeframes(w.readframes(w.getnframes()))
    return output.getvalue()