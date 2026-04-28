output "tfstate_bucket_name" {
  description = "Object Storage bucket that stores Terraform state."
  value       = yandex_storage_bucket.tfstate.bucket
}

output "tfstate_access_key" {
  description = "Static access key ID for the Terraform S3 backend."
  value       = yandex_iam_service_account_static_access_key.tfstate.access_key
  sensitive   = true
}

output "tfstate_secret_key" {
  description = "Static secret access key for the Terraform S3 backend."
  value       = yandex_iam_service_account_static_access_key.tfstate.secret_key
  sensitive   = true
}

output "backend_init_example" {
  description = "Example command for backend initialization."
  value       = "terraform -chdir=infra/yc init -reconfigure -backend-config=backend.hcl"
}
