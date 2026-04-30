resource "yandex_api_gateway" "restobot" {
  name              = "${local.project_name}-${local.environment}-gateway"
  description       = "Public gateway for RestoBot admin and widget APIs."
  execution_timeout = "30s"

  spec = <<-EOT
openapi: 3.0.0
info:
  title: RestoBot MVP Gateway
  version: "1.0.0"
paths:
  /health:
    get:
      operationId: gatewayHealth
      x-yc-apigateway-integration:
        type: serverless_containers
        container_id: ${yandex_serverless_container.admin_api.id}
        service_account_id: ${yandex_iam_service_account.runtime.id}
  /admin/{proxy+}:
    x-yc-apigateway-any-method:
      parameters:
        - name: proxy
          in: path
          required: false
          explode: false
          style: simple
          schema:
            type: string
            default: "-"
      x-yc-apigateway-integration:
        type: serverless_containers
        container_id: ${yandex_serverless_container.admin_api.id}
        service_account_id: ${yandex_iam_service_account.runtime.id}
  /widget/{proxy+}:
    x-yc-apigateway-any-method:
      parameters:
        - name: proxy
          in: path
          required: false
          explode: false
          style: simple
          schema:
            type: string
            default: "-"
      x-yc-apigateway-integration:
        type: serverless_containers
        container_id: ${yandex_serverless_container.public_api.id}
        service_account_id: ${yandex_iam_service_account.runtime.id}
  /api/v1/{proxy+}:
    x-yc-apigateway-any-method:
      parameters:
        - name: proxy
          in: path
          required: false
          explode: false
          style: simple
          schema:
            type: string
            default: "-"
      x-yc-apigateway-integration:
        type: serverless_containers
        container_id: ${yandex_serverless_container.public_api.id}
        service_account_id: ${yandex_iam_service_account.runtime.id}
EOT
}
