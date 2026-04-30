variable "yc_cloud_id" {
  description = "Yandex Cloud ID. Can also be provided via YC_CLOUD_ID."
  type        = string
}

variable "yc_folder_id" {
  description = "Yandex Cloud folder ID. Can also be provided via YC_FOLDER_ID."
  type        = string
}

variable "yc_token" {
  description = "Yandex Cloud IAM/OAuth token. Can also be provided via YC_TOKEN."
  type        = string
  default     = null
  sensitive   = true
}

variable "db_password" {
  description = "Password for the managed PostgreSQL user restobot."
  type        = string
  sensitive   = true
}

variable "redis_password" {
  description = "Password for the managed Redis cluster."
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "JWT signing secret for the application."
  type        = string
  sensitive   = true
}

variable "telegram_token" {
  description = "Telegram bot token."
  type        = string
  sensitive   = true
}

variable "yokassa_shop_id" {
  description = "YooKassa shop ID."
  type        = string
  sensitive   = true
}

variable "yokassa_secret_key" {
  description = "YooKassa secret key."
  type        = string
  sensitive   = true
}

variable "bootstrap_api_token" {
  description = "Optional bootstrap token required for production onboarding and smoke bootstrap."
  type        = string
  default     = null
  sensitive   = true
}

variable "enable_bootstrap_api" {
  description = "Whether the protected bootstrap onboarding endpoint is enabled in production."
  type        = bool
  default     = false
  validation {
    condition     = var.enable_bootstrap_api == false || var.bootstrap_api_token != null
    error_message = "bootstrap_api_token must be set when enable_bootstrap_api is true."
  }
}

variable "database_pool_min" {
  description = "Minimum SQLAlchemy/asyncpg pool size per container instance."
  type        = number
  default     = 1
  validation {
    condition     = var.database_pool_min >= 1
    error_message = "database_pool_min must be at least 1."
  }
}

variable "database_pool_max" {
  description = "Maximum SQLAlchemy/asyncpg pool size per container instance."
  type        = number
  default     = 2
  validation {
    condition     = var.database_pool_max >= var.database_pool_min
    error_message = "database_pool_max must be greater than or equal to database_pool_min."
  }
}

variable "yc_zone" {
  description = "Primary availability zone for VPC subnet and managed databases."
  type        = string
  default     = "ru-central1-a"
}

variable "subnet_cidr" {
  description = "Single /24 subnet used by serverless connectivity and managed databases."
  type        = string
  default     = "10.10.0.0/24"
}

variable "object_storage_bucket" {
  description = "Bucket name passed to the apps for future media storage usage."
  type        = string
  default     = "restobot-mvp-assets"
}

variable "admin_image" {
  description = "Admin API image URL in Yandex Container Registry."
  type        = string
  default     = "cr.yandex/placeholder/restobot-admin:latest"
}

variable "public_image" {
  description = "Public API image URL in Yandex Container Registry."
  type        = string
  default     = "cr.yandex/placeholder/restobot-public:latest"
}

variable "migration_image" {
  description = "Migration runner image URL in Yandex Container Registry."
  type        = string
  default     = "cr.yandex/placeholder/restobot-admin:latest"
}
