"""
Automated Setup & Verification Script for Vapi Assistant and Tools.

Usage:
    python scripts/setup_vapi.py --api-key <PRIVATE_VAPI_KEY> [--assistant-id <ID>] [--server-url <URL>]

This script:
1. Validates your Vapi private API key.
2. Creates or updates the 3 intake tools in your Vapi library (check_existing_patient, create_patient, update_patient).
3. Configures each tool with its exact JSON schema and your Railway server webhook URL.
4. Attaches the tools to your Vapi Assistant.
5. Updates the Assistant's system prompt from vapi_prompt.md.
6. Sets the Assistant's Server URL so both assistant-level and tool-level webhooks work.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

DEFAULT_RAILWAY_URL = "https://voice-ai-agent-patient-registration-system-production-b5a4.up.railway.app"
DEFAULT_ASSISTANT_ID = "63210c5e-8720-4026-8641-1a10d0c0b508"


def _api_request(url: str, method: str = "GET", data: dict = None, api_key: str = ""):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "CareCloud-Setup/1.0",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(error_body)
        except Exception:
            parsed = error_body
        return e.code, parsed


def load_tools_definitions(base_server_url: str):
    base_server_url = base_server_url.rstrip("/")
    tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vapi_tools")

    tools = [
        {
            "name": "check_existing_patient",
            "description": "Check if a patient already exists in the CareCloud database by their phone number. Call this as soon as phone number is provided to detect duplicates.",
            "schema_file": "parameters_schema_check_existing_patient.json",
            "url": f"{base_server_url}/vapi/check_existing_patient",
        },
        {
            "name": "create_patient",
            "description": "Create and persist a new patient registration record in the CareCloud database. Call this immediately AFTER the caller has confirmed all their information.",
            "schema_file": "parameters_schema_create_patient.json",
            "url": f"{base_server_url}/vapi/create_patient",
        },
        {
            "name": "update_patient",
            "description": "Update an existing patient record in the CareCloud database. Use when a duplicate record exists and the caller wishes to update their information.",
            "schema_file": "parameters_schema_update_patient.json",
            "url": f"{base_server_url}/vapi/update_patient",
        },
    ]

    loaded = []
    for t in tools:
        schema_path = os.path.join(tools_dir, t["schema_file"])
        with open(schema_path, "r", encoding="utf-8") as f:
            param_schema = json.load(f)

        tool_payload = {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": param_schema,
            },
            "server": {
                "url": t["url"],
                "timeoutSeconds": 20,
            },
        }
        loaded.append((t["name"], tool_payload))
    return loaded


def load_system_prompt():
    prompt_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vapi_prompt.md")
    with open(prompt_file, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("---")
    if len(parts) >= 3:
        return parts[2].strip()
    return content.strip()


def main():
    parser = argparse.ArgumentParser(description="Setup Vapi Assistant & Tools")
    parser.add_argument("--api-key", required=True, help="Your Private Vapi API Key (from dashboard.vapi.ai/api-keys)")
    parser.add_argument("--assistant-id", default=DEFAULT_ASSISTANT_ID, help="Your Assistant ID")
    parser.add_argument("--server-url", default=DEFAULT_RAILWAY_URL, help="Base Railway URL of your backend")
    args = parser.parse_args()

    api_key = args.api_key.strip()
    assistant_id = args.assistant_id.strip()
    server_url = args.server_url.strip().rstrip("/")

    print(f"\n[1/5] Verifying assistant {assistant_id} on Vapi...")
    code, assistant_data = _api_request(f"https://api.vapi.ai/assistant/{assistant_id}", "GET", api_key=api_key)
    if code != 200:
        print(f"Error fetching assistant: HTTP {code}: {assistant_data}")
        print("Please verify your Vapi Private API Key and Assistant ID.")
        sys.exit(1)
    print(f" Assistant found: '{assistant_data.get('name', 'Unnamed')}' ({assistant_id})")

    print("\n[2/5] Fetching existing tools from Vapi account...")
    code, existing_tools = _api_request("https://api.vapi.ai/tool", "GET", api_key=api_key)
    if code != 200:
        print(f"Warning: Could not list tools: HTTP {code}: {existing_tools}")
        existing_tools = []

    tools_by_name = {}
    for tool in existing_tools:
        fn_name = tool.get("function", {}).get("name") or tool.get("name")
        if fn_name:
            tools_by_name[fn_name] = tool.get("id")

    tool_defs = load_tools_definitions(server_url)
    configured_tool_ids = []

    print("\n[3/5] Synchronizing tools (check_existing_patient, create_patient, update_patient)...")
    for name, payload in tool_defs:
        if name in tools_by_name:
            tool_id = tools_by_name[name]
            print(f" Updating existing tool '{name}' (ID: {tool_id})...")
            code, resp = _api_request(f"https://api.vapi.ai/tool/{tool_id}", "PATCH", data=payload, api_key=api_key)
            if code == 200:
                print(f"   Updated tool '{name}'.")
                configured_tool_ids.append(tool_id)
            else:
                print(f"   Failed to update tool: {code} {resp}")
        else:
            print(f" Creating new tool '{name}'...")
            code, resp = _api_request("https://api.vapi.ai/tool", "POST", data=payload, api_key=api_key)
            if code in (200, 201):
                tool_id = resp.get("id")
                print(f"   Created tool '{name}' (ID: {tool_id}).")
                configured_tool_ids.append(tool_id)
            else:
                print(f"   Failed to create tool: {code} {resp}")

    print("\n[4/5] Reading updated system prompt from vapi_prompt.md...")
    prompt = load_system_prompt()
    print(f" Loaded prompt ({len(prompt)} characters).")

    print("\n[5/5] Attaching tools and updating assistant...")
    assistant_patch = {
        "serverUrl": f"{server_url}/vapi",
        "model": {
            **assistant_data.get("model", {}),
            "messages": [
                {"role": "system", "content": prompt}
            ],
            "toolIds": configured_tool_ids,
        },
    }
    code, update_resp = _api_request(f"https://api.vapi.ai/assistant/{assistant_id}", "PATCH", data=assistant_patch, api_key=api_key)
    if code == 200:
        print("\n SUCCESS! Vapi assistant and tools are now fully configured!")
        print(f"  • Assistant ID: {assistant_id}")
        print(f"  • Server URL: {server_url}/vapi")
        print(f"  • Attached Tool IDs: {configured_tool_ids}")
        print("  • System Prompt: Synced with vapi_prompt.md")
    else:
        print(f"Error updating assistant: HTTP {code}: {update_resp}")


if __name__ == "__main__":
    main()
