from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.database import init_db
from app.routers import analysis, interview, report, voice

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI Interview Accelerator API",
    description="JD/Resume analysis, adaptive AI interview engine, voice, and performance reporting.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis.router)
app.include_router(interview.router)
app.include_router(voice.router)
app.include_router(report.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "groq_key_configured": bool(settings.groq_api_key)}
