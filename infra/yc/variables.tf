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
