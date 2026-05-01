import json
import logging
import os
from dataclasses import dataclass, asdict

import azure.functions as func
import requests

logger = logging.getLogger(__name__)

VIRUSTOTAL_URL = "https://www.virustotal.com/api/v3"
ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"


@dataclass
class EnrichmentResult:
    entity: str
    entity_type: str
    vt_malicious: int = 0
    vt_suspicious: int = 0
    vt_total_engines: int = 0
    abuseipdb_score: int = 0
    abuseipdb_country: str = ""
    abuseipdb_total_reports: int = 0
    enriched: bool = False
    error: str = ""


def enrich_ip(ip: str, vt_key: str, abuseipdb_key: str) -> EnrichmentResult:
    result = EnrichmentResult(entity=ip, entity_type="ip")

    try:
        vt_resp = requests.get(
            f"{VIRUSTOTAL_URL}/ip_addresses/{ip}",
            headers={"x-apikey": vt_key},
            timeout=10,
        )
        if vt_resp.status_code == 200:
            stats = vt_resp.json()["data"]["attributes"]["last_analysis_stats"]
            result.vt_malicious = stats.get("malicious", 0)
            result.vt_suspicious = stats.get("suspicious", 0)
            result.vt_total_engines = sum(stats.values())
    except Exception as exc:
        logger.warning("VirusTotal lookup failed for %s: %s", ip, exc)

    try:
        abuse_resp = requests.get(
            ABUSEIPDB_URL,
            headers={"Key": abuseipdb_key, "Accept": "application/json"},
            params={"ipAddress": ip, "maxAgeInDays": "90"},
            timeout=10,
        )
        if abuse_resp.status_code == 200:
            data = abuse_resp.json()["data"]
            result.abuseipdb_score = data.get("abuseConfidenceScore", 0)
            result.abuseipdb_country = data.get("countryCode", "")
            result.abuseipdb_total_reports = data.get("totalReports", 0)
    except Exception as exc:
        logger.warning("AbuseIPDB lookup failed for %s: %s", ip, exc)

    result.enriched = True
    return result


def enrich_domain(domain: str, vt_key: str) -> EnrichmentResult:
    result = EnrichmentResult(entity=domain, entity_type="domain")
    try:
        vt_resp = requests.get(
            f"{VIRUSTOTAL_URL}/domains/{domain}",
            headers={"x-apikey": vt_key},
            timeout=10,
        )
        if vt_resp.status_code == 200:
            stats = vt_resp.json()["data"]["attributes"]["last_analysis_stats"]
            result.vt_malicious = stats.get("malicious", 0)
            result.vt_suspicious = stats.get("suspicious", 0)
            result.vt_total_engines = sum(stats.values())
            result.enriched = True
    except Exception as exc:
        result.error = str(exc)
        logger.warning("VirusTotal domain lookup failed for %s: %s", domain, exc)

    return result


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    vt_key = os.environ.get("VIRUSTOTAL_API_KEY", "")
    abuseipdb_key = os.environ.get("ABUSEIPDB_API_KEY", "")

    entities = body.get("entities", [])
    if not entities:
        return func.HttpResponse("No entities provided", status_code=400)

    results = []
    for entity in entities:
        entity_type = entity.get("type", "").lower()
        value = entity.get("value", "")

        if not value:
            continue

        if entity_type == "ip":
            results.append(asdict(enrich_ip(value, vt_key, abuseipdb_key)))
        elif entity_type == "domain":
            results.append(asdict(enrich_domain(value, vt_key)))
        else:
            logger.info("Unsupported entity type: %s", entity_type)

    logger.info("Enriched %d entities", len(results))
    return func.HttpResponse(
        json.dumps({"enrichments": results}),
        mimetype="application/json",
        status_code=200,
    )
