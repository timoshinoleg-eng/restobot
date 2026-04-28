resource "yandex_container_registry" "restobot" {
  name = "${local.project_name}-${local.environment}-registry"
}

resource "yandex_container_repository" "admin" {
  name = "${yandex_container_registry.restobot.id}/restobot-admin"
}

resource "yandex_container_repository" "public" {
  name = "${yandex_container_registry.restobot.id}/restobot-public"
}

resource "yandex_container_repository" "migration" {
  name = "${yandex_container_registry.restobot.id}/restobot-migrate"
}

resource "yandex_container_registry_iam_binding" "runtime_puller" {
  registry_id = yandex_container_registry.restobot.id
  role        = "container-registry.images.puller"
  members     = ["serviceAccount:${yandex_iam_service_account.runtime.id}"]
}
