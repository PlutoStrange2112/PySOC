terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }
}

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "soc" {
  name                       = "kv-${var.environment}-soc-${var.suffix}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  purge_protection_enabled   = var.environment == "prod" ? true : false
  soft_delete_retention_days = 7

  network_acls {
    bypass         = "AzureServices"
    default_action = var.public_network_access ? "Allow" : "Deny"
    ip_rules       = var.allowed_ip_ranges
  }

  tags = var.tags
}

# Grant the CI/CD service principal Secrets Officer role
resource "azurerm_role_assignment" "ci_secrets_officer" {
  scope                = azurerm_key_vault.soc.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.ci_principal_id
}

# Grant the Function App managed identity Secrets User role
resource "azurerm_role_assignment" "func_secrets_user" {
  scope                = azurerm_key_vault.soc.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.function_app_principal_id
}

# Secrets
resource "azurerm_key_vault_secret" "workspace_key" {
  name         = "sentinel-workspace-key"
  value        = var.sentinel_workspace_primary_key
  key_vault_id = azurerm_key_vault.soc.id

  depends_on = [azurerm_role_assignment.ci_secrets_officer]
}

resource "azurerm_key_vault_secret" "virustotal_key" {
  name         = "virustotal-api-key"
  value        = var.virustotal_api_key
  key_vault_id = azurerm_key_vault.soc.id

  depends_on = [azurerm_role_assignment.ci_secrets_officer]
}

resource "azurerm_key_vault_secret" "abuseipdb_key" {
  name         = "abuseipdb-api-key"
  value        = var.abuseipdb_api_key
  key_vault_id = azurerm_key_vault.soc.id

  depends_on = [azurerm_role_assignment.ci_secrets_officer]
}

resource "azurerm_key_vault_secret" "teams_webhook" {
  name         = "teams-webhook-url"
  value        = var.teams_webhook_url
  key_vault_id = azurerm_key_vault.soc.id

  depends_on = [azurerm_role_assignment.ci_secrets_officer]
}
