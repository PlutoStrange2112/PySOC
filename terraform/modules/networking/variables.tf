variable "environment" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "suffix" { type = string }

variable "vnet_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "subnet_functions_cidr" {
  type    = string
  default = "10.0.1.0/24"
}

variable "subnet_pe_cidr" {
  type    = string
  default = "10.0.2.0/24"
}

variable "tags" {
  type    = map(string)
  default = {}
}
