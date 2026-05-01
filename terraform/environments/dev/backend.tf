terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "sttfstatesoc"
    container_name       = "tfstate-dev"
    key                  = "soc.dev.tfstate"
  }
}
