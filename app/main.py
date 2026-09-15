"""FastAPI application entry point — wires routes, creates tables, seeds data."""

import logging
import os
import sys

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from app.database import Base, SessionLocal, engine
from app.api.routes import router as patient_router
from app.vapi.tools import router as vapi_router
from app.seed import seed_patients
from app.config import settings

# ── logging setup ────────────────────────────────────────────────────
# Structured JSON lines to stdout for easy inspection of call payloads.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("carecloud")

# ── create tables on startup ─────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── seed data (idempotent — only inserts if table is empty) ──────────
seed_patients()

# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(
    title="CareCloud — Patient Registration API",
    description=(
        "REST API for patient demographic registration, paired with a Vapi voice AI agent "
        "for phone-based intake. Interactive docs available at /docs."
    ),
    version="1.0.0",
)

# Register routers
app.include_router(patient_router)
app.include_router(vapi_router)


# ── global exception handler ─────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "data": None,
            "error": {"message": "Internal server error.", "details": None},
        },
    )


# ── health check ─────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
def health_check():
    return {"status": "ok"}


# ── browser voice test client ────────────────────────────────────────
# Serves web_test/index.html so you can talk to the Vapi assistant in the
# browser (mic + WebRTC) without a phone call. Served over localhost so the
# browser grants microphone access (a secure context).
_WEB_TEST_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "web_test", "index.html"
)


@app.get("/test", tags=["meta"], include_in_schema=False)
def voice_test_client():
    return FileResponse(_WEB_TEST_FILE)


@app.get("/vapi-config", tags=["meta"], include_in_schema=False)
def vapi_config():
    """
    Client-safe Vapi config for the /test browser voice client.
    Values come from Railway (or local .env) environment variables
    (VAPI_API_KEY, ASSISTANT_API_KEY) — never hardcoded or typed by hand.
    """
    return {
        "publicKey": settings.vapi_api_key,
        "assistantId": settings.assistant_api_key,
    }
