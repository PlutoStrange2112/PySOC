variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "suffix" {
  type = string
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Full resource ID of the Log Analytics workspace"
}

variable "sentinel_workspace_customer_id" {
  type        = string
  description = "Log Analytics customer/workspace GUID"
}

variable "storage_replication" {
  type        = string
  description = "Storage account replication type (LRS, GRS, ZRS)"
  default     = "LRS"
}

variable "kv_secret_uri_workspace_key" {
  type        = string
  description = "Key Vault secret URI for the Log Analytics primary shared key"
}

variable "kv_secret_uri_vt_key" {
  type        = string
  description = "Key Vault secret URI for VirusTotal API key"
}

variable "kv_secret_uri_abuseipdb_key" {
  type        = string
  description = "Key Vault secret URI for AbuseIPDB API key"
}

variable "kv_secret_uri_teams_webhook" {
  type        = string
  description = "Key Vault secret URI for Teams webhook URL"
}

variable "tags" {
  type    = map(string)
  default = {}
}
