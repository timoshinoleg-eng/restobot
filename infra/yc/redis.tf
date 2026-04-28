resource "yandex_mdb_redis_cluster" "restobot" {
  name               = "${local.project_name}-${local.environment}-redis"
  environment        = "PRODUCTION"
  network_id         = yandex_vpc_network.restobot.id
  security_group_ids = [yandex_vpc_security_group.restobot_data_plane.id]
  tls_enabled        = false

  config {
    password = var.redis_password
    version  = "7.0"
  }

  resources {
    # 2 GB burst classes are deprecated in current YC docs; b2.medium is the smallest supported option.
    resource_preset_id = "b2.medium"
    disk_size          = 8
  }

  host {
    zone      = var.yc_zone
    subnet_id = yandex_vpc_subnet.restobot.id
  }

  maintenance_window {
    type = "ANYTIME"
  }
}
