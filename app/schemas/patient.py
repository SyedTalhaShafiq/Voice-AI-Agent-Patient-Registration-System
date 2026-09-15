"""Pydantic schemas for Patient CRUD — validation, serialization, and the response envelope."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.patient import US_STATES

# ── helpers ──────────────────────────────────────────────────────────

_NAME_RE = re.compile(r"^[A-Za-zÀ-ÿ'\- ]{1,50}$")
_PHONE_RE = re.compile(r"^\d{10}$")  # 10-digit U.S.
_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")
_MEMBER_ID_RE = re.compile(r"^[A-Za-z0-9\-]{1,50}$")

VALID_SEX = {"Male", "Female", "Other", "Decline to Answer"}

# Placeholders frequently sent by LLMs during voice intake when optional fields were not provided
_PLACEHOLDERS = {
    "",
    "none",
    "null",
    "n/a",
    "na",
    "not provided",
    "not available",
    "unspecified",
    "unknown",
    "undefined",
    "no",
    "false",
    "declined",
    "prefer not to answer",
}

# Mapping of common full U.S. state names to 2-letter abbreviations
STATE_NAME_TO_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY", "puerto rico": "PR",
}


def _clean_optional_str(v: Any) -> str | None:
    """Return None if string is empty, null, or an LLM placeholder like 'not provided'."""
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in _PLACEHOLDERS:
        return None
    return s


def _normalize_phone(raw: Any) -> str:
    """Strip common formatting, punctuation, and a leading '1' country code."""
    if raw is None:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _normalize_state(v: Any) -> str:
    """Normalize 2-letter abbreviation or full state name to uppercase abbreviation."""
    if v is None:
        raise ValueError("State is required.")
    s = str(v).strip()
    upper = s.upper()
    if upper in US_STATES:
        return upper
    lower = s.lower()
    if lower in STATE_NAME_TO_ABBR:
        return STATE_NAME_TO_ABBR[lower]
    raise ValueError(f"'{v}' is not a valid 2-letter U.S. state abbreviation.")


def _normalize_sex(v: Any) -> str:
    """Normalize conversational gender/sex responses to standard enum values."""
    if v is None:
        raise ValueError("Sex is required.")
    s = str(v).strip().lower()
    if s in {"male", "m", "man", "boy"}:
        return "Male"
    if s in {"female", "f", "woman", "girl"}:
        return "Female"
    if s in {"other", "non-binary", "nonbinary", "transgender", "nb"}:
        return "Other"
    if s in {"decline to answer", "decline", "declined", "prefer not to answer", "prefer not to say", "unknown", "none"}:
        return "Decline to Answer"
    for valid in VALID_SEX:
        if s == valid.lower():
            return valid
    raise ValueError(f"Sex must be one of: {', '.join(sorted(VALID_SEX))}")


# ── shared base ──────────────────────────────────────────────────────

class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: date
    sex: str
    phone_number: str
    email: EmailStr | None = None
    address_line_1: str = Field(..., min_length=1, max_length=255)
    address_line_2: str | None = None
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=50)
    zip_code: str = Field(..., min_length=5, max_length=10)
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    # ── field validators ─────────────────────────────────────────

    @field_validator("email", mode="before")
    @classmethod
    def _clean_email(cls, v: Any) -> Any:
        cleaned = _clean_optional_str(v)
        return cleaned

    @field_validator("address_line_2", "insurance_provider", "emergency_contact_name", mode="before")
    @classmethod
    def _clean_optionals(cls, v: Any) -> str | None:
        return _clean_optional_str(v)

    @field_validator("preferred_language", mode="before")
    @classmethod
    def _clean_language(cls, v: Any) -> str:
        return _clean_optional_str(v) or "English"

    @field_validator("first_name", "last_name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if not _NAME_RE.match(v):
            raise ValueError(
                "Names must be 1-50 characters: letters, hyphens, apostrophes, and spaces only."
            )
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _validate_dob(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        if v.year < 1900:
            raise ValueError("Date of birth seems unrealistic (before 1900).")
        return v

    @field_validator("sex", mode="before")
    @classmethod
    def _validate_sex(cls, v: Any) -> str:
        return _normalize_sex(v)

    @field_validator("phone_number", mode="before")
    @classmethod
    def _validate_phone(cls, v: Any) -> str:
        digits = _normalize_phone(v)
        if not _PHONE_RE.match(digits):
            raise ValueError("Phone number must be a valid U.S. 10-digit number.")
        return digits

    @field_validator("state", mode="before")
    @classmethod
    def _validate_state(cls, v: Any) -> str:
        return _normalize_state(v)

    @field_validator("zip_code", mode="before")
    @classmethod
    def _validate_zip(cls, v: Any) -> str:
        if v is None:
            raise ValueError("ZIP code is required.")
        v = str(v).strip()
        if not _ZIP_RE.match(v):
            raise ValueError("ZIP code must be 5 digits (12345) or ZIP+4 (12345-6789).")
        return v

    @field_validator("insurance_member_id", mode="before")
    @classmethod
    def _validate_member_id(cls, v: Any) -> str | None:
        cleaned = _clean_optional_str(v)
        if cleaned is not None:
            if not _MEMBER_ID_RE.match(cleaned):
                raise ValueError("Insurance member ID must be alphanumeric (hyphens OK).")
        return cleaned

    @field_validator("emergency_contact_phone", mode="before")
    @classmethod
    def _validate_emerg_phone(cls, v: Any) -> str | None:
        cleaned = _clean_optional_str(v)
        if cleaned is not None:
            digits = _normalize_phone(cleaned)
            if not _PHONE_RE.match(digits):
                # Rather than failing the whole registration if an optional emergency phone is bad,
                # we return None if it is a placeholder or not a valid 10-digit number
                return None
            return digits
        return None


# ── create ────────────────────────────────────────────────────────────

class PatientCreate(PatientBase):
    """All required fields for creating a new patient."""
    pass


# ── update (all fields optional) ─────────────────────────────────────

class PatientUpdate(BaseModel):
    """Partial update — every field is optional."""
    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    date_of_birth: date | None = None
    sex: str | None = None
    phone_number: str | None = None
    email: EmailStr | None = None
    address_line_1: str | None = Field(None, min_length=1, max_length=255)
    address_line_2: str | None = None
    city: str | None = Field(None, min_length=1, max_length=100)
    state: str | None = Field(None, min_length=2, max_length=50)
    zip_code: str | None = Field(None, min_length=5, max_length=10)
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    # Re-use the same validators, but only on provided fields

    @field_validator("email", mode="before")
    @classmethod
    def _clean_email(cls, v: Any) -> Any:
        return _clean_optional_str(v)

    @field_validator("address_line_2", "insurance_provider", "emergency_contact_name", mode="before")
    @classmethod
    def _clean_optionals(cls, v: Any) -> str | None:
        return _clean_optional_str(v)

    @field_validator("preferred_language", mode="before")
    @classmethod
    def _clean_language(cls, v: Any) -> str | None:
        return _clean_optional_str(v)

    @field_validator("first_name", "last_name")
    @classmethod
    def _validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not _NAME_RE.match(v):
            raise ValueError(
                "Names must be 1-50 characters: letters, hyphens, apostrophes, and spaces only."
            )
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _validate_dob(cls, v: date | None) -> date | None:
        if v is None:
            return v
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        if v.year < 1900:
            raise ValueError("Date of birth seems unrealistic (before 1900).")
        return v

    @field_validator("sex", mode="before")
    @classmethod
    def _validate_sex(cls, v: Any) -> str | None:
        if v is None:
            return None
        cleaned = _clean_optional_str(v)
        if cleaned is None:
            return None
        return _normalize_sex(cleaned)

    @field_validator("phone_number", mode="before")
    @classmethod
    def _validate_phone(cls, v: Any) -> str | None:
        if v is None:
            return None
        cleaned = _clean_optional_str(v)
        if cleaned is None:
            return None
        digits = _normalize_phone(cleaned)
        if not _PHONE_RE.match(digits):
            raise ValueError("Phone number must be a valid U.S. 10-digit number.")
        return digits

    @field_validator("state", mode="before")
    @classmethod
    def _validate_state(cls, v: Any) -> str | None:
        if v is None:
            return None
        cleaned = _clean_optional_str(v)
        if cleaned is None:
            return None
        return _normalize_state(cleaned)

    @field_validator("zip_code", mode="before")
    @classmethod
    def _validate_zip(cls, v: Any) -> str | None:
        if v is None:
            return None
        cleaned = _clean_optional_str(v)
        if cleaned is None:
            return None
        if not _ZIP_RE.match(cleaned):
            raise ValueError("ZIP code must be 5 digits (12345) or ZIP+4 (12345-6789).")
        return cleaned

    @field_validator("insurance_member_id", mode="before")
    @classmethod
    def _validate_member_id(cls, v: Any) -> str | None:
        if v is None:
            return None
        cleaned = _clean_optional_str(v)
        if cleaned is not None:
            if not _MEMBER_ID_RE.match(cleaned):
                raise ValueError("Insurance member ID must be alphanumeric (hyphens OK).")
        return cleaned

    @field_validator("emergency_contact_phone", mode="before")
    @classmethod
    def _validate_emerg_phone(cls, v: Any) -> str | None:
        if v is None:
            return None
        cleaned = _clean_optional_str(v)
        if cleaned is not None:
            digits = _normalize_phone(cleaned)
            if not _PHONE_RE.match(digits):
                return None
            return digits
        return None


# ── response ──────────────────────────────────────────────────────────

class PatientResponse(PatientBase):
    """Returned to API consumers — includes auto-generated fields."""
    patient_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── response envelope ─────────────────────────────────────────────────

T = TypeVar("T")


class ErrorDetail(BaseModel):
    message: str
    details: list[dict[str, Any]] | None = None


class Envelope(BaseModel, Generic[T]):
    """Consistent response wrapper: { "data": ..., "error": null }"""
    data: T | None = None
    error: ErrorDetail | None = None
