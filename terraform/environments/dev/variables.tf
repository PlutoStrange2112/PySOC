variable "environment" {
  type    = string
  default = "dev"
}

variable "location" {
  type    = string
  default = "eastus"
}

variable "retention_days" {
  type    = number
  default = 90
}

variable "defender_tier" {
  type    = string
  default = "Free"
}

variable "ci_principal_id" {
  type        = string
  description = "Service principal used by CI/CD pipeline"
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

variable "soc_email_addresses" {
  type    = list(string)
  default = []
}
