terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }
}

# SOC Overview workbook
resource "azurerm_application_insights_workbook" "soc_overview" {
  name                = "soc-overview-workbook-${var.suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  display_name        = "SOC Overview - ${upper(var.environment)}"
  source_id           = lower(var.log_analytics_workspace_id)

  data_json = jsonencode({
    version = "Notebook/1.0"
    items = [
      {
        type = 1
        content = {
          json = "## SOC Overview Dashboard\nKey metrics for the Security Operations Center."
        }
      },
      {
        type = 3
        content = {
          version = "KqlItem/1.0"
          query   = "SecurityAlert | summarize count() by AlertSeverity | render piechart"
          size    = 1
          title   = "Alerts by Severity (Last 24h)"
          timeContext = {
            durationMs = 86400000
          }
          queryType  = 0
          resourceType = "microsoft.operationalinsights/workspaces"
        }
      },
      {
        type = 3
        content = {
          version = "KqlItem/1.0"
          query   = "SecurityIncident | summarize count() by Status | render barchart"
          size    = 1
          title   = "Incidents by Status"
          timeContext = {
            durationMs = 604800000
          }
          queryType  = 0
          resourceType = "microsoft.operationalinsights/workspaces"
        }
      },
      {
        type = 3
        content = {
          version = "KqlItem/1.0"
          query   = "SecurityIncident | where TimeGenerated > ago(7d) | extend MTTD = datetime_diff('minute', FirstActivityTime, TimeGenerated) | summarize avg(MTTD) by bin(TimeGenerated, 1d) | render timechart"
          size    = 1
          title   = "Mean Time to Detect (minutes) - Last 7 Days"
          queryType  = 0
          resourceType = "microsoft.operationalinsights/workspaces"
        }
      }
    ]
    isLocked = false
  })

  tags = var.tags
}

# Alert rule: Function App errors spike
resource "azurerm_monitor_metric_alert" "func_errors" {
  name                = "alert-func-errors-${var.environment}"
  resource_group_name = var.resource_group_name
  scopes              = [var.function_app_id]
  description         = "Function App error rate exceeded threshold"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "FunctionExecutionUnits"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 1000000
  }

  tags = var.tags
}

# Action group for SOC team notifications
resource "azurerm_monitor_action_group" "soc_team" {
  name                = "ag-soc-${var.environment}"
  resource_group_name = var.resource_group_name
  short_name          = "soc-team"

  dynamic "email_receiver" {
    for_each = var.soc_email_addresses
    content {
      name          = "soc-analyst-${email_receiver.key}"
      email_address = email_receiver.value
    }
  }

  tags = var.tags
}
