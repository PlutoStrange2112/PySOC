"""
Mock server that simulates Azure Sentinel / Microsoft Graph endpoints
for local Docker testing without real Azure credentials.
"""
import json
import logging
from datetime import datetime, timezone

from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory store for mock data
_incidents: dict[str, dict] = {}
_indicators: list[dict] = []
_teams_messages: list[dict] = []
_action_log: list[dict] = []


def _sample_incidents() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "id": "inc-0001", "name": "inc-0001",
            "properties": {
                "title": "Brute Force Attack Detected",
                "status": "New", "severity": "High",
                "incidentNumber": 1,
                "createdTimeUtc": now, "lastModifiedTimeUtc": now,
                "owner": {"userPrincipalName": ""},
                "additionalData": {"alertsCount": 3},
                "labels": [],
            },
        },
        {
            "id": "inc-0002", "name": "inc-0002",
            "properties": {
                "title": "Impossible Travel Detected",
                "status": "Active", "severity": "Medium",
                "incidentNumber": 2,
                "createdTimeUtc": now, "lastModifiedTimeUtc": now,
                "owner": {"userPrincipalName": "analyst@corp.com"},
                "additionalData": {"alertsCount": 1},
                "labels": [{"labelName": "investigation"}],
            },
        },
        {
            "id": "inc-0003", "name": "inc-0003",
            "properties": {
                "title": "New Global Admin Added",
                "status": "Closed", "severity": "High",
                "incidentNumber": 3,
                "createdTimeUtc": now, "lastModifiedTimeUtc": now,
                "owner": {"userPrincipalName": "lead@corp.com"},
                "additionalData": {"alertsCount": 1},
                "labels": [{"labelName": "resolved"}],
            },
        },
    ]


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


# --- Mock Sentinel Incident endpoints ---

@app.get("/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<ws>/providers/Microsoft.SecurityInsights/incidents")
def list_incidents(sub, rg, ws):
    top = int(request.args.get("$top", 200))
    results = list(_incidents.values())
    # Seed with sample data on first call so the endpoint is immediately useful
    if not results:
        for sample in _sample_incidents():
            _incidents[sample["name"]] = sample
        results = list(_incidents.values())
    return jsonify({"value": results[:top]})


@app.get("/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<ws>/providers/Microsoft.SecurityInsights/incidents/<incident_id>")
def get_incident(sub, rg, ws, incident_id):
    incident = _incidents.get(incident_id)
    if not incident:
        return jsonify({"error": "Not found"}), 404
    return jsonify(incident)


@app.post("/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<ws>/providers/Microsoft.SecurityInsights/incidents")
def create_incident(sub, rg, ws):
    data = request.get_json()
    incident_id = f"inc-{len(_incidents) + 1:04d}"
    incident = {
        "id": incident_id,
        "name": incident_id,
        "properties": {**data.get("properties", {}), "incidentNumber": len(_incidents) + 1},
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    _incidents[incident_id] = incident
    logger.info("Created mock incident: %s", incident_id)
    return jsonify(incident), 201


@app.post("/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<ws>/providers/Microsoft.SecurityInsights/incidents/<incident_id>/comments")
def add_incident_comment(sub, rg, ws, incident_id):
    data = request.get_json()
    comment = {
        "incidentId": incident_id,
        "message": data.get("properties", {}).get("message", ""),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Comment on incident %s: %s", incident_id, comment["message"][:80])
    return jsonify(comment), 201


# --- Mock Sentinel Threat Intelligence endpoints ---

@app.post("/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<ws>/providers/Microsoft.SecurityInsights/threatIntelligence/main/createIndicator")
def create_indicator(sub, rg, ws):
    data = request.get_json()
    _indicators.append(data)
    logger.info("Received TI indicator: %s", data.get("properties", {}).get("pattern", ""))
    return jsonify({"id": f"ti-{len(_indicators)}"}), 201


@app.get("/ti-indicators")
def list_indicators():
    return jsonify({"count": len(_indicators), "indicators": _indicators})


# --- Mock Microsoft Graph endpoints ---

@app.patch("/v1.0/users/<upn>")
def patch_user(upn):
    data = request.get_json()
    action = {"type": "patch_user", "upn": upn, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()}
    _action_log.append(action)
    logger.warning("Mock: patched user %s with %s", upn, data)
    return jsonify({}), 204


@app.post("/v1.0/users/<upn>/revokeSignInSessions")
def revoke_sessions(upn):
    action = {"type": "revoke_sessions", "upn": upn, "timestamp": datetime.now(timezone.utc).isoformat()}
    _action_log.append(action)
    logger.warning("Mock: revoked sessions for %s", upn)
    return jsonify({"value": True})


# --- Mock Defender endpoint ---

@app.post("/api/machines/<machine_id>/isolate")
def isolate_machine(machine_id):
    data = request.get_json()
    action = {"type": "isolate", "machineId": machine_id, "comment": data.get("Comment"), "timestamp": datetime.now(timezone.utc).isoformat()}
    _action_log.append(action)
    logger.warning("Mock: isolated machine %s", machine_id)
    return jsonify({"id": f"action-{len(_action_log)}", "status": "Pending"})


# --- Mock Teams webhook ---

@app.post("/teams-webhook")
def teams_webhook():
    data = request.get_json()
    _teams_messages.append(data)
    logger.info("Mock Teams message received: %s", str(data)[:100])
    return jsonify({"status": "ok"})


# --- Mock MSAL / AAD endpoints ---

@app.get("/<tenant_id>/.well-known/openid-configuration")
def openid_config(tenant_id):
    base = request.host_url.rstrip("/")
    return jsonify({
        "token_endpoint": f"{base}/{tenant_id}/oauth2/v2.0/token",
        "issuer": f"{base}/{tenant_id}/v2.0",
        "authorization_endpoint": f"{base}/{tenant_id}/oauth2/v2.0/authorize",
        "jwks_uri": f"{base}/{tenant_id}/discovery/v2.0/keys",
        "response_types_supported": ["code", "token"],
        "subject_types_supported": ["pairwise"],
        "id_token_signing_alg_values_supported": ["RS256"],
    })

@app.get("/<tenant_id>/discovery/v2.0/keys")
def jwks(tenant_id):
    return jsonify({"keys": []})

@app.post("/<tenant_id>/oauth2/v2.0/token")
def mock_token(tenant_id):
    return jsonify({
        "access_token": "mock-access-token-for-local-testing",
        "token_type": "Bearer",
        "expires_in": 3600,
    })


# --- Audit / inspection endpoints for tests ---

@app.get("/audit/actions")
def get_action_log():
    return jsonify(_action_log)


@app.get("/audit/teams-messages")
def get_teams_messages():
    return jsonify(_teams_messages)


@app.delete("/audit/reset")
def reset_state():
    _incidents.clear()
    _indicators.clear()
    _teams_messages.clear()
    _action_log.clear()
    return jsonify({"status": "reset"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
