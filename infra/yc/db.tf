resource "yandex_mdb_postgresql_cluster" "restobot" {
  name               = "${local.project_name}-${local.environment}-postgres"
  environment        = "PRODUCTION"
  network_id         = yandex_vpc_network.restobot.id
  security_group_ids = [yandex_vpc_security_group.restobot_data_plane.id]

  config {
    version = "15"

    resources {
      # Current supported minimum that matches the requested 4 GB RAM profile.
      resource_preset_id = "b1.medium"
      disk_type_id       = "network-ssd"
      disk_size          = 20
    }

    access {
      data_lens = false
    }

    postgresql_config = {
      max_connections = 100
    }
  }

  host {
    zone      = var.yc_zone
    subnet_id = yandex_vpc_subnet.restobot.id
  }

  maintenance_window {
    type = "ANYTIME"
  }
}

resource "yandex_mdb_postgresql_user" "restobot" {
  cluster_id = yandex_mdb_postgresql_cluster.restobot.id
  name       = "restobot"
  password   = var.db_password
  conn_limit = 100

  settings = {
    default_transaction_isolation = "read committed"
    lock_timeout                  = 5000
  }
}

resource "yandex_mdb_postgresql_database" "restobot" {
  cluster_id = yandex_mdb_postgresql_cluster.restobot.id
  name       = "restobot"
  owner      = yandex_mdb_postgresql_user.restobot.name

  extension {
    name = "uuid-ossp"
  }

  extension {
    name = "vector"
  }
}
