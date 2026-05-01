import json
from unittest.mock import patch, MagicMock

import azure.functions as func

from functions.incidents import main


MOCK_INCIDENTS = {
    "value": [
        {
            "id": "inc-0001", "name": "inc-0001",
            "properties": {
                "title": "Brute Force", "status": "New", "severity": "High",
                "incidentNumber": 1, "createdTimeUtc": "2026-05-01T00:00:00Z",
                "lastModifiedTimeUtc": "2026-05-01T00:00:00Z",
                "owner": {"userPrincipalName": ""},
                "additionalData": {"alertsCount": 3},
                "labels": [],
            },
        },
        {
            "id": "inc-0002", "name": "inc-0002",
            "properties": {
                "title": "Impossible Travel", "status": "Active", "severity": "Medium",
                "incidentNumber": 2, "createdTimeUtc": "2026-05-01T01:00:00Z",
                "lastModifiedTimeUtc": "2026-05-01T01:00:00Z",
                "owner": {"userPrincipalName": "analyst@corp.com"},
                "additionalData": {"alertsCount": 1},
                "labels": [{"labelName": "investigation"}],
            },
        },
    ]
}


def _make_req(params: dict = None):
    return func.HttpRequest(
        method="GET",
        url="/api/incidents",
        body=b"",
        params=params or {},
    )


@patch("functions.incidents.requests.get")
def test_returns_all_incidents(mock_get, monkeypatch):
    monkeypatch.setenv("MOCK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-1")
    monkeypatch.setenv("SENTINEL_RESOURCE_GROUP", "rg-1")
    monkeypatch.setenv("SENTINEL_WORKSPACE_NAME", "ws-1")

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = MOCK_INCIDENTS
    mock_get.return_value = mock_resp

    response = main(_make_req())
    assert response.status_code == 200
    data = json.loads(response.get_body())
    assert data["count"] == 2
    assert data["incidents"][0]["title"] == "Brute Force"


@patch("functions.incidents.requests.get")
def test_filter_by_status(mock_get, monkeypatch):
    monkeypatch.setenv("MOCK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-1")
    monkeypatch.setenv("SENTINEL_RESOURCE_GROUP", "rg-1")
    monkeypatch.setenv("SENTINEL_WORKSPACE_NAME", "ws-1")

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = MOCK_INCIDENTS
    mock_get.return_value = mock_resp

    response = main(_make_req({"status": "new"}))
    data = json.loads(response.get_body())
    assert data["count"] == 1
    assert data["incidents"][0]["status"] == "New"


@patch("functions.incidents.requests.get")
def test_filter_by_severity(mock_get, monkeypatch):
    monkeypatch.setenv("MOCK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-1")
    monkeypatch.setenv("SENTINEL_RESOURCE_GROUP", "rg-1")
    monkeypatch.setenv("SENTINEL_WORKSPACE_NAME", "ws-1")

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = MOCK_INCIDENTS
    mock_get.return_value = mock_resp

    response = main(_make_req({"severity": "medium"}))
    data = json.loads(response.get_body())
    assert data["count"] == 1
    assert data["incidents"][0]["severity"] == "Medium"


def test_invalid_status_returns_400():
    response = main(_make_req({"status": "unknown"}))
    assert response.status_code == 400


def test_invalid_severity_returns_400():
    response = main(_make_req({"severity": "critical"}))
    assert response.status_code == 400


def test_invalid_limit_returns_400():
    response = main(_make_req({"limit": "notanumber"}))
    assert response.status_code == 400


@patch("functions.incidents.requests.get")
def test_limit_param_respected(mock_get, monkeypatch):
    monkeypatch.setenv("MOCK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-1")
    monkeypatch.setenv("SENTINEL_RESOURCE_GROUP", "rg-1")
    monkeypatch.setenv("SENTINEL_WORKSPACE_NAME", "ws-1")

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = MOCK_INCIDENTS
    mock_get.return_value = mock_resp

    response = main(_make_req({"limit": "1"}))
    # limit is passed as $top to the API, not sliced client-side
    assert response.status_code == 200
    url_called = mock_get.call_args[0][0]
    assert "$top=1" in url_called


@patch("functions.incidents.requests.get")
def test_upstream_error_returns_500(mock_get, monkeypatch):
    monkeypatch.setenv("MOCK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-1")
    monkeypatch.setenv("SENTINEL_RESOURCE_GROUP", "rg-1")
    monkeypatch.setenv("SENTINEL_WORKSPACE_NAME", "ws-1")

    mock_get.side_effect = Exception("Connection refused")
    response = main(_make_req())
    assert response.status_code == 500
