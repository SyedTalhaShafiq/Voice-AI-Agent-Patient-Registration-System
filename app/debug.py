"""Temporary debug endpoint — REMOVE before going to production."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient

router = APIRouter(prefix="/debug", tags=["debug"])


def _patient_to_dict(p: Patient) -> dict:
    return {
        "patient_id": p.patient_id,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "phone_number": p.phone_number,
        "date_of_birth": str(p.date_of_birth) if p.date_of_birth else None,
        "sex": p.sex,
        "address_line_1": p.address_line_1,
        "city": p.city,
        "state": p.state,
        "zip_code": p.zip_code,
        "email": p.email,
        "insurance_provider": p.insurance_provider,
        "preferred_language": p.preferred_language,
        "created_at": str(p.created_at) if hasattr(p, "created_at") and p.created_at else None,
    }


@router.get("/patients")
def list_patients(db: Session = Depends(get_db)):
    """Return the 20 most-recently created patients. Useful for quick DB verification."""
    rows = (
        db.query(Patient)
        .filter(Patient.deleted_at.is_(None))
        .order_by(Patient.patient_id.desc())
        .limit(20)
        .all()
    )
    return {"count": len(rows), "patients": [_patient_to_dict(r) for r in rows]}


@router.get("/patients/{phone_number}")
def find_patient_by_phone(phone_number: str, db: Session = Depends(get_db)):
    """Lookup a patient by phone number (digits only, e.g. 15551234567)."""
    import re
    digits = re.sub(r"\D", "", phone_number)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    row = (
        db.query(Patient)
        .filter(Patient.phone_number == digits, Patient.deleted_at.is_(None))
        .first()
    )
    if not row:
        return {"found": False, "patient": None}
    return {"found": True, "patient": _patient_to_dict(row)}
