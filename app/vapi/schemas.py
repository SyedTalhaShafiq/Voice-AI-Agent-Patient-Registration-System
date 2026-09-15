"""Vapi-specific request/response schemas for tool-calling webhooks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Vapi tool-call request envelope ──────────────────────────────────
# Vapi sends a POST with this shape when the assistant triggers a tool.

class VapiToolCallRequest(BaseModel):
    """Incoming tool-call payload from Vapi."""
    message: VapiMessage | None = None


class VapiMessage(BaseModel):
    type: str | None = None
    toolCallList: list[VapiToolCall] = []


class VapiToolCall(BaseModel):
    id: str = ""
    type: str = "function"
    function: VapiFunction = Field(default_factory=lambda: VapiFunction())


class VapiFunction(BaseModel):
    name: str = ""
    arguments: str = "{}"


# ── Vapi tool response ───────────────────────────────────────────────

class VapiToolResponse(BaseModel):
    """Response that Vapi expects back from a tool call."""
    result: str  # A human-readable string the LLM will use in its reply


# ── Simplified tool argument schemas (what the LLM passes) ──────────

class CheckExistingPatientArgs(BaseModel):
    phone_number: str


class CreatePatientToolArgs(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str  # MM/DD/YYYY — parsed in handler
    sex: str
    phone_number: str
    address_line_1: str
    city: str
    state: str
    zip_code: str
    email: str | None = None
    address_line_2: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class UpdatePatientToolArgs(BaseModel):
    patient_id: str
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None
    sex: str | None = None
    phone_number: str | None = None
    address_line_1: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    email: str | None = None
    address_line_2: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
