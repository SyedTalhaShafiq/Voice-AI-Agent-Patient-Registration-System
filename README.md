# Voice AI Patient Registration System

A **Voice AI patient intake system** built with **Vapi** and **FastAPI**. Callers (or browser users) register as patients through natural conversation with an AI voice agent — no IVR menus, no rigid scripts. The agent collects demographics, validates fields, detects duplicates, and saves records to a database in real time.

> **Live demo:** [`https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app`](https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app)
>
> **Browser call demo (no phone needed):** [`/test`](https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app/test)
>
> **API docs:** [`/docs`](https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app/docs)

---

## 🎙️ How to Talk to the Agent (No Phone Required)

Since a US phone number is not available in all regions, the project ships a **browser-based voice client** that connects to the same live Vapi assistant using WebRTC — your microphone replaces the phone.

### Steps

1. Open the test page:
   ```
   https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app/test
   ```
2. Click **▶ Start Call** — your browser will ask for microphone permission, grant it.
3. Speak naturally. The assistant greets you and collects your patient information.
4. Watch the **live transcript** panel — it shows every utterance, tool call fired, and assistant response.
5. After the call, verify the patient record was saved:
   ```
   https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app/debug/patients
   ```

> **Note:** The `/test` page reads Vapi credentials securely from server-side environment variables — nothing is hardcoded or stored in the browser.

---

## Architecture

```
┌─────────────────────┐         ┌──────────────────────────────────────┐
│  Browser /test page │  WebRTC │              Vapi                     │
│  (mic + WebRTC)     │◄───────►│  Telephony + STT/TTS + LLM           │
│                     │         │  (hosts the voice assistant)          │
│  ─ ─ OR ─ ─         │         └──────────┬───────────────────────────┘
│  Phone call         │  voice             │ HTTPS tool calls (POST /vapi)
└─────────────────────┘                    ▼
                                ┌──────────────────────────┐
                                │   FastAPI Backend         │
                                │   (Railway)               │
                                │  ┌─────────────────────┐ │
                                │  │ REST API /patients   │ │  ← CRUD
                                │  └─────────────────────┘ │
                                │  ┌─────────────────────┐ │
                                │  │ Vapi Webhook /vapi   │ │  ← called mid-call
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
- `app/api/` — REST CRUD endpoints (public API)
- `app/vapi/` — Vapi webhook + tool handlers (Vapi integration)
- `app/debug.py` — DB verification endpoint
- `vapi_prompt.md` — The assistant's system prompt (prompt engineering)
- `vapi_tool_schemas.json` — Tool definitions for Vapi dashboard

---

## Tech Stack

| Choice | Why |
|---|---|
| **Python + FastAPI** | Fast to build, Pydantic validation, auto-generated `/docs`, async-ready |
| **SQLite** | Zero setup, single-file DB for demo. **Production:** swap to PostgreSQL |
| **SQLAlchemy** | Industry-standard ORM, clean migration path to Postgres |
| **Vapi** | Handles telephony, STT, TTS, and LLM orchestration in one platform |
| **Railway** | One-command deployment, auto-builds from GitHub, public URL |
| **pytest + httpx** | Standard Python testing stack with FastAPI `TestClient` |

---

## Project Structure

```
CareCloud/
├── app/
│   ├── __init__.py
│   ├── main.py              # App entry point, logging, table creation
│   ├── config.py            # Settings from .env / environment variables
│   ├── database.py          # SQLAlchemy engine + session
│   ├── debug.py             # Debug endpoint: GET /debug/patients
│   ├── seed.py              # Demo patient seed data
│   ├── models/
│   │   └── patient.py       # SQLAlchemy Patient model
│   ├── schemas/
│   │   └── patient.py       # Pydantic schemas + response envelope
│   ├── api/
│   │   └── routes.py        # REST CRUD endpoints
│   └── vapi/
│       ├── schemas.py       # Vapi request/response models
│       └── tools.py         # Vapi webhook dispatcher + tool handlers
├── scripts/
│   └── setup_vapi.py        # One-command Vapi tool registration script
├── tests/
│   ├── conftest.py          # pytest fixtures
│   └── test_api.py          # API + Vapi tool tests (36 tests)
├── vapi_tools/
│   ├── parameters_schema_check_existing_patient.json
│   ├── parameters_schema_create_patient.json
│   └── parameters_schema_update_patient.json
├── web_test/
│   └── index.html           # Browser voice client (no phone needed)
├── vapi_prompt.md           # Full system prompt for Vapi assistant
├── vapi_tool_schemas.json   # Tool definitions for Vapi dashboard
├── requirements.txt
├── railway.json             # Railway deployment config
├── Procfile
├── .env.example
└── README.md
```

---

## Step-by-Step Setup Guide

### Prerequisites

- Python 3.11+
- A [Vapi account](https://dashboard.vapi.ai) (free tier works)
- Git

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/SyedTalhaShafiq/Voice-AI-Agent-Patient-Registration-System.git
cd Voice-AI-Agent-Patient-Registration-System
```

---

### Step 2 — Create a virtual environment

```bash
# Create
python -m venv .venv

# Activate — Windows PowerShell
.venv\Scripts\Activate.ps1

# Activate — Mac/Linux
source .venv/bin/activate
```

---

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

---

### Step 4 — Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Vapi PUBLIC key (used by the /test browser client to start calls)
VAPI_API_KEY=your_vapi_public_key_here

# Vapi Assistant ID
ASSISTANT_API_KEY=your_vapi_assistant_id_here

# Database — leave as SQLite for local dev
DATABASE_URL=sqlite:///./patients.db

DEBUG=false
```

> Find your keys at [dashboard.vapi.ai](https://dashboard.vapi.ai):
> - **Public Key** → Account → API Keys
> - **Assistant ID** → Assistants → your assistant → copy the ID from the URL

---

### Step 5 — Run the server locally

```bash
uvicorn app.main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Browser voice client: `http://localhost:8000/test`

The SQLite database and demo seed data are created automatically on first run.

---

### Step 6 — (Local dev only) Expose your server to Vapi with ngrok

Vapi needs a public HTTPS URL to deliver tool calls. Use ngrok for local development:

```bash
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL — you'll use it as the Server URL in the next step.

> **Skip this step** if you're using the live Railway deployment — it's already public.

---

### Step 7 — Register Vapi tools

Run the setup script with your **Vapi Private API Key** (find it at [dashboard.vapi.ai/api-keys](https://dashboard.vapi.ai/api-keys) — different from the public key):

```bash
python scripts/setup_vapi.py --api-key YOUR_VAPI_PRIVATE_KEY
```

This automatically:
1. Creates/updates the 3 tools with their full JSON parameter schemas
2. Sets the Server URL to your deployed endpoint
3. Attaches the tools to your Vapi assistant
4. Syncs the system prompt from `vapi_prompt.md`

After running, refresh your [Vapi dashboard](https://dashboard.vapi.ai) and confirm each tool shows a populated **Parameters JSON** and correct **Server URL**.

#### Manual alternative

1. Open your Assistant in the [Vapi Dashboard](https://dashboard.vapi.ai)
2. **System Prompt** → paste the contents of [`vapi_prompt.md`](vapi_prompt.md)
3. **Server URL** → `https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app/vapi`
4. Under **Tools**, create each function tool and paste the matching schema from `vapi_tools/parameters_schema_*.json`

---

### Step 8 — Test the voice agent

**Option A — Browser (recommended, no phone needed):**

Open `http://localhost:8000/test`, click **▶ Start Call**, and speak to the agent.

**Option B — Simulate a tool call via PowerShell:**

```powershell
$body = '{"assistantId":"test","toolCallList":[{"toolCallId":"t1","name":"check_existing_patient","arguments":{"phone_number":"+15551234567"}}]}'
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/vapi" -ContentType "application/json" -Body $body
```

---

### Step 9 — Verify database persistence

```powershell
# List the most recent 20 patients
Invoke-RestMethod -Uri "http://localhost:8000/debug/patients"

# Look up a specific patient by phone number (digits only)
Invoke-RestMethod -Uri "http://localhost:8000/debug/patients/15551234567"
```

---

### Step 10 — Run the test suite

```bash
pytest tests/ -v
```

All 36 tests should pass. They cover:
- Patient CRUD (create, read, update, soft-delete)
- Field validation (name, DOB, state, ZIP, phone, sex, email)
- Vapi webhook dispatcher (tool calls, lifecycle events, batch calls)
- Duplicate detection, camelCase normalization, placeholder handling

---

## Live Deployment (Railway)

The project is deployed at:

```
https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app
```

| URL | Description |
|---|---|
| `/test` | **Browser voice client — click to call, no phone needed** |
| `/docs` | Interactive Swagger API documentation |
| `/health` | Health check |
| `/patients` | REST CRUD for patients |
| `/vapi` | Vapi webhook (tool calls + lifecycle events) |
| `/debug/patients` | Quick DB viewer (last 20 patients) |

### Deploy your own instance

1. Fork the repo
2. Create a new project on [Railway](https://railway.app)
3. Connect your GitHub repo — Railway auto-detects Python and builds with Nixpacks
4. Set environment variables in Railway:
   - `VAPI_API_KEY` — your Vapi public key
   - `ASSISTANT_API_KEY` — your Vapi assistant ID
5. Railway deploys automatically on every push to `main`

---

## REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/patients` | List all patients. Filters: `?last_name=`, `?phone_number=`, `?date_of_birth=` |
| `GET` | `/patients/{id}` | Get one patient by UUID |
| `POST` | `/patients` | Create a patient (validates all fields, returns 201) |
| `PUT` | `/patients/{id}` | Partial update (only provided fields change) |
| `DELETE` | `/patients/{id}` | Soft-delete (sets `deleted_at`, row remains) |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive Swagger UI |

All responses use a consistent envelope:

```json
{
  "data": { ... },
  "error": null
}
```

---

## Vapi Integration

### Conversation Flow

1. Caller starts a call (phone or browser `/test` page)
2. Agent greets naturally — not IVR-style
3. Collects required fields conversationally in logical groups
4. Validates each field; re-prompts only on errors
5. Offers optional fields (insurance, emergency contact, preferred language)
6. **Reads back all info** and asks for confirmation
7. Calls `check_existing_patient` silently to detect duplicates
8. On confirmation: calls `create_patient` (or `update_patient` for duplicates)
9. Relays success/failure in natural language
10. Closes the call gracefully

### Tool Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /vapi` | Universal dispatcher — handles all Vapi tool calls + lifecycle events |
| `POST /vapi/check_existing_patient` | Duplicate detection by phone number |
| `POST /vapi/create_patient` | Persist a new patient record |
| `POST /vapi/update_patient` | Update an existing patient record |

---

## Data Model

| Field | Type | Required | Validation |
|---|---|---|---|
| `patient_id` | UUID | Auto | Auto-generated |
| `first_name` | String(50) | ✅ | Letters, hyphens, apostrophes |
| `last_name` | String(50) | ✅ | Letters, hyphens, apostrophes |
| `date_of_birth` | Date | ✅ | Not future, not before 1900 |
| `sex` | Enum | ✅ | Male / Female / Other / Decline to Answer |
| `phone_number` | String(20) | ✅ | U.S. 10-digit |
| `email` | String(255) | — | Valid email format |
| `address_line_1` | String(255) | ✅ | Non-empty |
| `address_line_2` | String(255) | — | — |
| `city` | String(100) | ✅ | 1–100 chars |
| `state` | String(2) | ✅ | Valid 2-letter U.S. abbreviation |
| `zip_code` | String(10) | ✅ | 5-digit or ZIP+4 |
| `insurance_provider` | String(255) | — | — |
| `insurance_member_id` | String(255) | — | Alphanumeric + hyphens |
| `preferred_language` | String(100) | — | Default: "English" |
| `emergency_contact_name` | String(255) | — | — |
| `emergency_contact_phone` | String(20) | — | U.S. 10-digit |
| `created_at` | Timestamp | Auto | UTC |
| `updated_at` | Timestamp | Auto | UTC, set on modification |
| `deleted_at` | Timestamp | Auto | Nullable — set on soft-delete |

**Seed data:** 2 demo patients (Maria Garcia, James O'Connor) are auto-inserted on first run.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `VAPI_API_KEY` | Yes | — | Vapi **public** key (used by `/test` browser client) |
| `ASSISTANT_API_KEY` | Yes | — | Vapi assistant ID |
| `DATABASE_URL` | No | `sqlite:///./patients.db` | SQLAlchemy database URL |
| `DEBUG` | No | `false` | Enable verbose SQL logging |

All secrets are loaded from `.env` (gitignored). See `.env.example` for the template.

---

## Known Limitations & Trade-offs

| Limitation | Impact | Mitigation |
|---|---|---|
| **SQLite concurrency** | Single-writer; not for production | Swap `DATABASE_URL` to PostgreSQL |
| **No authentication** | API is open | Acceptable for demo; add JWT/API keys for production |
| **No rate limiting** | Could be abused | Acceptable for demo scope |
| **Dropped calls = no record** | Call must complete before confirmation | Design choice: no partial records |
| **Debug endpoint exposed** | `/debug/patients` is public | Remove `app/debug.py` before production |

---

## Next Steps (Production Roadmap)

1. **PostgreSQL** — Proper indexes on `phone_number`, `last_name`, `date_of_birth`
2. **Authentication** — API key middleware for REST endpoints
3. **Call transcript logging** — Vapi end-of-call webhook → store linked to patient records
4. **HIPAA** — Audit logging, encryption at rest, BAA with hosting provider
5. **Multi-language** — Bilingual Vapi prompts
6. **EHR integration** — HL7/FHIR export
7. **Analytics** — Registration completion rates, average call duration

---

## License

Take-home assessment project. Not intended for production use.
