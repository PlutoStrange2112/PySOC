import json
import logging
import os
from enum import Enum

import azure.functions as func
import requests
from msal import ConfidentialClientApplication

logger = logging.getLogger(__name__)

GRAPH_ENDPOINT = os.environ.get("GRAPH_ENDPOINT", "https://graph.microsoft.com/v1.0")
DEFENDER_ENDPOINT = os.environ.get("DEFENDER_ENDPOINT", "https://api.securitycenter.microsoft.com/api")
AZURE_AUTH_ENDPOINT = os.environ.get("AZURE_AUTH_ENDPOINT", "https://login.microsoftonline.com")


class ResponseAction(str, Enum):
    DISABLE_USER = "disable_user"
    ISOLATE_MACHINE = "isolate_machine"
    REVOKE_SESSIONS = "revoke_sessions"
    BLOCK_IP = "block_ip"


def get_graph_token() -> str:
    # Local Docker testing: skip MSAL entirely when a mock token is injected
    mock_token = os.environ.get("MOCK_ACCESS_TOKEN")
    if mock_token:
        return mock_token

    tenant_id = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["AZURE_CLIENT_ID"]
    client_secret = os.environ["AZURE_CLIENT_SECRET"]

    app = ConfidentialClientApplication(
        client_id,
        authority=f"{AZURE_AUTH_ENDPOINT}/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(f"MSAL token acquisition failed: {result.get('error_description')}")
    return result["access_token"]


def disable_user(upn: str, token: str) -> dict:
    resp = requests.patch(
        f"{GRAPH_ENDPOINT}/users/{upn}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"accountEnabled": False},
        timeout=15,
    )
    resp.raise_for_status()
    logger.warning("Disabled AAD user: %s", upn)
    return {"action": ResponseAction.DISABLE_USER, "target": upn, "status": "success"}


def revoke_user_sessions(upn: str, token: str) -> dict:
    resp = requests.post(
        f"{GRAPH_ENDPOINT}/users/{upn}/revokeSignInSessions",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    logger.warning("Revoked sign-in sessions for: %s", upn)
    return {"action": ResponseAction.REVOKE_SESSIONS, "target": upn, "status": "success"}


def isolate_machine(machine_id: str, token: str, comment: str = "SOC auto-isolation") -> dict:
    resp = requests.post(
        f"{DEFENDER_ENDPOINT}/machines/{machine_id}/isolate",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"Comment": comment, "IsolationType": "Full"},
        timeout=15,
    )
    resp.raise_for_status()
    logger.warning("Isolation requested for machine: %s", machine_id)
    return {"action": ResponseAction.ISOLATE_MACHINE, "target": machine_id, "status": "success"}


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    incident_id = body.get("incidentId", "unknown")
    actions = body.get("actions", [])

    if not actions:
        return func.HttpResponse("No actions specified", status_code=400)

    results = []
    errors = []

    try:
        token = get_graph_token()
    except Exception as exc:
        logger.error("Token acquisition failed: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Authentication failed", "detail": str(exc)}),
            mimetype="application/json",
            status_code=500,
        )

    for action in actions:
        action_type = action.get("type")
        target = action.get("target", "")

        try:
            if action_type == ResponseAction.DISABLE_USER:
                results.append(disable_user(target, token))
            elif action_type == ResponseAction.REVOKE_SESSIONS:
                results.append(revoke_user_sessions(target, token))
            elif action_type == ResponseAction.ISOLATE_MACHINE:
                results.append(isolate_machine(target, token))
            else:
                errors.append({"action": action_type, "error": "Unknown action type"})
        except Exception as exc:
            logger.error("Action %s on %s failed: %s", action_type, target, exc)
            errors.append({"action": action_type, "target": target, "error": str(exc)})

    logger.info("Incident %s: %d actions taken, %d errors", incident_id, len(results), len(errors))
    return func.HttpResponse(
        json.dumps({"incidentId": incident_id, "results": results, "errors": errors}),
        mimetype="application/json",
        status_code=200 if not errors else 207,
    )
