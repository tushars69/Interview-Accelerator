"""
Central application settings, loaded from environment variables / .env.

Only ONE external API key is required: GROQ_API_KEY.
Groq is used for three separate capabilities, each with its own model:
  1. Chat/reasoning (JD & resume analysis, adaptive interview logic, report generation)
  2. Speech-to-text (candidate's spoken answers)
  3. Text-to-speech (AI interviewer's spoken questions)
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Groq API ---
    groq_api_key: str = ""

    # Chat model used for analysis + interviewing. gpt-oss-120b is Groq's current
    # flagship reasoning model (llama-3.3-70b-versatile was deprecated by Groq and
    # is no longer callable) — swap to a smaller model if you want lower latency
    # at the cost of some reasoning depth.
    groq_chat_model: str = "openai/gpt-oss-120b"

    # Faster/cheaper model used for lightweight tasks (e.g. quick classification)
    groq_fast_model: str = "openai/gpt-oss-20b"

    # Speech-to-text model (Groq-hosted Whisper)
    groq_stt_model: str = "whisper-large-v3-turbo"

    # Text-to-speech model + default voice (Groq-hosted Orpheus TTS — the older
    # playai-tts model was deprecated by Groq; Orpheus voices are:
    # autumn, diana, hannah, austin, daniel, troy)
    groq_tts_model: str = "canopylabs/orpheus-v1-english"
    groq_tts_voice: str = "hannah"

    # --- App ---
    app_env: str = "development"
    database_url: str = "sqlite:///./interview_accelerator.db"
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"

    # Interview tuning
    max_questions_per_level: int = 5
    min_questions_per_level: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
