import json
from unittest.mock import patch, MagicMock

import pytest
import azure.functions as func

from functions.alert_enrichment import enrich_ip, enrich_domain, main


MOCK_VT_IP_RESPONSE = {
    "data": {
        "attributes": {
            "last_analysis_stats": {
                "malicious": 5,
                "suspicious": 2,
                "harmless": 60,
                "undetected": 10,
            }
        }
    }
}

MOCK_ABUSEIPDB_RESPONSE = {
    "data": {
        "abuseConfidenceScore": 87,
        "countryCode": "RU",
        "totalReports": 42,
    }
}


@patch("functions.alert_enrichment.requests.get")
def test_enrich_ip_success(mock_get):
    vt_resp = MagicMock(status_code=200)
    vt_resp.json.return_value = MOCK_VT_IP_RESPONSE
    abuse_resp = MagicMock(status_code=200)
    abuse_resp.json.return_value = MOCK_ABUSEIPDB_RESPONSE

    mock_get.side_effect = [vt_resp, abuse_resp]

    result = enrich_ip("1.2.3.4", "vt-key", "abuse-key")

    assert result.entity == "1.2.3.4"
    assert result.vt_malicious == 5
    assert result.vt_suspicious == 2
    assert result.abuseipdb_score == 87
    assert result.abuseipdb_country == "RU"
    assert result.enriched is True


@patch("functions.alert_enrichment.requests.get")
def test_enrich_ip_vt_failure_still_returns_abuseipdb(mock_get):
    vt_resp = MagicMock(status_code=429)
    vt_resp.json.return_value = {}
    abuse_resp = MagicMock(status_code=200)
    abuse_resp.json.return_value = MOCK_ABUSEIPDB_RESPONSE

    mock_get.side_effect = [vt_resp, abuse_resp]

    result = enrich_ip("1.2.3.4", "vt-key", "abuse-key")

    assert result.vt_malicious == 0
    assert result.abuseipdb_score == 87
    assert result.enriched is True


@patch("functions.alert_enrichment.requests.get")
def test_enrich_domain_success(mock_get):
    vt_resp = MagicMock(status_code=200)
    vt_resp.json.return_value = MOCK_VT_IP_RESPONSE

    mock_get.return_value = vt_resp

    result = enrich_domain("malicious.example.com", "vt-key")

    assert result.entity == "malicious.example.com"
    assert result.entity_type == "domain"
    assert result.vt_malicious == 5
    assert result.enriched is True


def test_main_empty_entities():
    req = func.HttpRequest(
        method="POST",
        url="/api/enrich-alert",
        body=json.dumps({"entities": []}).encode(),
        headers={"Content-Type": "application/json"},
    )
    response = main(req)
    assert response.status_code == 400


def test_main_invalid_json():
    req = func.HttpRequest(
        method="POST",
        url="/api/enrich-alert",
        body=b"not-json",
        headers={},
    )
    response = main(req)
    assert response.status_code == 400


@patch("functions.alert_enrichment.requests.get")
def test_main_enriches_ip_entity(mock_get):
    vt_resp = MagicMock(status_code=200)
    vt_resp.json.return_value = MOCK_VT_IP_RESPONSE
    abuse_resp = MagicMock(status_code=200)
    abuse_resp.json.return_value = MOCK_ABUSEIPDB_RESPONSE
    mock_get.side_effect = [vt_resp, abuse_resp]

    req = func.HttpRequest(
        method="POST",
        url="/api/enrich-alert",
        body=json.dumps({"entities": [{"type": "ip", "value": "1.2.3.4"}]}).encode(),
        headers={"Content-Type": "application/json"},
        params={"VIRUSTOTAL_API_KEY": "k", "ABUSEIPDB_API_KEY": "k"},
    )

    import os
    os.environ["VIRUSTOTAL_API_KEY"] = "test"
    os.environ["ABUSEIPDB_API_KEY"] = "test"

    response = main(req)
    assert response.status_code == 200
    data = json.loads(response.get_body())
    assert len(data["enrichments"]) == 1
    assert data["enrichments"][0]["entity"] == "1.2.3.4"
