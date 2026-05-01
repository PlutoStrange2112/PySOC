variable "environment" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "suffix" { type = string }

variable "public_network_access" {
  type    = bool
  default = true
}

variable "allowed_ip_ranges" {
  type    = list(string)
  default = []
}

variable "ci_principal_id" {
  type        = string
  description = "Service principal ID used by CI/CD to write secrets"
}

variable "function_app_principal_id" {
  type        = string
  description = "Managed identity principal ID of the Function App"
}

variable "sentinel_workspace_primary_key" {
  type      = string
  sensitive = true
}

variable "virustotal_api_key" {
  type      = string
  sensitive = true
  default   = "placeholder"
}

variable "abuseipdb_api_key" {
  type      = string
  sensitive = true
  default   = "placeholder"
}

variable "teams_webhook_url" {
  type      = string
  sensitive = true
  default   = "placeholder"
}

variable "tags" {
  type    = map(string)
  default = {}
}
