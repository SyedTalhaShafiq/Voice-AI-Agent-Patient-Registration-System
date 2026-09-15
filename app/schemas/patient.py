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


def _normalize_phone(raw: str) -> str:
    """Strip common formatting and a leading '1' country code."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


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
    state: str = Field(..., min_length=2, max_length=2)
    zip_code: str = Field(..., min_length=5, max_length=10)
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    # ── field validators ─────────────────────────────────────────

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

    @field_validator("sex")
    @classmethod
    def _validate_sex(cls, v: str) -> str:
        v = v.strip()
        # Case-insensitive matching but return canonical form
        for valid in VALID_SEX:
            if v.lower() == valid.lower():
                return valid
        raise ValueError(f"Sex must be one of: {', '.join(sorted(VALID_SEX))}")

    @field_validator("phone_number")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        digits = _normalize_phone(v)
        if not _PHONE_RE.match(digits):
            raise ValueError("Phone number must be a valid U.S. 10-digit number.")
        return digits

    @field_validator("state")
    @classmethod
    def _validate_state(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError(f"'{v}' is not a valid 2-letter U.S. state abbreviation.")
        return v

    @field_validator("zip_code")
    @classmethod
    def _validate_zip(cls, v: str) -> str:
        v = v.strip()
        if not _ZIP_RE.match(v):
            raise ValueError("ZIP code must be 5 digits (12345) or ZIP+4 (12345-6789).")
        return v

    @field_validator("insurance_member_id")
    @classmethod
    def _validate_member_id(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not _MEMBER_ID_RE.match(v):
                raise ValueError("Insurance member ID must be alphanumeric (hyphens OK).")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def _validate_emerg_phone(cls, v: str | None) -> str | None:
        if v is not None:
            digits = _normalize_phone(v)
            if not _PHONE_RE.match(digits):
                raise ValueError("Emergency contact phone must be a valid U.S. 10-digit number.")
            return digits
        return v


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
    state: str | None = Field(None, min_length=2, max_length=2)
    zip_code: str | None = Field(None, min_length=5, max_length=10)
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    # Re-use the same validators, but only on provided fields

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

    @field_validator("sex")
    @classmethod
    def _validate_sex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        for valid in VALID_SEX:
            if v.lower() == valid.lower():
                return valid
        raise ValueError(f"Sex must be one of: {', '.join(sorted(VALID_SEX))}")

    @field_validator("phone_number")
    @classmethod
    def _validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        digits = _normalize_phone(v)
        if not _PHONE_RE.match(digits):
            raise ValueError("Phone number must be a valid U.S. 10-digit number.")
        return digits

    @field_validator("state")
    @classmethod
    def _validate_state(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError(f"'{v}' is not a valid 2-letter U.S. state abbreviation.")
        return v

    @field_validator("zip_code")
    @classmethod
    def _validate_zip(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not _ZIP_RE.match(v):
            raise ValueError("ZIP code must be 5 digits (12345) or ZIP+4 (12345-6789).")
        return v

    @field_validator("insurance_member_id")
    @classmethod
    def _validate_member_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not _MEMBER_ID_RE.match(v):
            raise ValueError("Insurance member ID must be alphanumeric (hyphens OK).")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def _validate_emerg_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        digits = _normalize_phone(v)
        if not _PHONE_RE.match(digits):
            raise ValueError("Emergency contact phone must be a valid U.S. 10-digit number.")
        return digits


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
