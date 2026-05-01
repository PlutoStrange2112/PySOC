"""
Integration tests against the running Docker Compose stack.
Run with: pytest tests/integration/ -v
Requires: docker-compose up -d (from docker/ directory)
"""
import json
import time

import pytest
import requests

FUNCTIONS_BASE = "http://localhost:7071/api"
MOCK_SENTINEL_BASE = "http://localhost:8080"


def wait_for_service(url: str, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    return False


@pytest.fixture(scope="session", autouse=True)
def wait_for_stack():
    assert wait_for_service(f"{MOCK_SENTINEL_BASE}/health"), \
        "mock-sentinel did not become healthy in time"


@pytest.fixture(autouse=True)
def reset_mock_state():
    requests.delete(f"{MOCK_SENTINEL_BASE}/audit/reset", timeout=5)
    yield


class TestAlertEnrichment:
    def test_enrich_ip_returns_200(self):
        payload = {"entities": [{"type": "ip", "value": "8.8.8.8"}]}
        resp = requests.post(
            f"{FUNCTIONS_BASE}/enrich-alert",
            json=payload,
            timeout=20,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "enrichments" in data
        assert len(data["enrichments"]) == 1

    def test_enrich_empty_entities_returns_400(self):
        resp = requests.post(
            f"{FUNCTIONS_BASE}/enrich-alert",
            json={"entities": []},
            timeout=10,
        )
        assert resp.status_code == 400

    def test_enrich_multiple_entities(self):
        payload = {
            "entities": [
                {"type": "ip", "value": "1.1.1.1"},
                {"type": "domain", "value": "example.com"},
            ]
        }
        resp = requests.post(
            f"{FUNCTIONS_BASE}/enrich-alert",
            json=payload,
            timeout=30,
        )
        assert resp.status_code == 200
        assert len(resp.json()["enrichments"]) == 2


class TestIncidentResponse:
    def test_disable_user_action(self):
        payload = {
            "incidentId": "inc-test-001",
            "actions": [{"type": "disable_user", "target": "attacker@example.com"}],
        }
        resp = requests.post(
            f"{FUNCTIONS_BASE}/respond-incident",
            json=payload,
            timeout=15,
        )
        assert resp.status_code in (200, 207)

        actions = requests.get(f"{MOCK_SENTINEL_BASE}/audit/actions", timeout=5).json()
        disable_actions = [a for a in actions if a.get("type") == "patch_user"]
        assert len(disable_actions) >= 1

    def test_empty_actions_returns_400(self):
        resp = requests.post(
            f"{FUNCTIONS_BASE}/respond-incident",
            json={"incidentId": "inc-test-002", "actions": []},
            timeout=10,
        )
        assert resp.status_code == 400


class TestMockSentinel:
    def test_create_and_get_incident(self):
        payload = {
            "properties": {
                "title": "Test Incident",
                "severity": "High",
                "status": "New",
            }
        }
        create_resp = requests.post(
            f"{MOCK_SENTINEL_BASE}/subscriptions/sub-1/resourceGroups/rg-1"
            "/providers/Microsoft.OperationalInsights/workspaces/ws-1"
            "/providers/Microsoft.SecurityInsights/incidents",
            json=payload,
            timeout=10,
        )
        assert create_resp.status_code == 201
        incident_id = create_resp.json()["id"]

        get_resp = requests.get(
            f"{MOCK_SENTINEL_BASE}/subscriptions/sub-1/resourceGroups/rg-1"
            f"/providers/Microsoft.OperationalInsights/workspaces/ws-1"
            f"/providers/Microsoft.SecurityInsights/incidents/{incident_id}",
            timeout=10,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == incident_id
