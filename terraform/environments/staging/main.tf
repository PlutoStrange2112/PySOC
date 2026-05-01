terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_resource_group" "soc" {
  name     = "rg-${var.environment}-soc"
  location = var.location
  tags     = local.common_tags
}

module "networking" {
  source              = "../../modules/networking"
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.soc.name
  suffix              = random_string.suffix.result
  tags                = local.common_tags
}

module "sentinel" {
  source              = "../../modules/sentinel"
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.soc.name
  suffix              = random_string.suffix.result
  retention_days      = var.retention_days
  defender_tier       = var.defender_tier
  tags                = local.common_tags
}

module "keyvault" {
  source                         = "../../modules/keyvault"
  environment                    = var.environment
  location                       = var.location
  resource_group_name            = azurerm_resource_group.soc.name
  suffix                         = random_string.suffix.result
  public_network_access          = false
  allowed_ip_ranges              = var.allowed_ip_ranges
  ci_principal_id                = var.ci_principal_id
  function_app_principal_id      = module.functions.function_app_principal_id
  sentinel_workspace_primary_key = module.sentinel.primary_shared_key
  virustotal_api_key             = var.virustotal_api_key
  abuseipdb_api_key              = var.abuseipdb_api_key
  teams_webhook_url              = var.teams_webhook_url
  tags                           = local.common_tags

  depends_on = [module.functions]
}

module "functions" {
  source                         = "../../modules/functions"
  environment                    = var.environment
  location                       = var.location
  resource_group_name            = azurerm_resource_group.soc.name
  suffix                         = random_string.suffix.result
  log_analytics_workspace_id     = module.sentinel.workspace_id
  sentinel_workspace_customer_id = module.sentinel.workspace_customer_id
  storage_replication            = "ZRS"
  kv_secret_uri_workspace_key    = module.keyvault.secret_uri_workspace_key
  kv_secret_uri_vt_key           = module.keyvault.secret_uri_vt_key
  kv_secret_uri_abuseipdb_key    = module.keyvault.secret_uri_abuseipdb_key
  kv_secret_uri_teams_webhook    = module.keyvault.secret_uri_teams_webhook
  tags                           = local.common_tags

  depends_on = [module.keyvault]
}

module "monitoring" {
  source                     = "../../modules/monitoring"
  environment                = var.environment
  location                   = var.location
  resource_group_name        = azurerm_resource_group.soc.name
  suffix                     = random_string.suffix.result
  log_analytics_workspace_id = module.sentinel.workspace_id
  function_app_id            = module.functions.function_app_id
  soc_email_addresses        = var.soc_email_addresses
  tags                       = local.common_tags
}

locals {
  common_tags = {
    environment = var.environment
    project     = "pysoc"
    managed_by  = "terraform"
  }
}
