from unittest.mock import patch, MagicMock

import pytest

from functions.threat_intel_sync import fetch_abuse_ch_iocs, push_indicator_to_sentinel


MOCK_FEODO_RESPONSE = {
    "blocklist": [
        {"ip_address": "10.0.0.1", "country": "US", "malware": "Emotet"},
        {"ip_address": "10.0.0.2", "country": "RU", "malware": "TrickBot"},
        {"ip_address": None},  # Should be skipped
    ]
}


@patch("functions.threat_intel_sync.requests.get")
def test_fetch_abuse_ch_iocs(mock_get):
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = MOCK_FEODO_RESPONSE
    mock_get.return_value = mock_resp

    iocs = fetch_abuse_ch_iocs()

    assert len(iocs) == 2  # None IP skipped
    assert iocs[0]["value"] == "10.0.0.1"
    assert iocs[0]["type"] == "ipv4-addr"
    assert "malicious-activity" in iocs[0]["labels"]


@patch("functions.threat_intel_sync.requests.get")
def test_fetch_abuse_ch_empty_response(mock_get):
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"blocklist": []}
    mock_get.return_value = mock_resp

    iocs = fetch_abuse_ch_iocs()
    assert iocs == []


@patch("functions.threat_intel_sync.requests.post")
def test_push_indicator_success(mock_post, monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-1")
    monkeypatch.setenv("SENTINEL_RESOURCE_GROUP", "rg-1")
    monkeypatch.setenv("SENTINEL_WORKSPACE_NAME", "ws-1")

    mock_resp = MagicMock(status_code=201)
    mock_resp.json.return_value = {"id": "ti-1"}
    mock_post.return_value = mock_resp

    ioc = {"type": "ipv4-addr", "value": "10.0.0.1", "confidence": 85, "source": "Test", "labels": []}
    result = push_indicator_to_sentinel(ioc, "mock-token")

    assert result is True


@patch("functions.threat_intel_sync.requests.post")
def test_push_indicator_failure_returns_false(mock_post, monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-1")
    monkeypatch.setenv("SENTINEL_RESOURCE_GROUP", "rg-1")
    monkeypatch.setenv("SENTINEL_WORKSPACE_NAME", "ws-1")

    mock_post.side_effect = Exception("Connection error")

    ioc = {"type": "ipv4-addr", "value": "10.0.0.1", "confidence": 85, "source": "Test", "labels": []}
    result = push_indicator_to_sentinel(ioc, "mock-token")

    assert result is False
