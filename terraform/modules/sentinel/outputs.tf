output "workspace_id" {
  value       = azurerm_log_analytics_workspace.soc.id
  description = "Log Analytics Workspace resource ID"
}

output "workspace_name" {
  value       = azurerm_log_analytics_workspace.soc.name
  description = "Log Analytics Workspace name"
}

output "workspace_customer_id" {
  value       = azurerm_log_analytics_workspace.soc.workspace_id
  description = "Log Analytics customer/workspace GUID (used in queries)"
}

output "primary_shared_key" {
  value       = azurerm_log_analytics_workspace.soc.primary_shared_key
  sensitive   = true
  description = "Primary shared key for workspace (stored in Key Vault)"
}
