locals {
  db_host      = yandex_mdb_postgresql_cluster.restobot.host[0].fqdn
  redis_host   = yandex_mdb_redis_cluster.restobot.host[0].fqdn
  database_url = "postgresql+asyncpg://${yandex_mdb_postgresql_user.restobot.name}:${urlencode(var.db_password)}@${local.db_host}:6432/${yandex_mdb_postgresql_database.restobot.name}"
  redis_url    = "rediss://:${urlencode(var.redis_password)}@${local.redis_host}:6379/0"
}

resource "yandex_lockbox_secret" "common" {
  name = "${local.project_name}/common"
}

resource "yandex_lockbox_secret" "db" {
  name = "${local.project_name}/db"
}

resource "yandex_lockbox_secret" "redis" {
  name = "${local.project_name}/redis"
}

resource "yandex_lockbox_secret_version" "common" {
  secret_id = yandex_lockbox_secret.common.id

  entries {
    key = "jwt_secret"
    command {
      path = "python"
      args = ["${path.module}/scripts/echo_secret.py"]
      env = {
        SECRET_VALUE = var.jwt_secret
      }
    }
  }

  entries {
    key = "telegram_token"
    command {
      path = "python"
      args = ["${path.module}/scripts/echo_secret.py"]
      env = {
        SECRET_VALUE = var.telegram_token
      }
    }
  }

  entries {
    key = "yokassa_shop_id"
    command {
      path = "python"
      args = ["${path.module}/scripts/echo_secret.py"]
      env = {
        SECRET_VALUE = var.yokassa_shop_id
      }
    }
  }

  entries {
    key = "yokassa_secret_key"
    command {
      path = "python"
      args = ["${path.module}/scripts/echo_secret.py"]
      env = {
        SECRET_VALUE = var.yokassa_secret_key
      }
    }
  }

  dynamic "entries" {
    for_each = var.bootstrap_api_token == null ? [] : [var.bootstrap_api_token]
    content {
      key = "bootstrap_api_token"
      command {
        path = "python"
        args = ["${path.module}/scripts/echo_secret.py"]
        env = {
          SECRET_VALUE = entries.value
        }
      }
    }
  }
}

resource "yandex_lockbox_secret_version" "db" {
  secret_id = yandex_lockbox_secret.db.id

  entries {
    key = "db_user"
    command {
      path = "python"
      args = ["${path.module}/scripts/echo_secret.py"]
      env = {
        SECRET_VALUE = yandex_mdb_postgresql_user.restobot.name
      }
    }
  }

  entries {
    key = "db_password"
    command {
      path = "python"
      args = ["${path.module}/scripts/echo_secret.py"]
      env = {
        SECRET_VALUE = var.db_password
      }
    }
  }

  entries {
    key = "database_url"
    command {
      path = "python"
      args = ["${path.module}/scripts/echo_secret.py"]
      env = {
        SECRET_VALUE = local.database_url
      }
    }
  }
}

resource "yandex_lockbox_secret_version" "redis" {
  secret_id = yandex_lockbox_secret.redis.id

  entries {
    key = "redis_password"
    command {
      path = "python"
      args = ["${path.module}/scripts/echo_secret.py"]
      env = {
        SECRET_VALUE = var.redis_password
      }
    }
  }

  entries {
    key = "redis_url"
    command {
      path = "python"
      args = ["${path.module}/scripts/echo_secret.py"]
      env = {
        SECRET_VALUE = local.redis_url
      }
    }
  }
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
