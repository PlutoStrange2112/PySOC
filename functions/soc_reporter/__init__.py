import json
import logging
import os
from datetime import datetime, timedelta, timezone

import azure.functions as func
import requests
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


QUERIES = {
    "total_incidents": "SecurityIncident | where TimeGenerated > ago(7d) | count",
    "incidents_by_severity": (
        "SecurityIncident | where TimeGenerated > ago(7d) "
        "| summarize count() by Severity"
    ),
    "top_analytic_rules": (
        "SecurityAlert | where TimeGenerated > ago(7d) "
        "| summarize count() by AlertName | top 5 by count_"
    ),
    "mean_time_to_detect": (
        "SecurityIncident | where TimeGenerated > ago(7d) "
        "| extend MTTD = datetime_diff('minute', FirstActivityTime, TimeGenerated) "
        "| summarize avg(MTTD)"
    ),
}


def run_queries(workspace_id: str) -> dict:
    credential = DefaultAzureCredential()
    client = LogsQueryClient(credential)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)

    results = {}
    for name, query in QUERIES.items():
        try:
            response = client.query_workspace(
                workspace_id=workspace_id,
                query=query,
                timespan=(start_time, end_time),
            )
            if response.status == LogsQueryStatus.SUCCESS:
                table = response.tables[0]
                results[name] = [
                    dict(zip(table.columns, row)) for row in table.rows
                ]
            else:
                logger.warning("Query %s returned partial results", name)
                results[name] = []
        except Exception as exc:
            logger.error("Query %s failed: %s", name, exc)
            results[name] = []

    return results


def build_report(metrics: dict) -> str:
    week_end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    total = metrics.get("total_incidents", [{}])
    total_count = total[0].get("Count", "N/A") if total else "N/A"

    mttd = metrics.get("mean_time_to_detect", [{}])
    avg_mttd = round(mttd[0].get("avg_MTTD", 0), 1) if mttd else "N/A"

    by_severity = metrics.get("incidents_by_severity", [])
    severity_lines = "\n".join(
        f"  - {row.get('Severity', 'Unknown')}: {row.get('count_', 0)}"
        for row in by_severity
    )

    top_rules = metrics.get("top_analytic_rules", [])
    rule_lines = "\n".join(
        f"  {i+1}. {row.get('AlertName', 'Unknown')} ({row.get('count_', 0)} alerts)"
        for i, row in enumerate(top_rules)
    )

    return f"""SOC Weekly Report: {week_start} to {week_end}
{'=' * 50}

INCIDENT SUMMARY
  Total Incidents (7d): {total_count}
  Mean Time to Detect:  {avg_mttd} minutes

INCIDENTS BY SEVERITY
{severity_lines or '  No data'}

TOP ANALYTIC RULES
{rule_lines or '  No data'}
"""


def send_teams_notification(report: str, webhook_url: str) -> None:
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": "SOC Weekly Report",
        "themeColor": "0076D7",
        "sections": [
            {
                "activityTitle": "SOC Weekly Report",
                "activityText": f"```\n{report}\n```",
            }
        ],
    }
    resp = requests.post(webhook_url, json=payload, timeout=15)
    resp.raise_for_status()
    logger.info("SOC report sent to Teams")


def main(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logger.warning("SOC reporter timer is past due")

    workspace_id = os.environ.get("SENTINEL_WORKSPACE_ID", "")
    teams_webhook = os.environ.get("TEAMS_WEBHOOK_URL", "")

    if not workspace_id:
        logger.error("SENTINEL_WORKSPACE_ID not configured")
        return

    logger.info("Generating SOC weekly report")
    metrics = run_queries(workspace_id)
    report = build_report(metrics)
    logger.info("Report:\n%s", report)

    if teams_webhook and teams_webhook != "placeholder":
        try:
            send_teams_notification(report, teams_webhook)
        except Exception as exc:
            logger.error("Failed to send Teams notification: %s", exc)
