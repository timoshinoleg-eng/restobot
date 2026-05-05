output "gateway_url" {
  description = "Public URL of the Yandex API Gateway."
  value       = "https://${yandex_api_gateway.restobot.domain}"
}

output "admin_container_id" {
  description = "ID of the admin Serverless Container."
  value       = yandex_serverless_container.admin_api.id
}

output "public_container_id" {
  description = "ID of the public Serverless Container."
  value       = yandex_serverless_container.public_api.id
}

output "db_host" {
  description = "Managed PostgreSQL host FQDN."
  value       = var.existing_db_host
}

output "redis_host" {
  description = "Managed Redis host FQDN."
  value       = var.existing_redis_host
}

output "migration_container_url" {
  description = "Direct HTTPS invoke URL for the migration runner task container."
  value       = yandex_serverless_container.migration_runner.url
}

output "registry_id" {
  description = "Container Registry ID used for image pushes."
  value       = yandex_container_registry.restobot.id
}
