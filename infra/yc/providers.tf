terraform {
  required_version = ">= 1.6.0"

  required_providers {
    yandex = {
      source  = "yandex-cloud/yandex"
      version = ">= 0.196.0"
    }
  }
}

locals {
  project_name                  = "restobot"
  environment                   = "mvp"
  yc_region                     = "ru-central1"
  default_object_storage_bucket = "restobot-mvp-assets"
}

provider "yandex" {
  cloud_id  = var.yc_cloud_id
  folder_id = var.yc_folder_id
  token     = var.yc_token
  zone      = var.yc_zone
}

check "bootstrap_api_requires_token" {
  assert {
    condition     = !var.enable_bootstrap_api || var.bootstrap_api_token != null
    error_message = "bootstrap_api_token must be set when enable_bootstrap_api is true."
  }
}

check "database_pool_bounds" {
  assert {
    condition     = var.database_pool_max >= var.database_pool_min
    error_message = "database_pool_max must be greater than or equal to database_pool_min."
  }
}

check "pilot_existing_hosts_set" {
  assert {
    condition     = var.existing_db_host != null && var.existing_redis_host != null
    error_message = "existing_db_host and existing_redis_host must be set for the pilot attachment flow."
  }
}

check "pilot_secret_versions_set" {
  assert {
    condition = var.existing_common_secret_version_id != null && var.existing_db_secret_version_id != null && var.existing_redis_secret_version_id != null
    error_message = "existing_*_secret_version_id values must be set for the pilot attachment flow."
  }
}
