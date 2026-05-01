terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }
}

resource "azurerm_log_analytics_workspace" "soc" {
  name                = "law-${var.environment}-soc-${var.suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_days

  tags = var.tags
}

resource "azurerm_log_analytics_solution" "sentinel" {
  solution_name         = "SecurityInsights"
  location              = var.location
  resource_group_name   = var.resource_group_name
  workspace_resource_id = azurerm_log_analytics_workspace.soc.id
  workspace_name        = azurerm_log_analytics_workspace.soc.name

  plan {
    publisher = "Microsoft"
    product   = "OMSGallery/SecurityInsights"
  }

  tags = var.tags
}

# Defender for Cloud auto-provisioning and pricing
resource "azurerm_security_center_subscription_pricing" "defender_servers" {
  tier          = var.defender_tier
  resource_type = "VirtualMachines"
}

resource "azurerm_security_center_subscription_pricing" "defender_storage" {
  tier          = var.defender_tier
  resource_type = "StorageAccounts"
}

resource "azurerm_security_center_subscription_pricing" "defender_keyvault" {
  tier          = var.defender_tier
  resource_type = "KeyVaults"
}

resource "azurerm_security_center_auto_provisioning" "mma" {
  auto_provision = "On"
}

# Sentinel analytic rules via ARM template
resource "azurerm_resource_group_template_deployment" "sentinel_rules" {
  name                = "sentinel-analytics-rules"
  resource_group_name = var.resource_group_name
  deployment_mode     = "Incremental"

  template_content = file("${path.module}/../../../arm_templates/sentinel_analytics_rules.json")

  parameters_content = jsonencode({
    workspaceName = { value = azurerm_log_analytics_workspace.soc.name }
    location      = { value = var.location }
  })

  depends_on = [azurerm_log_analytics_solution.sentinel]
}
