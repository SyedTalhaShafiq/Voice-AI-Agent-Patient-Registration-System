"""Automated tests for the Patient REST API — CRUD happy paths and validation failures."""

import json


# ── valid patient payload factory ────────────────────────────────────

def _valid_patient(**overrides):
    base = {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
        "sex": "Female",
        "phone_number": "5551112222",
        "address_line_1": "123 Main Street",
        "city": "Springfield",
        "state": "IL",
        "zip_code": "62704",
    }
    base.update(overrides)
    return base


# ── CREATE ───────────────────────────────────────────────────────────

class TestCreatePatient:
    def test_create_happy_path(self, client):
        resp = client.post("/patients", json=_valid_patient())
        assert resp.status_code == 201
        body = resp.json()
        assert body["error"] is None
        patient = body["data"]
        assert patient["first_name"] == "Jane"
        assert patient["last_name"] == "Doe"
        assert "patient_id" in patient

    def test_create_with_optional_fields(self, client):
        resp = client.post(
            "/patients",
            json=_valid_patient(
                email="jane@example.com",
                insurance_provider="Aetna",
                insurance_member_id="AET-123456",
                preferred_language="Spanish",
                emergency_contact_name="John Doe",
                emergency_contact_phone="5553334444",
            ),
        )
        assert resp.status_code == 201
        patient = resp.json()["data"]
        assert patient["email"] == "jane@example.com"
        assert patient["insurance_provider"] == "Aetna"

    def test_create_invalid_name_digits(self, client):
        resp = client.post("/patients", json=_valid_patient(first_name="123"))
        assert resp.status_code == 422

    def test_create_future_dob(self, client):
        resp = client.post("/patients", json=_valid_patient(date_of_birth="2099-01-01"))
        assert resp.status_code == 422

    def test_create_invalid_state(self, client):
        resp = client.post("/patients", json=_valid_patient(state="XX"))
        assert resp.status_code == 422

    def test_create_invalid_zip(self, client):
        resp = client.post("/patients", json=_valid_patient(zip_code="123"))
        assert resp.status_code == 422

    def test_create_invalid_phone(self, client):
        resp = client.post("/patients", json=_valid_patient(phone_number="123"))
        assert resp.status_code == 422

    def test_create_invalid_sex(self, client):
        resp = client.post("/patients", json=_valid_patient(sex="Alien"))
        assert resp.status_code == 422

    def test_create_invalid_email(self, client):
        resp = client.post("/patients", json=_valid_patient(email="not-an-email"))
        assert resp.status_code == 422


# ── READ ─────────────────────────────────────────────────────────────

class TestReadPatient:
    def test_get_by_id(self, client):
        # Create first
        create_resp = client.post("/patients", json=_valid_patient(phone_number="5552223333"))
        pid = create_resp.json()["data"]["patient_id"]

        # Read
        resp = client.get(f"/patients/{pid}")
        assert resp.status_code == 200
        assert resp.json()["data"]["patient_id"] == pid

    def test_get_nonexistent(self, client):
        resp = client.get("/patients/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_list_patients(self, client):
        resp = client.get("/patients")
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], list)

    def test_filter_by_last_name(self, client):
        client.post("/patients", json=_valid_patient(
            first_name="Filter", last_name="Testname", phone_number="5554445555"
        ))
        resp = client.get("/patients?last_name=Testname")
        assert resp.status_code == 200
        names = [p["last_name"] for p in resp.json()["data"]]
        assert any("Testname" in n for n in names)

    def test_filter_by_phone(self, client):
        client.post("/patients", json=_valid_patient(phone_number="5556667777"))
        resp = client.get("/patients?phone_number=5556667777")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1


# ── UPDATE ───────────────────────────────────────────────────────────

class TestUpdatePatient:
    def test_update_city(self, client):
        create_resp = client.post("/patients", json=_valid_patient(phone_number="5558889999"))
        pid = create_resp.json()["data"]["patient_id"]

        resp = client.put(f"/patients/{pid}", json={"city": "Chicago"})
        assert resp.status_code == 200
        assert resp.json()["data"]["city"] == "Chicago"

    def test_update_multiple_fields(self, client):
        create_resp = client.post("/patients", json=_valid_patient(phone_number="5551010101"))
        pid = create_resp.json()["data"]["patient_id"]

        resp = client.put(f"/patients/{pid}", json={
            "city": "Decatur",
            "state": "GA",
            "zip_code": "30030",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["city"] == "Decatur"
        assert data["state"] == "GA"

    def test_update_nonexistent(self, client):
        resp = client.put(
            "/patients/00000000-0000-0000-0000-000000000000",
            json={"city": "Nowhere"},
        )
        assert resp.status_code == 404

    def test_update_invalid_state(self, client):
        create_resp = client.post("/patients", json=_valid_patient(phone_number="5552020202"))
        pid = create_resp.json()["data"]["patient_id"]

        resp = client.put(f"/patients/{pid}", json={"state": "ZZ"})
        assert resp.status_code == 422


# ── DELETE (soft) ────────────────────────────────────────────────────

class TestDeletePatient:
    def test_soft_delete(self, client):
        create_resp = client.post("/patients", json=_valid_patient(phone_number="5553030303"))
        pid = create_resp.json()["data"]["patient_id"]

        # Delete
        del_resp = client.delete(f"/patients/{pid}")
        assert del_resp.status_code == 200

        # Should now 404
        resp = client.get(f"/patients/{pid}")
        assert resp.status_code == 404

    def test_soft_delete_nonexistent(self, client):
        resp = client.delete("/patients/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_soft_deleted_excluded_from_list(self, client):
        create_resp = client.post("/patients", json=_valid_patient(
            first_name="Deleted", last_name="Person", phone_number="5554040404"
        ))
        pid = create_resp.json()["data"]["patient_id"]
        client.delete(f"/patients/{pid}")

        resp = client.get("/patients?last_name=Person")
        ids = [p["patient_id"] for p in resp.json()["data"]]
        assert pid not in ids


# ── RESPONSE ENVELOPE ────────────────────────────────────────────────

class TestEnvelope:
    def test_success_has_data_and_null_error(self, client):
        resp = client.get("/patients")
        body = resp.json()
        assert "data" in body
        assert "error" in body
        assert body["error"] is None

    def test_error_envelope_on_404(self, client):
        """404s from HTTPException still return JSON (FastAPI default detail)."""
        resp = client.get("/patients/nonexistent-uuid")
        assert resp.status_code == 404


# ── VAPI TOOL ENDPOINTS ─────────────────────────────────────────────

class TestVapiTools:
    def _tool_call_payload(self, tool_name: str, arguments: dict) -> dict:
        """Wrap args in Vapi's expected webhook envelope."""
        return {
            "message": {
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "call_test",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(arguments),
                        },
                    }
                ],
            }
        }

    def test_check_existing_no_match(self, client):
        payload = self._tool_call_payload(
            "check_existing_patient",
            {"phone_number": "5550000000"},
        )
        resp = client.post("/vapi/check_existing_patient", json=payload)
        assert resp.status_code == 200
        assert "NO_DUPLICATE" in resp.json()["result"]

    def test_check_existing_duplicate(self, client):
        # Create a patient first
        client.post("/patients", json=_valid_patient(phone_number="5557777777"))

        payload = self._tool_call_payload(
            "check_existing_patient",
            {"phone_number": "5557777777"},
        )
        resp = client.post("/vapi/check_existing_patient", json=payload)
        assert resp.status_code == 200
        assert "DUPLICATE_FOUND" in resp.json()["result"]

    def test_create_patient_via_vapi(self, client):
        args = {
            "first_name": "Vapi",
            "last_name": "Caller",
            "date_of_birth": "06/15/1988",
            "sex": "Male",
            "phone_number": "5558881234",
            "address_line_1": "999 Vapi Lane",
            "city": "Austin",
            "state": "TX",
            "zip_code": "73301",
        }
        payload = self._tool_call_payload("create_patient", args)
        resp = client.post("/vapi/create_patient", json=payload)
        assert resp.status_code == 200
        assert "SUCCESS" in resp.json()["result"]

        # Verify it's in the DB
        list_resp = client.get("/patients?phone_number=5558881234")
        assert len(list_resp.json()["data"]) >= 1

    def test_create_patient_invalid_data_via_vapi(self, client):
        args = {
            "first_name": "123Bad",
            "last_name": "Name",
            "date_of_birth": "01/01/1990",
            "sex": "Male",
            "phone_number": "5559998888",
            "address_line_1": "1 Test St",
            "city": "TestCity",
            "state": "NY",
            "zip_code": "10001",
        }
        payload = self._tool_call_payload("create_patient", args)
        resp = client.post("/vapi/create_patient", json=payload)
        assert resp.status_code == 200
        assert "ERROR" in resp.json()["result"]

    def test_update_patient_via_vapi(self, client):
        # Create
        create_resp = client.post("/patients", json=_valid_patient(phone_number="5556661234"))
        pid = create_resp.json()["data"]["patient_id"]

        args = {"patient_id": pid, "city": "Updated City"}
        payload = self._tool_call_payload("update_patient", args)
        resp = client.post("/vapi/update_patient", json=payload)
        assert resp.status_code == 200
        assert "SUCCESS" in resp.json()["result"]

        # Verify update
        get_resp = client.get(f"/patients/{pid}")
        assert get_resp.json()["data"]["city"] == "Updated City"

    def test_create_patient_real_vapi_shape(self, client):
        """Vapi's documented webhook puts id/name/arguments at the top level of
        each toolCallList entry, with arguments as an OBJECT (not a JSON string).
        The handler must read that shape and persist the record."""
        payload = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "toolu_realshape_123",
                        "name": "create_patient",
                        "arguments": {
                            "first_name": "Real",
                            "last_name": "Shape",
                            "date_of_birth": "09/09/1990",
                            "sex": "Female",
                            "phone_number": "5554443210",
                            "address_line_1": "1 Vapi Way",
                            "city": "Seattle",
                            "state": "WA",
                            "zip_code": "98101",
                        },
                    }
                ],
            }
        }
        resp = client.post("/vapi/create_patient", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        # Vapi-required envelope
        assert body["results"][0]["toolCallId"] == "toolu_realshape_123"
        assert "SUCCESS" in body["results"][0]["result"]
        # And it must actually be saved in the DB
        list_resp = client.get("/patients?phone_number=5554443210")
        assert len(list_resp.json()["data"]) == 1
        assert list_resp.json()["data"][0]["first_name"] == "Real"

    def test_universal_webhook_at_vapi_root(self, client):
        """Vapi Assistant Server URL set to /vapi triggers tool execution via dispatcher."""
        payload = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "call_webhook_1",
                        "name": "create_patient",
                        "arguments": {
                            "first_name": "Webhook",
                            "last_name": "Caller",
                            "date_of_birth": "04/20/1985",
                            "sex": "Female",
                            "phone_number": "5559991122",
                            "address_line_1": "100 Server Road",
                            "city": "Denver",
                            "state": "CO",
                            "zip_code": "80201",
                        },
                    }
                ],
            }
        }
        resp = client.post("/vapi", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"][0]["toolCallId"] == "call_webhook_1"
        assert "SUCCESS" in data["results"][0]["result"]

        saved = client.get("/patients?phone_number=5559991122").json()["data"]
        assert len(saved) == 1
        assert saved[0]["first_name"] == "Webhook"

    def test_root_post_and_webhook_alias(self, client):
        """Assistant Server URL set to / or /webhook also dispatches successfully."""
        payload = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "call_alias_1",
                        "name": "check_existing_patient",
                        "arguments": {"phone_number": "5559991122"},
                    }
                ],
            }
        }
        # POST /webhook
        resp_webhook = client.post("/webhook", json=payload)
        assert resp_webhook.status_code == 200
        assert "DUPLICATE_FOUND" in resp_webhook.json()["results"][0]["result"]

        # POST /
        resp_root = client.post("/", json=payload)
        assert resp_root.status_code == 200
        assert "DUPLICATE_FOUND" in resp_root.json()["results"][0]["result"]

    def test_batched_tool_calls(self, client):
        """Vapi can send multiple tool calls in a single toolCallList."""
        payload = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "call_batch_1",
                        "name": "check_existing_patient",
                        "arguments": {"phone_number": "5550009999"},
                    },
                    {
                        "id": "call_batch_2",
                        "name": "create_patient",
                        "arguments": {
                            "first_name": "Batch",
                            "last_name": "Patient",
                            "date_of_birth": "1991-07-23",
                            "sex": "Male",
                            "phone_number": "5550009999",
                            "address_line_1": "200 Batch Way",
                            "city": "Boston",
                            "state": "MA",
                            "zip_code": "02108",
                        },
                    },
                ],
            }
        }
        resp = client.post("/vapi", json=payload)
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 2
        assert results[0]["toolCallId"] == "call_batch_1"
        assert "NO_DUPLICATE" in results[0]["result"]
        assert results[1]["toolCallId"] == "call_batch_2"
        assert "SUCCESS" in results[1]["result"]

    def test_vapi_lifecycle_events_return_ok(self, client):
        """Non-tool-call events from Vapi should return HTTP 200 {status: ok}."""
        for event_type in ["status-update", "speech-update", "transcript", "end-of-call-report"]:
            payload = {"message": {"type": event_type, "call": {"id": "call_123"}}}
            resp = client.post("/vapi", json=payload)
            assert resp.status_code == 200
            assert resp.json().get("status") == "ok"

    def test_create_patient_with_voice_placeholders(self, client):
        """LLMs passing 'not provided', 'none', 'n/a' for optional fields must not crash validation."""
        payload = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "call_ph_1",
                        "name": "create_patient",
                        "arguments": {
                            "first_name": "Grace",
                            "last_name": "Hopper",
                            "date_of_birth": "12/09/1906",
                            "sex": "Female",
                            "phone_number": "5551239876",
                            "address_line_1": "1 Navy Pier",
                            "address_line_2": "none",
                            "city": "New York",
                            "state": "NY",
                            "zip_code": "10001",
                            "email": "not provided",
                            "insurance_provider": "not provided",
                            "insurance_member_id": "none",
                            "preferred_language": "English",
                            "emergency_contact_name": "not provided",
                            "emergency_contact_phone": "not provided",
                        },
                    }
                ],
            }
        }
        resp = client.post("/vapi/create_patient", json=payload)
        assert resp.status_code == 200
        assert "SUCCESS" in resp.json()["results"][0]["result"]

        patient = client.get("/patients?phone_number=5551239876").json()["data"][0]
        assert patient["email"] is None
        assert patient["emergency_contact_phone"] is None
        assert patient["insurance_provider"] is None

    def test_create_patient_full_state_and_conversational_sex(self, client):
        """Full state name 'California' converts to 'CA', 'man' converts to 'Male'."""
        payload = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "call_full_state",
                        "name": "create_patient",
                        "arguments": {
                            "first_name": "Alan",
                            "last_name": "Turing",
                            "date_of_birth": "06/23/1912",
                            "sex": "man",
                            "phone_number": "5553214567",
                            "address_line_1": "42 Bletchley Park",
                            "city": "San Francisco",
                            "state": "California",
                            "zip_code": "94102",
                        },
                    }
                ],
            }
        }
        resp = client.post("/vapi/create_patient", json=payload)
        assert resp.status_code == 200
        assert "SUCCESS" in resp.json()["results"][0]["result"]

        patient = client.get("/patients?phone_number=5553214567").json()["data"][0]
        assert patient["state"] == "CA"
        assert patient["sex"] == "Male"

    def test_create_patient_camel_case_args(self, client):
        """CamelCase arguments commonly emitted by LLMs are normalized to snake_case."""
        payload = {
            "message": {
                "type": "tool-calls",
                "toolCallList": [
                    {
                        "id": "call_camel",
                        "name": "create_patient",
                        "arguments": {
                            "firstName": "Ada",
                            "lastName": "Lovelace",
                            "dateOfBirth": "12/10/1915",
                            "sex": "woman",
                            "phoneNumber": "5558889900",
                            "addressLine1": "12 St James Square",
                            "city": "Austin",
                            "state": "Texas",
                            "zipCode": "78701",
                        },
                    }
                ],
            }
        }
        resp = client.post("/vapi", json=payload)
        assert resp.status_code == 200
        assert "SUCCESS" in resp.json()["results"][0]["result"]

        patient = client.get("/patients?phone_number=5558889900").json()["data"][0]
        assert patient["first_name"] == "Ada"
        assert patient["last_name"] == "Lovelace"
        assert patient["state"] == "TX"
        assert patient["sex"] == "Female"

