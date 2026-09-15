"""REST API routes for Patient CRUD operations."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.schemas.patient import (
    Envelope,
    ErrorDetail,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/patients", tags=["patients"])


# ── helpers ──────────────────────────────────────────────────────────

def _ok(data):
    return Envelope(data=data, error=None)


def _err(status: int, message: str, details=None):
    return Envelope(
        data=None,
        error=ErrorDetail(message=message, details=details),
    )


def _get_patient_or_404(db: Session, patient_id: str) -> Patient:
    patient = db.query(Patient).filter(
        Patient.patient_id == patient_id,
        Patient.deleted_at.is_(None),
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return patient


# ── GET /patients ─────────────────────────────────────────────────────

@router.get("", response_model=Envelope[list[PatientResponse]])
def list_patients(
    last_name: str | None = Query(None),
    date_of_birth: str | None = Query(None),
    phone_number: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """List all non-deleted patients. Supports optional filters."""
    query = db.query(Patient).filter(Patient.deleted_at.is_(None))

    if last_name:
        query = query.filter(Patient.last_name.ilike(f"%{last_name}%"))
    if date_of_birth:
        try:
            dob = datetime.strptime(date_of_birth, "%m/%d/%Y").date()
            query = query.filter(Patient.date_of_birth == dob)
        except ValueError:
            pass  # ignore bad filter format, return unfiltered
    if phone_number:
        import re
        digits = re.sub(r"\D", "", phone_number)
        query = query.filter(Patient.phone_number == digits)

    patients = query.order_by(Patient.created_at.desc()).all()
    return _ok([PatientResponse.model_validate(p) for p in patients])


# ── GET /patients/{id} ────────────────────────────────────────────────

@router.get("/{patient_id}", response_model=Envelope[PatientResponse])
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    """Retrieve a single patient by UUID."""
    patient = _get_patient_or_404(db, patient_id)
    return _ok(PatientResponse.model_validate(patient))


# ── POST /patients ────────────────────────────────────────────────────

@router.post("", response_model=Envelope[PatientResponse], status_code=201)
def create_patient(body: PatientCreate, db: Session = Depends(get_db)):
    """Create a new patient record."""
    data = body.model_dump()
    patient = Patient(**data)
    try:
        db.add(patient)
        db.commit()
        db.refresh(patient)
    except Exception as exc:
        db.rollback()
        logger.exception("Database write failed during patient creation")
        raise HTTPException(status_code=500, detail="Failed to save patient record.")

    logger.info(
        "Patient created: %s %s (id=%s)",
        patient.first_name,
        patient.last_name,
        patient.patient_id,
    )
    return _ok(PatientResponse.model_validate(patient))


# ── PUT /patients/{id} ────────────────────────────────────────────────

@router.put("/{patient_id}", response_model=Envelope[PatientResponse])
def update_patient(
    patient_id: str,
    body: PatientUpdate,
    db: Session = Depends(get_db),
):
    """Partial update — only provided fields are changed."""
    patient = _get_patient_or_404(db, patient_id)
    updates = body.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    for field, value in updates.items():
        setattr(patient, field, value)

    try:
        db.commit()
        db.refresh(patient)
    except Exception as exc:
        db.rollback()
        logger.exception("Database write failed during patient update")
        raise HTTPException(status_code=500, detail="Failed to update patient record.")

    logger.info(
        "Patient updated: %s %s (id=%s)",
        patient.first_name,
        patient.last_name,
        patient.patient_id,
    )
    return _ok(PatientResponse.model_validate(patient))


# ── DELETE /patients/{id} (soft-delete) ───────────────────────────────

@router.delete("/{patient_id}", response_model=Envelope[dict])
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    """Soft-delete: sets deleted_at, does not remove the row."""
    patient = _get_patient_or_404(db, patient_id)
    patient.deleted_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Database write failed during patient deletion")
        raise HTTPException(status_code=500, detail="Failed to delete patient record.")

    logger.info(
        "Patient soft-deleted: %s %s (id=%s)",
        patient.first_name,
        patient.last_name,
        patient.patient_id,
    )
    return _ok({"message": "Patient record deleted.", "patient_id": patient_id})
