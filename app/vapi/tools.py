"""Vapi tool/webhook handlers — routes that Vapi calls during a live conversation."""

import json
import logging
import re
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate
from app.vapi.schemas import VapiToolResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vapi", tags=["vapi-tools"])

CAMEL_TO_SNAKE = {
    "firstName": "first_name",
    "lastName": "last_name",
    "dateOfBirth": "date_of_birth",
    "dob": "date_of_birth",
    "phoneNumber": "phone_number",
    "phone": "phone_number",
    "emailAddress": "email",
    "addressLine1": "address_line_1",
    "address1": "address_line_1",
    "streetAddress": "address_line_1",
    "addressLine2": "address_line_2",
    "address2": "address_line_2",
    "apt": "address_line_2",
    "unit": "address_line_2",
    "zipCode": "zip_code",
    "zip": "zip_code",
    "postalCode": "zip_code",
    "insuranceProvider": "insurance_provider",
    "insuranceMemberId": "insurance_member_id",
    "memberId": "insurance_member_id",
    "preferredLanguage": "preferred_language",
    "language": "preferred_language",
    "emergencyContactName": "emergency_contact_name",
    "emergencyContactPhone": "emergency_contact_phone",
    "patientId": "patient_id",
}


def _phone_digits(raw: Any) -> str:
    if raw is None:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _parse_dob(raw: Any):
    """Try dateutil and common date formats to return a date object or None."""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if raw is None or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        from dateutil import parser
        return parser.parse(s).date()
    except Exception:
        pass
    for fmt in (
        "%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y",
        "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%d/%m/%Y",
        "%d-%m-%Y", "%Y/%m/%d", "%Y%m%d",
    ):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_args(raw_args: dict) -> dict:
    """Normalize camelCase keys and clean values in argument dictionary."""
    normalized = {}
    for k, v in raw_args.items():
        key = CAMEL_TO_SNAKE.get(k, k)
        normalized[key] = v
    return normalized


# ── Core Tool Execution Logic ────────────────────────────────────────

def execute_check_existing_patient(db: Session, args: dict) -> str:
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
    return result


def execute_create_patient(db: Session, args: dict) -> str:
    dob_raw = args.get("date_of_birth") or args.get("dob")
    dob = _parse_dob(dob_raw)
    if dob is None:
        logger.warning("create_patient: invalid date_of_birth=%s", dob_raw)
        return (
            "ERROR (internal status, never say this word aloud): The date of birth wasn't understood. "
            "Ask the caller to repeat their date of birth, including the month, day, and year."
        )

    first_name = args.get("first_name")
    last_name = args.get("last_name")
    phone_number = args.get("phone_number")
    address_line_1 = args.get("address_line_1")
    city = args.get("city")
    state = args.get("state")
    zip_code = args.get("zip_code")
    sex = args.get("sex", "Other")

    if not all([first_name, last_name, phone_number, address_line_1, city, state, zip_code]):
        missing = [
            f for f, v in [
                ("first name", first_name),
                ("last name", last_name),
                ("phone number", phone_number),
                ("street address", address_line_1),
                ("city", city),
                ("state", state),
                ("zip code", zip_code),
            ] if not v
        ]
        return (
            f"ERROR (internal status, never say this word aloud): Missing required information: {', '.join(missing)}. "
            "Ask the caller to provide these missing details."
        )

    try:
        payload = PatientCreate(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            sex=sex,
            phone_number=phone_number,
            address_line_1=address_line_1,
            city=city,
            state=state,
            zip_code=str(zip_code),
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
        return (
            f"ERROR (internal status, never say this word aloud): Some details didn't pass validation. "
            f"Gently ask the caller to re-check the affected information and repeat it. Internal detail, never read aloud: {exc}"
        )

    patient = Patient(**payload.model_dump())
    try:
        db.add(patient)
        db.commit()
        db.refresh(patient)
    except Exception:
        db.rollback()
        logger.exception("create_patient: database write failed")
        return (
            "ERROR (internal status, never say this word aloud): Saving the record failed. "
            "Apologize to the caller, let them know there was a problem on our end, and offer to try again or have them call back."
        )

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

    return (
        "SUCCESS (internal status, never say this word aloud): "
        f"The registration was saved. Warmly let {patient.first_name} know they're all set. "
        "Never read any ID or system detail aloud."
    )


def execute_update_patient(db: Session, args: dict) -> str:
    patient_id = args.get("patient_id", "")
    patient = db.query(Patient).filter(
        Patient.patient_id == patient_id,
        Patient.deleted_at.is_(None),
    ).first()

    if not patient:
        return (
            "ERROR (internal status, never say this word aloud): That record could not be found. "
            "Ask the caller to confirm their details so you can look again."
        )

    updates = {}
    for field in [
        "first_name", "last_name", "sex", "phone_number", "address_line_1",
        "address_line_2", "city", "state", "zip_code", "email",
        "insurance_provider", "insurance_member_id", "preferred_language",
        "emergency_contact_name", "emergency_contact_phone",
    ]:
        if args.get(field) is not None:
            updates[field] = args[field]

    if args.get("date_of_birth") or args.get("dob"):
        dob_val = args.get("date_of_birth") or args.get("dob")
        dob = _parse_dob(dob_val)
        if dob is None:
            return (
                "ERROR (internal status, never say this word aloud): The date of birth wasn't understood. "
                "Ask the caller to repeat their date of birth, including the month, day, and year."
            )
        updates["date_of_birth"] = dob

    if not updates:
        return (
            "ERROR (internal status, never say this word aloud): No changes were provided. "
            "Ask the caller what they'd like to update."
        )

    try:
        validated = PatientUpdate(**updates)
    except Exception as exc:
        logger.warning("update_patient: validation failed: %s", exc)
        return (
            f"ERROR (internal status, never say this word aloud): Some details didn't pass validation. "
            f"Gently ask the caller to re-check the affected information. Internal detail, never read aloud: {exc}"
        )

    for field, value in validated.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    try:
        db.commit()
        db.refresh(patient)
    except Exception:
        db.rollback()
        logger.exception("update_patient: database write failed")
        return (
            "ERROR (internal status, never say this word aloud): Updating the record failed. "
            "Apologize to the caller and offer to try again or have them call back."
        )

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

    return (
        "SUCCESS (internal status, never say this word aloud): "
        f"The update was saved. Let {patient.first_name} know their information has been updated. "
        "Never read any ID or system detail aloud."
    )


def dispatch_tool_call(db: Session, fn_name: str, args: dict) -> str:
    """Route function name to corresponding executor with intelligent fallback."""
    name_lower = (fn_name or "").lower()
    if "check" in name_lower or "existing" in name_lower or "duplicate" in name_lower:
        return execute_check_existing_patient(db, args)
    if "update" in name_lower:
        return execute_update_patient(db, args)
    if "create" in name_lower or "register" in name_lower:
        return execute_create_patient(db, args)

    # Fallback heuristic based on arguments provided
    if "patient_id" in args:
        return execute_update_patient(db, args)
    if "address_line_1" in args or "city" in args:
        return execute_create_patient(db, args)
    if "phone_number" in args:
        return execute_check_existing_patient(db, args)

    return f"ERROR (internal status, never say this word aloud): Unknown tool '{fn_name}'."


# ── Universal Webhook Handler (Assistant Server URL) ─────────────────

@router.post("")
@router.post("/")
@router.post("/webhook")
async def handle_vapi_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Universal webhook receiver for Vapi. Handles:
    - Assistant-level Server URL webhooks
    - Batched or single tool-calls (toolCallList / toolCalls)
    - Lifecycle messages (status-update, end-of-call-report, speech-update, transcript)
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    message = body.get("message", {}) or {}
    msg_type = message.get("type") or body.get("type")

    # If it's a non-tool-call event (e.g. status-update, transcript, end-of-call-report), acknowledge with 200 OK
    if msg_type and msg_type != "tool-calls":
        logger.info("Vapi lifecycle event received: type=%s", msg_type)
        return {"status": "ok"}

    extracted = _extract_tool_calls(body)
    if not extracted:
        logger.info("Vapi webhook with no tool calls: type=%s", msg_type)
        return {"status": "ok", "results": []}

    results = []
    for tool_call_id, fn_name, args in extracted:
        logger.info("Executing Vapi tool call: id=%s name=%s", tool_call_id, fn_name)
        result_text = dispatch_tool_call(db, fn_name, args)
        results.append({"toolCallId": tool_call_id, "result": result_text})

    return {
        "results": results,
        "result": results[0]["result"] if results else "SUCCESS",
    }


# ── Dedicated Per-Tool Endpoints (Tool Server URL) ────────────────────

@router.post("/check_existing_patient")
async def check_existing_patient(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    tool_call_id, args = _extract_tool_call(body)
    result = execute_check_existing_patient(db, args)
    return _vapi_result(tool_call_id, result)


@router.post("/create_patient")
async def create_patient_vapi(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    tool_call_id, args = _extract_tool_call(body)
    result = execute_create_patient(db, args)
    return _vapi_result(tool_call_id, result)


@router.post("/update_patient")
async def update_patient_vapi(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    tool_call_id, args = _extract_tool_call(body)
    result = execute_update_patient(db, args)
    return _vapi_result(tool_call_id, result)


# ── Vapi payload helpers ─────────────────────────────────────────────

def _extract_tool_calls(body: dict) -> list[tuple[str, str, dict]]:
    """
    Robust extractor supporting all Vapi tool-call formats:
    - { message: { toolCallList: [ { id, name, arguments } ] } }
    - { message: { toolCalls: [ { id, function: { name, arguments } } ] } }
    - { message: { toolCall: { id, name, arguments } } }
    - Top-level without message: { toolCallList: [...] } or { toolCalls: [...] }
    - Direct function call: { id, name, arguments } or { function: {...} }
    Returns list of (tool_call_id, function_name, normalized_args).
    """
    calls_list = []
    message = body.get("message", {}) or {}

    raw_calls = (
        message.get("toolCallList")
        or message.get("toolCalls")
        or body.get("toolCallList")
        or body.get("toolCalls")
        or []
    )

    # Check for singular toolCall
    single_call = message.get("toolCall") or body.get("toolCall")
    if single_call and isinstance(single_call, dict):
        raw_calls = [single_call]

    # If no array or singular was found, check if body itself is a tool call
    if not raw_calls and (body.get("function") or body.get("name") or body.get("id")):
        raw_calls = [body]

    for call in raw_calls:
        if not isinstance(call, dict):
            continue
        tool_call_id = call.get("id") or call.get("toolCallId") or "call_unknown"
        fn = call.get("function", {}) or {}
        fn_name = call.get("name") or fn.get("name") or ""

        raw_args = call.get("arguments")
        if raw_args is None:
            raw_args = fn.get("arguments")
        if raw_args is None:
            raw_args = call.get("parameters") or fn.get("parameters") or {}

        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args or "{}")
            except Exception:
                raw_args = {}

        if not isinstance(raw_args, dict):
            raw_args = {}

        normalized = _normalize_args(raw_args)
        calls_list.append((tool_call_id, fn_name, normalized))

    return calls_list


def _extract_tool_call(body: dict):
    """
    Backward-compatible helper returning (tool_call_id, args_dict) for the first call.
    """
    calls = _extract_tool_calls(body)
    if calls:
        call_id, _, args = calls[0]
        return call_id, args
    return None, {}


def _vapi_result(tool_call_id, text: str) -> dict:
    """
    Wrap a caller-facing message in Vapi's expected tool response envelope:
        { "results": [ { "toolCallId": ..., "result": ... } ] }
    A top-level "result" key is also included for backward-compatible clients/tests.
    """
    return {
        "results": [{"toolCallId": tool_call_id, "result": text}],
        "result": text,
    }
