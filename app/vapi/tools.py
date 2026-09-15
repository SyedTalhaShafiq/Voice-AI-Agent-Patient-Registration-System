"""Vapi tool/webhook handlers — routes that Vapi calls during a live conversation."""

import json
import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate
from app.vapi.schemas import VapiToolResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vapi", tags=["vapi-tools"])


def _phone_digits(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _parse_dob(raw: str):
    """Try common date formats and return a date object or None."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


# ── check_existing_patient ───────────────────────────────────────────

@router.post("/check_existing_patient")
async def check_existing_patient(request: Request, db: Session = Depends(get_db)):
    """
    Vapi tool: Look up a patient by phone number.
    Returns whether a matching record already exists.
    """
    body = await request.json()
    args = _extract_args(body)
    phone = args.get("phone_number", "")
    digits = _phone_digits(phone)

    existing = db.query(Patient).filter(
        Patient.phone_number == digits,
        Patient.deleted_at.is_(None),
    ).first()

    if existing:
        result = (
            "DUPLICATE_FOUND (internal status, never say this word aloud): "
            f"An existing record was found for {existing.first_name} {existing.last_name}. "
            "Warmly let the caller know we already have them on file and ask whether "
            "they'd like to update their existing information. "
            "Never read any ID or system detail aloud. "
            f"Use this reference only if they choose to update (never say it aloud): {existing.patient_id}"
        )
        logger.info("Duplicate check hit: phone=%s → patient_id=%s", digits, existing.patient_id)
    else:
        result = (
            "NO_DUPLICATE (internal status, never say this word aloud): "
            "No existing record was found for this caller; go ahead and register them."
        )
        logger.info("Duplicate check: phone=%s → no match", digits)

    return {"result": result}


# ── create_patient ───────────────────────────────────────────────────

@router.post("/create_patient")
async def create_patient_vapi(request: Request, db: Session = Depends(get_db)):
    """
    Vapi tool: Create a new patient record after caller confirmation.
    """
    body = await request.json()
    args = _extract_args(body)

    # Parse date of birth
    dob = _parse_dob(args.get("date_of_birth", ""))
    if dob is None:
        logger.warning("create_patient: invalid date_of_birth=%s", args.get("date_of_birth"))
        return {"result": "ERROR (internal status, never say this word aloud): The date of birth wasn't understood. Ask the caller to repeat their date of birth, including the month, day, and year."}

    # Build PatientCreate payload
    try:
        payload = PatientCreate(
            first_name=args["first_name"],
            last_name=args["last_name"],
            date_of_birth=dob,
            sex=args["sex"],
            phone_number=args["phone_number"],
            address_line_1=args["address_line_1"],
            city=args["city"],
            state=args["state"],
            zip_code=args["zip_code"],
            email=args.get("email"),
            address_line_2=args.get("address_line_2"),
            insurance_provider=args.get("insurance_provider"),
            insurance_member_id=args.get("insurance_member_id"),
            preferred_language=args.get("preferred_language", "English"),
            emergency_contact_name=args.get("emergency_contact_name"),
            emergency_contact_phone=args.get("emergency_contact_phone"),
        )
    except Exception as exc:
        logger.warning("create_patient: validation failed: %s", exc)
        return {"result": f"ERROR (internal status, never say this word aloud): Some details didn't pass validation. Gently ask the caller to re-check the affected information and repeat it. Internal detail, never read aloud: {exc}"}

    # Persist
    patient = Patient(**payload.model_dump())
    try:
        db.add(patient)
        db.commit()
        db.refresh(patient)
    except Exception:
        db.rollback()
        logger.exception("create_patient: database write failed")
        return {"result": "ERROR (internal status, never say this word aloud): Saving the record failed. Apologize to the caller, let them know there was a problem on our end, and offer to try again or have them call back."}

    # Log final payload as JSON lines for inspection
    logger.info(
        json.dumps(
            {
                "event": "patient_created_via_vapi",
                "patient_id": patient.patient_id,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "phone_number": patient.phone_number,
                "data": payload.model_dump(mode="json"),
            }
        )
    )

    return {
        "result": (
            "SUCCESS (internal status, never say this word aloud): "
            f"The registration was saved. Warmly let {patient.first_name} know they're all set. "
            "Never read any ID or system detail aloud."
        )
    }


# ── update_patient ───────────────────────────────────────────────────

@router.post("/update_patient")
async def update_patient_vapi(request: Request, db: Session = Depends(get_db)):
    """
    Vapi tool: Update an existing patient record.
    """
    body = await request.json()
    args = _extract_args(body)

    patient_id = args.get("patient_id", "")
    patient = db.query(Patient).filter(
        Patient.patient_id == patient_id,
        Patient.deleted_at.is_(None),
    ).first()

    if not patient:
        return {"result": "ERROR (internal status, never say this word aloud): That record could not be found. Ask the caller to confirm their details so you can look again."}

    # Build partial update dict
    updates = {}
    for field in [
        "first_name", "last_name", "sex", "phone_number", "address_line_1",
        "address_line_2", "city", "state", "zip_code", "email",
        "insurance_provider", "insurance_member_id", "preferred_language",
        "emergency_contact_name", "emergency_contact_phone",
    ]:
        if args.get(field) is not None:
            updates[field] = args[field]

    # Handle date_of_birth separately
    if args.get("date_of_birth"):
        dob = _parse_dob(args["date_of_birth"])
        if dob is None:
            return {"result": "ERROR (internal status, never say this word aloud): The date of birth wasn't understood. Ask the caller to repeat their date of birth, including the month, day, and year."}
        updates["date_of_birth"] = dob

    if not updates:
        return {"result": "ERROR (internal status, never say this word aloud): No changes were provided. Ask the caller what they'd like to update."}

    # Validate via PatientUpdate
    try:
        validated = PatientUpdate(**updates)
    except Exception as exc:
        logger.warning("update_patient: validation failed: %s", exc)
        return {"result": f"ERROR (internal status, never say this word aloud): Some details didn't pass validation. Gently ask the caller to re-check the affected information. Internal detail, never read aloud: {exc}"}

    for field, value in validated.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    try:
        db.commit()
        db.refresh(patient)
    except Exception:
        db.rollback()
        logger.exception("update_patient: database write failed")
        return {"result": "ERROR (internal status, never say this word aloud): Updating the record failed. Apologize to the caller and offer to try again or have them call back."}

    logger.info(
        json.dumps(
            {
                "event": "patient_updated_via_vapi",
                "patient_id": patient.patient_id,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "updated_fields": list(updates.keys()),
            }
        )
    )

    return {
        "result": (
            "SUCCESS (internal status, never say this word aloud): "
            f"The update was saved. Let {patient.first_name} know their information has been updated. "
            "Never read any ID or system detail aloud."
        )
    }


# ── helper ────────────────────────────────────────────────────────────

def _extract_args(body: dict) -> dict:
    """
    Extract tool-call arguments from the Vapi webhook payload.
    Vapi sends: { "message": { "toolCallList": [{ "function": { "name": ..., "arguments": "..." } }] } }
    """
    try:
        tool_calls = body.get("message", {}).get("toolCallList", [])
        if tool_calls:
            raw_args = tool_calls[0].get("function", {}).get("arguments", "{}")
            if isinstance(raw_args, str):
                return json.loads(raw_args)
            return raw_args
    except (json.JSONDecodeError, AttributeError, IndexError) as exc:
        logger.warning("_extract_args: failed to parse Vapi payload: %s", exc)
    return {}
