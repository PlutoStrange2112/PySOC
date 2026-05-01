output "function_app_id" {
  value = azurerm_linux_function_app.soc.id
}

output "function_app_name" {
  value = azurerm_linux_function_app.soc.name
}

output "function_app_principal_id" {
  value       = azurerm_linux_function_app.soc.identity[0].principal_id
  description = "Managed identity principal ID for Key Vault access policy"
}

output "storage_account_name" {
  value = azurerm_storage_account.functions.name
}

output "app_insights_instrumentation_key" {
  value     = azurerm_application_insights.soc.instrumentation_key
  sensitive = true
}
