import json
import logging
import os

import azure.functions as func
import requests

logger = logging.getLogger(__name__)

SENTINEL_API = (
    "https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}"
    "/providers/Microsoft.OperationalInsights/workspaces/{ws}"
    "/providers/Microsoft.SecurityInsights/incidents"
    "?api-version=2023-02-01-preview"
)

VALID_STATUSES = {"new", "active", "closed"}
VALID_SEVERITIES = {"high", "medium", "low", "informational"}


def get_token() -> str:
    mock = os.environ.get("MOCK_ACCESS_TOKEN")
    if mock:
        return mock

    tenant_id = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["AZURE_CLIENT_ID"]
    client_secret = os.environ["AZURE_CLIENT_SECRET"]
    auth_endpoint = os.environ.get("AZURE_AUTH_ENDPOINT", "https://login.microsoftonline.com")

    resp = requests.post(
        f"{auth_endpoint}/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://management.azure.com/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_incidents(token: str, status: str | None, severity: str | None, limit: int) -> list[dict]:
    sub = os.environ["AZURE_SUBSCRIPTION_ID"]
    rg = os.environ["SENTINEL_RESOURCE_GROUP"]
    ws = os.environ["SENTINEL_WORKSPACE_NAME"]

    sentinel_endpoint = os.environ.get("SENTINEL_ENDPOINT", "https://management.azure.com")
    url = (
        f"{sentinel_endpoint}/subscriptions/{sub}/resourceGroups/{rg}"
        f"/providers/Microsoft.OperationalInsights/workspaces/{ws}"
        f"/providers/Microsoft.SecurityInsights/incidents"
        f"?api-version=2023-02-01-preview&$top={limit}&$orderby=properties/createdTimeUtc desc"
    )

    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()

    incidents = resp.json().get("value", [])

    if status:
        incidents = [
            i for i in incidents
            if i.get("properties", {}).get("status", "").lower() == status
        ]
    if severity:
        incidents = [
            i for i in incidents
            if i.get("properties", {}).get("severity", "").lower() == severity
        ]

    return incidents


def shape_incident(raw: dict) -> dict:
    props = raw.get("properties", {})
    return {
        "id": raw.get("name") or raw.get("id", ""),
        "title": props.get("title", ""),
        "status": props.get("status", ""),
        "severity": props.get("severity", ""),
        "incidentNumber": props.get("incidentNumber"),
        "createdAt": props.get("createdTimeUtc", ""),
        "updatedAt": props.get("lastModifiedTimeUtc", ""),
        "assignedTo": props.get("owner", {}).get("userPrincipalName", ""),
        "alertCount": props.get("additionalData", {}).get("alertsCount", 0),
        "labels": [l.get("labelName", "") for l in props.get("labels", [])],
    }


def main(req: func.HttpRequest) -> func.HttpResponse:
    status = req.params.get("status", "").lower() or None
    severity = req.params.get("severity", "").lower() or None
    try:
        limit = min(int(req.params.get("limit", "50")), 200)
    except ValueError:
        return func.HttpResponse("'limit' must be an integer", status_code=400)

    if status and status not in VALID_STATUSES:
        return func.HttpResponse(
            f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}",
            status_code=400,
        )
    if severity and severity not in VALID_SEVERITIES:
        return func.HttpResponse(
            f"Invalid severity '{severity}'. Must be one of: {', '.join(VALID_SEVERITIES)}",
            status_code=400,
        )

    try:
        token = get_token()
        raw_incidents = fetch_incidents(token, status, severity, limit)
    except Exception as exc:
        logger.error("Failed to fetch incidents: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Failed to fetch incidents", "detail": str(exc)}),
            mimetype="application/json",
            status_code=500,
        )

    incidents = [shape_incident(i) for i in raw_incidents]
    logger.info("Returning %d incidents (status=%s severity=%s)", len(incidents), status, severity)

    return func.HttpResponse(
        json.dumps({"count": len(incidents), "incidents": incidents}),
        mimetype="application/json",
        status_code=200,
    )
