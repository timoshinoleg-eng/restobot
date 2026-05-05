resource "yandex_lockbox_secret" "common" {
  name = "${local.project_name}/common"
}

resource "yandex_lockbox_secret" "db" {
  name = "${local.project_name}/db"
}

resource "yandex_lockbox_secret" "redis" {
  name = "${local.project_name}/redis"
}

resource "yandex_lockbox_secret_iam_binding" "common_payload_viewer" {
  secret_id = yandex_lockbox_secret.common.id
  role      = "lockbox.payloadViewer"
  members   = ["serviceAccount:${yandex_iam_service_account.runtime.id}"]
}

resource "yandex_lockbox_secret_iam_binding" "db_payload_viewer" {
  secret_id = yandex_lockbox_secret.db.id
  role      = "lockbox.payloadViewer"
  members   = ["serviceAccount:${yandex_iam_service_account.runtime.id}"]
}

resource "yandex_lockbox_secret_iam_binding" "redis_payload_viewer" {
  secret_id = yandex_lockbox_secret.redis.id
  role      = "lockbox.payloadViewer"
  members   = ["serviceAccount:${yandex_iam_service_account.runtime.id}"]
}
