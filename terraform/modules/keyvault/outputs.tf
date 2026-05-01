output "key_vault_id" {
  value = azurerm_key_vault.soc.id
}

output "key_vault_uri" {
  value = azurerm_key_vault.soc.vault_uri
}

output "secret_uri_workspace_key" {
  value = azurerm_key_vault_secret.workspace_key.versionless_id
}

output "secret_uri_vt_key" {
  value = azurerm_key_vault_secret.virustotal_key.versionless_id
}

output "secret_uri_abuseipdb_key" {
  value = azurerm_key_vault_secret.abuseipdb_key.versionless_id
}

output "secret_uri_teams_webhook" {
  value = azurerm_key_vault_secret.teams_webhook.versionless_id
}
