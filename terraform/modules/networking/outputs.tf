output "vnet_id" {
  value = azurerm_virtual_network.soc.id
}

output "subnet_functions_id" {
  value = azurerm_subnet.functions.id
}

output "subnet_private_endpoints_id" {
  value = azurerm_subnet.private_endpoints.id
}

output "private_dns_zone_storage_blob_id" {
  value = azurerm_private_dns_zone.storage_blob.id
}

output "private_dns_zone_keyvault_id" {
  value = azurerm_private_dns_zone.keyvault.id
}
