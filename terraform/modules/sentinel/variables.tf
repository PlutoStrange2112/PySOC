variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, prod)"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group to deploy into"
}

variable "suffix" {
  type        = string
  description = "Short random suffix for globally unique names"
}

variable "retention_days" {
  type        = number
  description = "Log Analytics retention in days"
  default     = 90
}

variable "defender_tier" {
  type        = string
  description = "Defender for Cloud pricing tier (Free or Standard)"
  default     = "Standard"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}
