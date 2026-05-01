import logging
import os
from datetime import datetime, timezone

import azure.functions as func
import requests

logger = logging.getLogger(__name__)

ABUSE_CH_FEODO_URL = "https://feodotracker.abuse.ch/downloads/ipblocklist.json"
SENTINEL_TI_URL = (
    "https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}"
    "/providers/Microsoft.OperationalInsights/workspaces/{ws}"
    "/providers/Microsoft.SecurityInsights/threatIntelligence/main/createIndicator"
    "?api-version=2023-02-01-preview"
)


def get_management_token() -> str:
    tenant_id = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["AZURE_CLIENT_ID"]
    client_secret = os.environ["AZURE_CLIENT_SECRET"]

    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
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


def fetch_abuse_ch_iocs() -> list[dict]:
    resp = requests.get(ABUSE_CH_FEODO_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    iocs = []
    for entry in data.get("blocklist", []):
        ip = entry.get("ip_address")
        if ip:
            iocs.append({
                "type": "ipv4-addr",
                "value": ip,
                "confidence": 85,
                "source": "Feodo Tracker (abuse.ch)",
                "labels": ["malicious-activity", "botnet"],
            })
    logger.info("Fetched %d IOCs from Feodo Tracker", len(iocs))
    return iocs


def push_indicator_to_sentinel(ioc: dict, token: str) -> bool:
    sub = os.environ["AZURE_SUBSCRIPTION_ID"]
    rg = os.environ["SENTINEL_RESOURCE_GROUP"]
    ws = os.environ["SENTINEL_WORKSPACE_NAME"]

    url = SENTINEL_TI_URL.format(sub=sub, rg=rg, ws=ws)
    now = datetime.now(timezone.utc).isoformat()

    payload = {
        "kind": "indicator",
        "properties": {
            "source": ioc["source"],
            "displayName": f"SOC-TI: {ioc['value']}",
            "description": f"Automated import from {ioc['source']}",
            "pattern": f"[{ioc['type']}:value = '{ioc['value']}']",
            "patternType": "stix",
            "confidence": ioc["confidence"],
            "threatIntelligenceTags": ioc["labels"],
            "validFrom": now,
            "revoked": False,
        },
    }

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Failed to push IOC %s: %s", ioc["value"], exc)
        return False


def main(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logger.warning("Threat intel sync timer is past due")

    logger.info("Starting threat intel sync")

    try:
        token = get_management_token()
        iocs = fetch_abuse_ch_iocs()
    except Exception as exc:
        logger.error("Threat intel sync aborted: %s", exc)
        return

    pushed = sum(push_indicator_to_sentinel(ioc, token) for ioc in iocs)
    logger.info("Threat intel sync complete: %d/%d indicators pushed", pushed, len(iocs))
