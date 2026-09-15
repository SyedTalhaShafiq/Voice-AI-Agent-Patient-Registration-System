# CareCloud — Voice AI Patient Registration System

A take-home technical assessment for a **Voice AI / Conversational AI Engineer** role. This system pairs a **Vapi-powered voice agent** with a **Python/FastAPI backend** to let callers register as patients over the phone using natural conversation — no IVR menus, no rigid scripts.

---

## Architecture

```
┌────────────────┐         ┌──────────────────────────────────┐
│   Caller       │  voice  │            Vapi                   │
│  (phone)       │◄───────►│  Telephony + STT/TTS + LLM       │
└────────────────┘         │  (hosts the voice assistant)      │
                           └──────────┬───────────────────────┘
                                      │ HTTPS tool calls
                                      ▼
                           ┌──────────────────────────┐
                           │   FastAPI Backend         │
                           │                          │
                           │  ┌─────────────────────┐ │
                           │  │ REST API /patients   │ │  ← queryable by anyone
                           │  └─────────────────────┘ │
                           │  ┌─────────────────────┐ │
                           │  │ Vapi Tool Handlers   │ │  ← called by Vapi mid-call
                           │  └─────────────────────┘ │
                           └────────────┬─────────────┘
                                        │
                                        ▼
                           ┌──────────────────────┐
                           │  SQLite (patients.db) │
                           └──────────────────────┘
```

**Separation of concerns:**
- `app/models/` — SQLAlchemy ORM (data layer)
- `app/schemas/` — Pydantic validation (validation layer)
- `app/api/` — REST endpoints (public API)
- `app/vapi/` — Tool/webhook handlers (Vapi integration)
- `vapi_prompt.md` — The assistant's system prompt (prompt engineering artifact)
- `vapi_tool_schemas.json` — Tool definitions to paste into Vapi dashboard

---

## Tech Stack & Justification

| Choice | Why |
|---|---|
| **Python + FastAPI** | Fast to build, Pydantic for validation, auto-generated `/docs` for reviewers, async-ready |
| **SQLite** | Zero setup, single-file DB, perfect for a 3-hour demo. **Production note:** swap to PostgreSQL for concurrency, durability, and proper enum types |
| **SQLAlchemy** | Industry-standard ORM, clean separation, easy migration path to Postgres |
| **Vapi** | Handles telephony, STT, TTS, and LLM orchestration in one platform; server-side tool calling fits this architecture cleanly |
| **pytest + httpx** | Standard Python testing stack; httpx provides the `TestClient` for FastAPI |

---

## Project Structure

```
CareCloud/
├── app/
│   ├── __init__.py
│   ├── main.py              # App entry point, logging, table creation
│   ├── config.py             # Settings from .env
│   ├── database.py           # SQLAlchemy engine + session
│   ├── seed.py               # Demo patient seed data
│   ├── models/
│   │   └── patient.py        # SQLAlchemy Patient model
│   ├── schemas/
│   │   └── patient.py        # Pydantic schemas + response envelope
│   ├── api/
│   │   └── routes.py         # REST CRUD endpoints
│   └── vapi/
│       ├── schemas.py        # Vapi request/response models
│       └── tools.py          # Vapi tool-call handlers
├── tests/
│   ├── conftest.py           # pytest fixtures
│   └── test_api.py           # API + Vapi tool tests
├── vapi_prompt.md            # Full system prompt for Vapi assistant
├── vapi_tool_schemas.json    # Tool JSON schemas for Vapi config
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- A Vapi account ([dashboard.vapi.ai](https://dashboard.vapi.ai))

### 2. Setup

```bash
# Clone / navigate to the project
cd CareCloud

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your VAPI_API_KEY

# Run the server
uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 3. Expose for Vapi (local development)

Vapi needs a public URL to call your tool endpoints. Use ngrok:

```bash
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL and replace `YOUR_DEPLOYED_URL` in `vapi_tool_schemas.json`.

### 4. Configure Vapi Assistant & Tools

You can configure Vapi either automatically via script or manually in the Dashboard:

#### Option A: Automated Configuration (Fastest)
Run the setup script with your Vapi **Private API Key** (from [dashboard.vapi.ai/api-keys](https://dashboard.vapi.ai/api-keys)):
```bash
python scripts/setup_vapi.py --api-key YOUR_PRIVATE_VAPI_KEY
```
This automatically registers the 3 tools with their schemas and URLs, attaches them to your assistant (`63210c5e-8720-4026-8641-1a10d0c0b508`), sets the Server URL, and syncs the system prompt.

#### Option B: Manual Dashboard Configuration
1. Log into [Vapi Dashboard](https://dashboard.vapi.ai)
2. Open your Assistant:
   - **System Prompt**: Copy and paste the entire prompt from [`vapi_prompt.md`](vapi_prompt.md).
   - **Server URL**: Set to `https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app/vapi`.
3. Under **Tools**, create/edit each function tool:
   - `check_existing_patient`: Copy schema from `vapi_tools/parameters_schema_check_existing_patient.json` into the Parameters editor.
   - `create_patient`: Copy schema from `vapi_tools/parameters_schema_create_patient.json` into the Parameters editor.
   - `update_patient`: Copy schema from `vapi_tools/parameters_schema_update_patient.json` into the Parameters editor.
   - Set Server URL on each tool to `https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app/vapi/<tool_name>` (or leave blank to inherit Assistant Server URL).
4. Save the Assistant and test!

---

## REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/patients` | List all non-deleted patients. Filters: `?last_name=`, `?date_of_birth=MM/DD/YYYY`, `?phone_number=` |
| `GET` | `/patients/{id}` | Get one patient by UUID (404 if deleted) |
| `POST` | `/patients` | Create patient (validates all fields, returns 201) |
| `PUT` | `/patients/{id}` | Partial update (only provided fields change) |
| `DELETE` | `/patients/{id}` | Soft-delete (sets `deleted_at`, row remains) |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive Swagger UI (auto-generated by FastAPI) |

All responses use a consistent envelope:
```json
{
  "data": { ... },
  "error": null
}
```

---

## Vapi Integration

### Webhook & Tool Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /vapi` | Universal webhook dispatcher for Assistant Server URL (handles `tool-calls` & lifecycle events) |
| `POST /webhook` | Alias for universal webhook |
| `POST /vapi/check_existing_patient` | Duplicate detection by phone number |
| `POST /vapi/create_patient` | Persist a confirmed new patient |
| `POST /vapi/update_patient` | Update an existing patient's record |

### Conversation Flow

1. Caller dials the Vapi-provisioned number
2. Agent greets naturally (not IVR-style)
3. Collects required fields conversationally in logical groups
4. Validates each field, re-prompts only on errors
5. Offers optional fields (insurance, emergency contact, language)
6. **Reads back all info** and asks for confirmation
7. Calls `check_existing_patient` to detect duplicates
8. On confirmation, calls `create_patient` (or `update_patient` if duplicate)
9. Relays success/failure to caller in natural language
10. Closes the call gracefully

### Prompt Engineering

The full system prompt is documented in [`vapi_prompt.md`](vapi_prompt.md) with comments explaining each behavioral instruction:
- Natural greeting (not robotic)
- Grouped field collection
- Field-level validation re-prompting
- Optional fields: offer, don't force
- Confirmation-before-save (critical)
- Duplicate detection flow
- Correction handling mid-conversation
- Restart handling
- Graceful error messaging
- Call closing

---

## Data Model

| Field | Type | Required | Validation |
|---|---|---|---|
| `patient_id` | UUID | Auto | Auto-generated |
| `first_name` | String(50) | Yes | Letters, hyphens, apostrophes |
| `last_name` | String(50) | Yes | Letters, hyphens, apostrophes |
| `date_of_birth` | Date | Yes | Not future, not before 1900 |
| `sex` | Enum | Yes | Male/Female/Other/Decline to Answer |
| `phone_number` | String(20) | Yes | U.S. 10-digit |
| `email` | String(255) | No | Valid email format |
| `address_line_1` | String(255) | Yes | Non-empty |
| `address_line_2` | String(255) | No | — |
| `city` | String(100) | Yes | 1-100 chars |
| `state` | String(2) | Yes | Valid 2-letter U.S. state |
| `zip_code` | String(10) | Yes | 5-digit or ZIP+4 |
| `insurance_provider` | String(255) | No | — |
| `insurance_member_id` | String(255) | No | Alphanumeric + hyphens |
| `preferred_language` | String(100) | No | Default: "English" |
| `emergency_contact_name` | String(255) | No | — |
| `emergency_contact_phone` | String(20) | No | U.S. 10-digit |
| `created_at` | Timestamp | Auto | UTC |
| `updated_at` | Timestamp | Auto | UTC, on modification |
| `deleted_at` | Timestamp | Auto | Nullable, set on soft-delete |

**Seed data:** 2 demo patients (Maria Garcia, James O'Connor) are auto-inserted on first run.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage (if pytest-cov installed)
pytest tests/ -v --cov=app
```

Tests cover:
- **Create:** happy path, optional fields, invalid name/DOB/state/ZIP/phone/sex/email
- **Read:** by ID, nonexistent (404), list, filter by last_name/phone
- **Update:** single field, multiple fields, nonexistent (404), invalid state
- **Delete:** soft-delete, nonexistent (404), excluded from list
- **Envelope:** success format, error format
- **Vapi tools:** check duplicate (no match/match), create via Vapi, invalid data via Vapi, update via Vapi

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `VAPI_API_KEY` | Yes | — | Vapi dashboard API key |
| `DATABASE_URL` | No | `sqlite:///./patients.db` | SQLAlchemy database URL |
| `DEBUG` | No | `false` | Enable verbose SQL logging |

All secrets are loaded from `.env` (gitignored). See `.env.example` for a template.

---

## Logging

All significant events are logged to **stdout** with timestamps:
- Patient CRUD operations (create, update, delete)
- Vapi tool calls (duplicate checks, creates, updates)
- Completed call payloads as **JSON lines** for easy inspection
- Database errors with full tracebacks

Example log line:
```
2026-01-15T14:32:00 | INFO    | app.vapi.tools | {"event": "patient_created_via_vapi", "patient_id": "abc-123", ...}
```

---

## Deployment

For the demo, deploy to any platform that provides a public URL:

- **Railway:** `railway up` (auto-detects Python)
- **Render:** connect repo, set build command `pip install -r requirements.txt`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Fly.io:** `fly launch` then `fly deploy`
- **ngrok** (local): `ngrok http 8000`

After deploying, update the `server.url` in `vapi_tool_schemas.json` with your public URL and re-configure the Vapi assistant tools.

---

## Known Limitations & Trade-offs

| Limitation | Impact | Mitigation |
|---|---|---|
| **SQLite concurrency** | Single-writer; not suitable for production | Documented; swap to Postgres for production |
| **No authentication** | API is open | Acceptable for demo; would add JWT/API keys for production |
| **No rate limiting** | Could be abused | Acceptable for demo scope |
| **Dropped calls = no record** | If call drops before confirmation, nothing is persisted | This is a **design choice**: no partial records. Caller must call back |
| **Phone normalization** | Only strips formatting and leading "1" | Sufficient for U.S. numbers; would add libphonenumber for international |
| **No call recording/transcript storage** | Vapi handles this natively | Would add webhook to store transcripts in production |
| **Soft-delete only** | Deleted records remain in DB | Acceptable; would add hard-delete/purge policy for production |

---

## Next Steps (if more time were available)

1. **Production database:** Migrate to PostgreSQL with proper indexes on `phone_number`, `last_name`, `date_of_birth`
2. **Authentication:** Add API key middleware for REST endpoints
3. **Call transcript logging:** Vapi webhook → store transcripts linked to patient records
4. **Retry logic:** Add exponential backoff on DB writes
5. **HIPAA considerations:** Audit logging, encryption at rest, access controls, BAA with hosting provider
6. **Multi-language support:** Configure Vapi with bilingual prompts
7. **EHR integration:** HL7/FHIR export of patient records
8. **Analytics dashboard:** Registration completion rates, average call duration, field correction frequency

---

## License

This is a take-home assessment project. Not intended for production use.
