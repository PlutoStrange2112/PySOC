variable "environment" {
  type    = string
  default = "prod"
}

variable "location" {
  type    = string
  default = "eastus"
}

variable "retention_days" {
  type    = number
  default = 365
}

variable "allowed_ip_ranges" {
  type    = list(string)
  default = []
}

variable "ci_principal_id" {
  type = string
}

variable "virustotal_api_key" {
  type      = string
  sensitive = true
}

variable "abuseipdb_api_key" {
  type      = string
  sensitive = true
}

variable "teams_webhook_url" {
  type      = string
  sensitive = true
}

variable "soc_email_addresses" {
  type    = list(string)
  default = []
}
