variable "environment" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "suffix" { type = string }

variable "log_analytics_workspace_id" {
  type = string
}

variable "function_app_id" {
  type = string
}

variable "soc_email_addresses" {
  type        = list(string)
  description = "Email addresses for SOC team alert notifications"
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
