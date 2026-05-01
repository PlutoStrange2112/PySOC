output "action_group_id" {
  value = azurerm_monitor_action_group.soc_team.id
}

output "workbook_id" {
  value = azurerm_application_insights_workbook.soc_overview.id
}
