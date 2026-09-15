"""FastAPI application entry point — wires routes, creates tables, seeds data."""

import logging
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import Base, SessionLocal, engine
from app.api.routes import router as patient_router
from app.vapi.tools import router as vapi_router
from app.seed import seed_patients

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
