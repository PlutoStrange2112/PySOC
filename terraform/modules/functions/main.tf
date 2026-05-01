terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }
}

resource "azurerm_storage_account" "functions" {
  name                     = "st${var.environment}soc${var.suffix}"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = var.storage_replication
  min_tls_version          = "TLS1_2"

  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }

  tags = var.tags
}

resource "azurerm_application_insights" "soc" {
  name                = "appi-${var.environment}-soc-${var.suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = var.log_analytics_workspace_id
  application_type    = "web"

  tags = var.tags
}

resource "azurerm_service_plan" "functions" {
  name                = "asp-${var.environment}-soc-${var.suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"
  sku_name            = "Y1"

  tags = var.tags
}

resource "azurerm_linux_function_app" "soc" {
  name                       = "func-${var.environment}-soc-${var.suffix}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.functions.id
  storage_account_name       = azurerm_storage_account.functions.name
  storage_account_access_key = azurerm_storage_account.functions.primary_access_key
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }
    application_insights_connection_string = azurerm_application_insights.soc.connection_string
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME       = "python"
    APPINSIGHTS_INSTRUMENTATIONKEY = azurerm_application_insights.soc.instrumentation_key
    SENTINEL_WORKSPACE_ID          = var.sentinel_workspace_customer_id
    SENTINEL_WORKSPACE_KEY         = "@Microsoft.KeyVault(SecretUri=${var.kv_secret_uri_workspace_key})"
    VIRUSTOTAL_API_KEY             = "@Microsoft.KeyVault(SecretUri=${var.kv_secret_uri_vt_key})"
    ABUSEIPDB_API_KEY              = "@Microsoft.KeyVault(SecretUri=${var.kv_secret_uri_abuseipdb_key})"
    TEAMS_WEBHOOK_URL              = "@Microsoft.KeyVault(SecretUri=${var.kv_secret_uri_teams_webhook})"
    ENVIRONMENT                    = var.environment
  }

  tags = var.tags
}

# Diagnostic settings → Log Analytics
resource "azurerm_monitor_diagnostic_setting" "functions" {
  name                       = "diag-func-to-law"
  target_resource_id         = azurerm_linux_function_app.soc.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "FunctionAppLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
