from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import create_all_tables, check_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="JOURNI API",
    description="Personalized AI travel-planning API",
    version="1.0.0"
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    """
    On startup:
    1. Verify database connectivity — fail clearly if unavailable.
    2. Ensure all tables exist (safe for both fresh and existing databases).
    """
    healthy, message = check_db_connection()
    if not healthy:
        logger.critical(f"DATABASE UNAVAILABLE AT STARTUP: {message}")
        raise RuntimeError(f"Cannot connect to database: {message}")
    logger.info(f"Database ready: {message}")
    
    # Create tables (idempotent — does nothing if they already exist)
    create_all_tables()
    logger.info("Schema check complete.")
    from app.llm.client import LLMClient
    llm_client = LLMClient.get_instance()
    logger.info("Gemini integration %s.", "initialized" if llm_client.client else "unavailable; deterministic fallbacks enabled")

# ─── Routers ──────────────────────────────────────────────────────────────────

from app.api import trips
app.include_router(trips.router, prefix="/api/trips", tags=["trips"])

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["health"])
def health_check():
    """
    Returns application and database health status.
    Does NOT expose credentials or internal configuration.
    """
    db_healthy, db_message = check_db_connection()
    from app.llm.client import LLMClient
    gemini_configured = LLMClient.get_instance().client is not None
    return {
        "status": "ok" if db_healthy else "degraded",
        "service": "journi-api",
        "ai": {
            "provider": "Gemini",
            "configured": gemini_configured,
            "model": LLMClient.get_instance().model,
        },
        "database": {
            "connected": db_healthy,
            "message": db_message
        }
    }
