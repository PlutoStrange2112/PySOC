import json
from unittest.mock import patch, MagicMock

import pytest
import azure.functions as func

from functions.incident_response import disable_user, revoke_user_sessions, isolate_machine, main


def test_disable_user_success():
    token = "mock-token"
    with patch("functions.incident_response.requests.patch") as mock_patch:
        mock_resp = MagicMock(status_code=204)
        mock_patch.return_value = mock_resp

        result = disable_user("user@example.com", token)

        assert result["status"] == "success"
        assert result["target"] == "user@example.com"
        mock_patch.assert_called_once()


def test_revoke_sessions_success():
    token = "mock-token"
    with patch("functions.incident_response.requests.post") as mock_post:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"value": True}
        mock_post.return_value = mock_resp

        result = revoke_user_sessions("user@example.com", token)

        assert result["status"] == "success"


def test_isolate_machine_success():
    token = "mock-token"
    with patch("functions.incident_response.requests.post") as mock_post:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"id": "action-1", "status": "Pending"}
        mock_post.return_value = mock_resp

        result = isolate_machine("machine-abc123", token)

        assert result["status"] == "success"
        assert result["target"] == "machine-abc123"


def test_main_no_actions():
    req = func.HttpRequest(
        method="POST",
        url="/api/respond-incident",
        body=json.dumps({"incidentId": "inc-001", "actions": []}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with patch("functions.incident_response.get_graph_token", return_value="tok"):
        response = main(req)
    assert response.status_code == 400


def test_main_invalid_json():
    req = func.HttpRequest(
        method="POST",
        url="/api/respond-incident",
        body=b"bad",
        headers={},
    )
    response = main(req)
    assert response.status_code == 400


def test_main_mixed_success_and_error():
    import os
    for k, v in [
        ("AZURE_TENANT_ID", "tid"), ("AZURE_CLIENT_ID", "cid"), ("AZURE_CLIENT_SECRET", "sec")
    ]:
        os.environ[k] = v

    with patch("functions.incident_response.get_graph_token", return_value="tok"), \
         patch("functions.incident_response.disable_user", return_value={"action": "disable_user", "target": "u@e.com", "status": "success"}), \
         patch("functions.incident_response.revoke_user_sessions", side_effect=Exception("API error")):

        req = func.HttpRequest(
            method="POST",
            url="/api/respond-incident",
            body=json.dumps({
                "incidentId": "inc-007",
                "actions": [
                    {"type": "disable_user", "target": "u@e.com"},
                    {"type": "revoke_sessions", "target": "u@e.com"},
                ]
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        response = main(req)

    # 207 Multi-Status when some actions succeed and some fail
    assert response.status_code == 207
    data = json.loads(response.get_body())
    assert len(data["results"]) == 1
    assert len(data["errors"]) == 1
