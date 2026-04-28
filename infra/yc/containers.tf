resource "yandex_serverless_container" "admin_api" {
  name               = "${local.project_name}-${local.environment}-admin-api"
  description        = "Admin HTTP API for RestoBot."
  memory             = 1024
  cores              = 1
  core_fraction      = 100
  concurrency        = 1
  execution_timeout  = "30s"
  service_account_id = yandex_iam_service_account.runtime.id

  runtime {
    type = "http"
  }

  connectivity {
    network_id = yandex_vpc_network.restobot.id
  }

  provision_policy {
    min_instances = 1
  }

  image {
    url      = var.admin_image
    command  = ["sh", "-c"]
    args     = ["uvicorn apps.admin_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
    work_dir = "/app"
    environment = {
      ENVIRONMENT              = "production"
      LOG_FORMAT               = "json"
      LOG_LEVEL                = "INFO"
      YC_CLOUD_ID              = var.yc_cloud_id
      YC_FOLDER_ID             = var.yc_folder_id
      YC_OBJECT_STORAGE_BUCKET = var.object_storage_bucket
    }
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "jwt_secret"
    environment_variable = "JWT_SECRET"
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "telegram_token"
    environment_variable = "TELEGRAM_BOT_TOKEN"
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "yokassa_shop_id"
    environment_variable = "YOOKASSA_SHOP_ID"
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "yokassa_secret_key"
    environment_variable = "YOOKASSA_SECRET_KEY"
  }

  secrets {
    id                   = yandex_lockbox_secret.db.id
    version_id           = yandex_lockbox_secret_version.db.id
    key                  = "database_url"
    environment_variable = "DATABASE_URL"
  }

  secrets {
    id                   = yandex_lockbox_secret.redis.id
    version_id           = yandex_lockbox_secret_version.redis.id
    key                  = "redis_url"
    environment_variable = "REDIS_URL"
  }

  log_options {
    folder_id = var.yc_folder_id
    min_level = "INFO"
  }
}

resource "yandex_serverless_container" "public_api" {
  name               = "${local.project_name}-${local.environment}-public-api"
  description        = "Public/widget HTTP API for RestoBot."
  memory             = 1024
  cores              = 1
  core_fraction      = 100
  concurrency        = 1
  execution_timeout  = "30s"
  service_account_id = yandex_iam_service_account.runtime.id

  runtime {
    type = "http"
  }

  connectivity {
    network_id = yandex_vpc_network.restobot.id
  }

  provision_policy {
    min_instances = 1
  }

  image {
    url      = var.public_image
    command  = ["sh", "-c"]
    args     = ["uvicorn apps.public_api.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
    work_dir = "/app"
    environment = {
      ENVIRONMENT              = "production"
      LOG_FORMAT               = "json"
      LOG_LEVEL                = "INFO"
      YC_CLOUD_ID              = var.yc_cloud_id
      YC_FOLDER_ID             = var.yc_folder_id
      YC_OBJECT_STORAGE_BUCKET = var.object_storage_bucket
    }
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "jwt_secret"
    environment_variable = "JWT_SECRET"
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "telegram_token"
    environment_variable = "TELEGRAM_BOT_TOKEN"
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "yokassa_shop_id"
    environment_variable = "YOOKASSA_SHOP_ID"
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "yokassa_secret_key"
    environment_variable = "YOOKASSA_SECRET_KEY"
  }

  secrets {
    id                   = yandex_lockbox_secret.db.id
    version_id           = yandex_lockbox_secret_version.db.id
    key                  = "database_url"
    environment_variable = "DATABASE_URL"
  }

  secrets {
    id                   = yandex_lockbox_secret.redis.id
    version_id           = yandex_lockbox_secret_version.redis.id
    key                  = "redis_url"
    environment_variable = "REDIS_URL"
  }

  log_options {
    folder_id = var.yc_folder_id
    min_level = "INFO"
  }
}

resource "yandex_serverless_container" "migration_runner" {
  name               = "${local.project_name}-${local.environment}-migration-runner"
  description        = "One-shot task container for Alembic migrations."
  memory             = 512
  cores              = 1
  core_fraction      = 100
  concurrency        = 1
  execution_timeout  = "600s"
  service_account_id = yandex_iam_service_account.runtime.id

  runtime {
    type = "task"
  }

  connectivity {
    network_id = yandex_vpc_network.restobot.id
  }

  image {
    url      = var.migration_image
    command  = ["python"]
    args     = ["scripts/migrate_cloud.py"]
    work_dir = "/app"
    environment = {
      ENVIRONMENT              = "production"
      LOG_FORMAT               = "json"
      LOG_LEVEL                = "INFO"
      YC_CLOUD_ID              = var.yc_cloud_id
      YC_FOLDER_ID             = var.yc_folder_id
      YC_OBJECT_STORAGE_BUCKET = var.object_storage_bucket
    }
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "jwt_secret"
    environment_variable = "JWT_SECRET"
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "telegram_token"
    environment_variable = "TELEGRAM_BOT_TOKEN"
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "yokassa_shop_id"
    environment_variable = "YOOKASSA_SHOP_ID"
  }

  secrets {
    id                   = yandex_lockbox_secret.common.id
    version_id           = yandex_lockbox_secret_version.common.id
    key                  = "yokassa_secret_key"
    environment_variable = "YOOKASSA_SECRET_KEY"
  }

  secrets {
    id                   = yandex_lockbox_secret.db.id
    version_id           = yandex_lockbox_secret_version.db.id
    key                  = "database_url"
    environment_variable = "DATABASE_URL"
  }

  secrets {
    id                   = yandex_lockbox_secret.redis.id
    version_id           = yandex_lockbox_secret_version.redis.id
    key                  = "redis_url"
    environment_variable = "REDIS_URL"
  }

  log_options {
    folder_id = var.yc_folder_id
    min_level = "INFO"
  }
}

resource "yandex_serverless_container_iam_binding" "admin_invoker" {
  container_id = yandex_serverless_container.admin_api.id
  role         = "serverless.containers.invoker"
  members      = ["serviceAccount:${yandex_iam_service_account.runtime.id}"]
}

resource "yandex_serverless_container_iam_binding" "public_invoker" {
  container_id = yandex_serverless_container.public_api.id
  role         = "serverless.containers.invoker"
  members      = ["serviceAccount:${yandex_iam_service_account.runtime.id}"]
}

resource "yandex_serverless_container_iam_binding" "migration_invoker" {
  container_id = yandex_serverless_container.migration_runner.id
  role         = "serverless.containers.invoker"
  members      = ["serviceAccount:${yandex_iam_service_account.runtime.id}"]
}

# The Terraform provider currently exposes prepared instances but not a first-class max-instances
# knob for Serverless Containers. The deployment guide documents an optional post-deploy CLI hard cap
# if you need a strict ceiling beyond the default quota-based scaling behavior.
