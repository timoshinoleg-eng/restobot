variable "yc_cloud_id" {
  description = "Yandex Cloud ID."
  type        = string
}

variable "yc_folder_id" {
  description = "Yandex Cloud folder ID."
  type        = string
}

variable "yc_token" {
  description = "Yandex Cloud IAM/OAuth token."
  type        = string
  default     = null
  sensitive   = true
}

variable "yc_zone" {
  description = "Primary zone used only for provider initialization."
  type        = string
  default     = "ru-central1-a"
}

variable "tfstate_bucket_name" {
  description = "Globally unique Object Storage bucket name for Terraform state."
  type        = string
}

variable "tfstate_service_account_name" {
  description = "Service account name used by Terraform S3 backend."
  type        = string
  default     = "restobot-tfstate"
}

variable "force_destroy_bucket" {
  description = "Allow destroying the backend bucket with objects inside."
  type        = bool
  default     = false
}
