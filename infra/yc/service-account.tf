resource "yandex_iam_service_account" "runtime" {
  name        = "${local.project_name}-${local.environment}-runtime"
  description = "Runtime and gateway invocation service account for RestoBot MVP."
}

resource "yandex_resourcemanager_folder_iam_member" "runtime_monitoring_editor" {
  folder_id = var.yc_folder_id
  role      = "monitoring.editor"
  member    = "serviceAccount:${yandex_iam_service_account.runtime.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "runtime_container_invoker" {
  folder_id = var.yc_folder_id
  role      = "serverless.containers.invoker"
  member    = "serviceAccount:${yandex_iam_service_account.runtime.id}"
}
