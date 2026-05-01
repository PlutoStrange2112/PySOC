# PySOC

A production-grade Security Operations Center deployed on Azure, managed with Terraform and automated with Python Azure Functions. Fully testable locally via Docker Compose — no Azure subscription required for development.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
  - [Start the Stack](#start-the-stack)
  - [Using the Functions](#using-the-functions)
  - [Inspecting Mock State](#inspecting-mock-state)
  - [Running Tests](#running-tests)
- [Functions Reference](#functions-reference)
  - [GET /api/incidents](#get-apiincidents)
  - [POST /api/enrich-alert](#post-apienrich-alert)
  - [POST /api/respond-incident](#post-apirespond-incident)
  - [threat_intel_sync](#threat_intel_sync)
  - [soc_reporter](#soc_reporter)
- [Azure Deployment](#azure-deployment)
  - [Bootstrap State Storage](#bootstrap-state-storage)
  - [Deploy an Environment](#deploy-an-environment)
  - [Required Variables](#required-variables)
- [SOC Capabilities](#soc-capabilities)
  - [SIEM / Log Analytics](#siem--log-analytics)
  - [Threat Detection](#threat-detection)
  - [Incident Response Functions](#incident-response-functions)
  - [Dashboards and Alerting](#dashboards-and-alerting)
- [Functions Reference](#functions-reference)
  - [alert_enrichment](#alert_enrichment)
  - [incident_response](#incident_response)
  - [threat_intel_sync](#threat_intel_sync)
  - [soc_reporter](#soc_reporter)
- [Terraform Modules](#terraform-modules)
- [Environments](#environments)
- [Security Notes](#security-notes)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Azure Subscription                    │
│                                                             │
│  ┌──────────────┐    ┌────────────────────────────────────┐ │
│  │  Defender    │    │  Log Analytics Workspace (SIEM)    │ │
│  │  for Cloud   │───▶│  + Microsoft Sentinel              │ │
│  └──────────────┘    │  + 4 KQL Analytic Rules            │ │
│                      └──────────────┬───────────────────── ┘ │
│                                     │ alerts/incidents        │
│  ┌──────────────────────────────────▼───────────────────────┐ │
│  │              Azure Function App (Python 3.11)            │ │
│  │                                                          │ │
│  │  alert_enrichment  ──▶  VirusTotal + AbuseIPDB           │ │
│  │  incident_response ──▶  Disable user / Isolate host      │ │
│  │  threat_intel_sync ──▶  Feodo Tracker → Sentinel TI      │ │
│  │  soc_reporter      ──▶  Weekly metrics → Teams           │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │  Key Vault  │  │   Storage   │  │  App Insights        │  │
│  │  (secrets)  │  │  (fn state) │  │  (telemetry)         │  │
│  └─────────────┘  └─────────────┘  └──────────────────────┘  │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  VNet + Private Endpoints + NSGs                         │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

**Local Docker stack mirrors the same flow:**

```
docker-compose
├── pysoc-functions       (Azure Functions runtime, port 7071)
├── pysoc-azurite         (Azure Storage emulator, ports 10000-10002)
└── pysoc-mock-sentinel   (Mock for Sentinel, Graph, Defender, MSAL, port 8080)
```

---

## Project Structure

```
PySOC/
├── terraform/
│   ├── modules/
│   │   ├── sentinel/       # Log Analytics Workspace + Microsoft Sentinel (ARM)
│   │   ├── functions/      # Function App + Storage Account + App Insights
│   │   ├── keyvault/       # Key Vault with RBAC and all app secrets
│   │   ├── networking/     # VNet, subnets, NSGs, private endpoints, DNS zones
│   │   └── monitoring/     # Azure Workbooks, metric alerts, action groups
│   ├── environments/
│   │   ├── dev/            # Free Defender, LRS storage, public endpoints
│   │   ├── staging/        # Standard Defender, ZRS storage, private Key Vault
│   │   └── prod/           # Standard Defender, GRS storage, all private endpoints
│   └── arm_templates/
│       └── sentinel_analytics_rules.json   # KQL detection rules
├── functions/
│   ├── alert_enrichment/   # HTTP POST  — enrich IPs/domains with threat intel
│   ├── incident_response/  # HTTP POST  — disable users, isolate machines
│   ├── threat_intel_sync/  # Timer/6h   — sync IOCs from Feodo Tracker to Sentinel
│   ├── soc_reporter/       # Timer/Mon  — weekly KQL metrics report to Teams
│   ├── host.json
│   └── requirements.txt
├── docker/
│   ├── Dockerfile                  # Functions runtime image
│   ├── Dockerfile.mock-sentinel    # Mock API server image
│   ├── docker-compose.yml          # Full local stack
│   ├── mock_sentinel_server.py     # Flask mock for Sentinel, Graph, Defender, MSAL
│   └── mock_env/
│       └── .env.local              # Local environment variables
├── tests/
│   ├── unit/                       # pytest — mocked Azure SDK, no Docker needed
│   └── integration/                # pytest — requires Docker stack running
├── requirements-dev.txt
└── pytest.ini
```

---

## Prerequisites

| Tool | Minimum Version | Purpose |
|---|---|---|
| Docker Desktop | 4.x | Local testing stack |
| Python | 3.11 | Running tests and functions locally |
| Terraform | 1.6+ | Infrastructure deployment |
| Azure CLI | 2.50+ | Azure authentication for Terraform |

---

## Local Development

### Start the Stack

```bash
cd docker
docker compose up -d
```

All three containers start in dependency order: Azurite and mock-sentinel become healthy first, then the Functions container starts.

Verify everything is running:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected output:
```
NAMES                 STATUS                   PORTS
pysoc-functions       Up N seconds             0.0.0.0:7071->80/tcp
pysoc-azurite         Up N seconds (healthy)   0.0.0.0:10000-10002->...
pysoc-mock-sentinel   Up N seconds (healthy)   0.0.0.0:8080->8080/tcp
```

Stop the stack:

```bash
docker compose down
```

---

### Using the Functions

#### `POST /api/enrich-alert`

Enriches IP addresses and domains against VirusTotal and AbuseIPDB.

```bash
curl -X POST http://localhost:7071/api/enrich-alert \
  -H "Content-Type: application/json" \
  -d '{
    "entities": [
      {"type": "ip",     "value": "1.2.3.4"},
      {"type": "domain", "value": "malicious.example.com"}
    ]
  }'
```

Response:
```json
{
  "enrichments": [
    {
      "entity": "1.2.3.4",
      "entity_type": "ip",
      "vt_malicious": 5,
      "vt_suspicious": 2,
      "vt_total_engines": 72,
      "abuseipdb_score": 87,
      "abuseipdb_country": "RU",
      "abuseipdb_total_reports": 42,
      "enriched": true,
      "error": ""
    }
  ]
}
```

> Locally, VirusTotal and AbuseIPDB calls use the test API keys from `.env.local` — they will return zero scores unless you supply real keys.

---

#### `POST /api/respond-incident`

Executes one or more response actions against a Sentinel incident. Locally, all actions are intercepted by the mock server.

**Supported actions:**

| `type` | Effect |
|---|---|
| `disable_user` | Sets `accountEnabled: false` on the AAD user |
| `revoke_sessions` | Calls `revokeSignInSessions` on the AAD user |
| `isolate_machine` | Sends a full isolation request to Defender for Endpoint |

```bash
curl -X POST http://localhost:7071/api/respond-incident \
  -H "Content-Type: application/json" \
  -d '{
    "incidentId": "inc-042",
    "actions": [
      {"type": "disable_user",    "target": "attacker@corp.com"},
      {"type": "revoke_sessions", "target": "attacker@corp.com"},
      {"type": "isolate_machine", "target": "machine-abc123"}
    ]
  }'
```

Response (`200` all succeeded, `207` partial failure):
```json
{
  "incidentId": "inc-042",
  "results": [
    {"action": "disable_user",    "target": "attacker@corp.com", "status": "success"},
    {"action": "revoke_sessions", "target": "attacker@corp.com", "status": "success"},
    {"action": "isolate_machine", "target": "machine-abc123",    "status": "success"}
  ],
  "errors": []
}
```

---

### Inspecting Mock State

The mock-sentinel server exposes audit endpoints so you can assert what the functions actually did:

```bash
# All response actions taken (disable user, revoke sessions, isolate machine)
curl http://localhost:8080/audit/actions

# Threat intelligence indicators pushed to Sentinel
curl http://localhost:8080/ti-indicators

# Teams webhook messages sent by soc_reporter
curl http://localhost:8080/audit/teams-messages

# Reset all state between test runs
curl -X DELETE http://localhost:8080/audit/reset
```

You can also create mock Sentinel incidents directly:

```bash
curl -X POST \
  "http://localhost:8080/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.OperationalInsights/workspaces/ws-1/providers/Microsoft.SecurityInsights/incidents" \
  -H "Content-Type: application/json" \
  -d '{
    "properties": {
      "title": "Brute Force Detected",
      "severity": "High",
      "status": "New"
    }
  }'
```

---

### Running Tests

Install dev dependencies:

```bash
pip install -r requirements-dev.txt
```

**Unit tests** — no Docker required, all Azure SDK calls are mocked:

```bash
pytest tests/unit/ -v
```

**Integration tests** — requires the Docker stack to be running:

```bash
docker compose -f docker/docker-compose.yml up -d
pytest tests/integration/ -v
```

**With coverage:**

```bash
pytest tests/unit/ --cov=functions --cov-report=term-missing
```

---

## Azure Deployment

### Bootstrap State Storage

Before the first deploy, create the Azure Blob Storage backend for Terraform state. Run this once per subscription:

```bash
az group create --name rg-tfstate --location eastus

az storage account create \
  --name sttfstatesoc \
  --resource-group rg-tfstate \
  --sku Standard_LRS \
  --allow-blob-public-access false

az storage container create --name tfstate-dev     --account-name sttfstatesoc
az storage container create --name tfstate-staging --account-name sttfstatesoc
az storage container create --name tfstate-prod    --account-name sttfstatesoc
```

---

### Deploy an Environment

```bash
# Authenticate
az login
az account set --subscription <your-subscription-id>

# Deploy dev
terraform -chdir=terraform/environments/dev init
terraform -chdir=terraform/environments/dev plan -var="ci_principal_id=$(az ad sp show --id <your-sp> --query id -o tsv)"
terraform -chdir=terraform/environments/dev apply
```

Replace `dev` with `staging` or `prod` for other environments.

---

### Required Variables

These must be supplied at apply time (never commit real values):

| Variable | Description |
|---|---|
| `ci_principal_id` | Object ID of the service principal used by CI/CD to write Key Vault secrets |
| `virustotal_api_key` | VirusTotal API key for `alert_enrichment` |
| `abuseipdb_api_key` | AbuseIPDB API key for `alert_enrichment` |
| `teams_webhook_url` | Incoming Webhook URL for the `soc_reporter` Teams channel |

Pass them via environment variables to avoid shell history leaks:

```bash
export TF_VAR_virustotal_api_key="your-key"
export TF_VAR_abuseipdb_api_key="your-key"
export TF_VAR_teams_webhook_url="https://..."
export TF_VAR_ci_principal_id="..."
terraform -chdir=terraform/environments/prod apply
```

---

## SOC Capabilities

### SIEM / Log Analytics

- **Log Analytics Workspace** ingests sign-in logs, audit logs, blob storage logs, and Defender alerts.
- **Microsoft Sentinel** is enabled on top of the workspace via an ARM template deployment.
- Retention: 90 days (dev), 180 days (staging), 365 days (prod).

### Threat Detection

Four scheduled KQL analytic rules deploy automatically via ARM template:

| Rule | Tactic | Trigger |
|---|---|---|
| Brute Force Attack | CredentialAccess (T1110) | >10 failed logins from one IP in 10 min |
| Impossible Travel | InitialAccess (T1078) | Same user signs in from two locations within 1 hour |
| New Global Admin | PrivilegeEscalation (T1078.004) | User added to Global Administrator role |
| Large Blob Download | Exfiltration (T1530) | >1 GB downloaded from Storage in 1 hour |

Defender for Cloud is enabled on VMs, Storage Accounts, and Key Vaults (Standard tier in staging/prod, Free in dev).

### Incident Response Functions

| Function | Trigger | What it does |
|---|---|---|
| `alert_enrichment` | HTTP POST from Sentinel Logic App | Enriches incident entities with VirusTotal + AbuseIPDB scores, posts results as incident comment |
| `incident_response` | HTTP POST from Sentinel Logic App | Disables AAD users, revokes sign-in sessions, isolates Defender-managed machines |
| `threat_intel_sync` | Timer — every 6 hours | Pulls IP blocklist from Feodo Tracker (abuse.ch), pushes indicators to Sentinel Threat Intelligence |
| `soc_reporter` | Timer — Monday 08:00 | Queries Log Analytics for weekly metrics (incident count, MTTD, top rules), posts report to Teams |

### Dashboards and Alerting

- **Azure Workbook** — SOC Overview with incident pie chart, status bar chart, and MTTD trend line, scoped to the Log Analytics workspace.
- **Metric alert** — fires when Function App execution units exceed threshold, routes to the SOC action group.
- **Action group** — email list configurable per environment via `soc_email_addresses` variable.

---

## Functions Reference

### `incidents`

**Trigger:** `GET /api/incidents`
**Auth:** Anonymous (local) / Function key (Azure)

Returns Sentinel incidents with optional filtering. Results are sorted by creation time descending.

**Query parameters:**

| Parameter | Values | Default |
|---|---|---|
| `status` | `new`, `active`, `closed` | all |
| `severity` | `high`, `medium`, `low`, `informational` | all |
| `limit` | integer 1–200 | `50` |

```bash
# All incidents
curl http://localhost:7071/api/incidents

# Only new high-severity incidents
curl "http://localhost:7071/api/incidents?status=new&severity=high"

# Most recent 10
curl "http://localhost:7071/api/incidents?limit=10"
```

Response:
```json
{
  "count": 2,
  "incidents": [
    {
      "id": "inc-0001",
      "title": "Brute Force Attack Detected",
      "status": "New",
      "severity": "High",
      "incidentNumber": 1,
      "createdAt": "2026-05-01T00:00:00Z",
      "updatedAt": "2026-05-01T00:00:00Z",
      "assignedTo": "",
      "alertCount": 3,
      "labels": []
    }
  ]
}
```

---

### `alert_enrichment`

**Trigger:** HTTP POST `/api/enrich-alert`  
**Auth:** Anonymous (local) / Function key (Azure)

Accepts a list of entities and queries external threat intel APIs in parallel.

```
POST /api/enrich-alert
{
  "entities": [
    { "type": "ip",     "value": "<ip-address>" },
    { "type": "domain", "value": "<domain-name>" }
  ]
}
```

Returns zero-score results locally (test API keys); real scores in Azure with live keys in Key Vault.

---

### `incident_response`

**Trigger:** HTTP POST `/api/respond-incident`  
**Auth:** Anonymous (local) / Function key (Azure)

Executes response actions using a system-assigned managed identity (Azure) or `MOCK_ACCESS_TOKEN` (local).

```
POST /api/respond-incident
{
  "incidentId": "<sentinel-incident-id>",
  "actions": [
    { "type": "disable_user",    "target": "<upn>" },
    { "type": "revoke_sessions", "target": "<upn>" },
    { "type": "isolate_machine", "target": "<defender-machine-id>" }
  ]
}
```

Returns `200` if all actions succeeded, `207 Multi-Status` if any failed.

---

### `threat_intel_sync`

**Trigger:** Timer — `0 */6 * * * *` (every 6 hours)  
**No HTTP endpoint.**

Fetches the Feodo Tracker IP blocklist (Emotet, TrickBot, etc.) and upserts each IP as a STIX indicator into Sentinel Threat Intelligence. Runs silently; output visible in App Insights and Log Analytics.

---

### `soc_reporter`

**Trigger:** Timer — `0 0 8 * * 1` (Mondays at 08:00)  
**No HTTP endpoint.**

Runs four KQL queries against the Log Analytics workspace and assembles a plain-text weekly report:

- Total incidents in the last 7 days
- Incidents by severity
- Mean Time to Detect (minutes)
- Top 5 firing analytic rules

Posts the report to the Teams webhook URL stored in Key Vault.

---

## Terraform Modules

| Module | Key Resources |
|---|---|
| `sentinel` | `azurerm_log_analytics_workspace`, `azurerm_log_analytics_solution` (Sentinel), ARM template deployment (analytic rules), Defender pricing tiers |
| `functions` | `azurerm_linux_function_app` (Python 3.11, Consumption Y1), `azurerm_storage_account`, `azurerm_application_insights`, diagnostic settings |
| `keyvault` | `azurerm_key_vault` (RBAC mode), `azurerm_role_assignment` (Secrets Officer for CI, Secrets User for Function App), all app secrets |
| `networking` | `azurerm_virtual_network`, subnets (functions delegation, private endpoints), NSG (deny-all + HTTPS allow), private DNS zones |
| `monitoring` | `azurerm_application_insights_workbook`, `azurerm_monitor_metric_alert`, `azurerm_monitor_action_group` |

---

## Environments

| | `dev` | `staging` | `prod` |
|---|---|---|---|
| Defender tier | Free | Standard | Standard |
| Log retention | 90 days | 180 days | 365 days |
| Storage replication | LRS | ZRS | GRS |
| Key Vault network | Public | Private | Private |
| Function endpoints | Public | Public | Public |
| Terraform state container | `tfstate-dev` | `tfstate-staging` | `tfstate-prod` |

---

## Security Notes

- **No secrets in code.** All API keys and connection strings are stored in Key Vault and referenced via `@Microsoft.KeyVault(SecretUri=...)` in Function App settings.
- **Managed identity.** The Function App uses a system-assigned managed identity to read Key Vault secrets — no credential rotation needed.
- **Purge protection.** Key Vault purge protection is enabled in prod; soft-delete only in dev/staging.
- **Private endpoints.** In staging and prod, Key Vault and Storage are only reachable within the VNet.
- **`MOCK_ACCESS_TOKEN` is local only.** It is set in `docker/mock_env/.env.local` which is `.gitignore`d and never reaches Azure.
- **`authLevel: anonymous`** on the HTTP functions applies to the local Docker image only. In Azure, the Functions platform enforces function-level key auth at the host level regardless of `function.json`.
