resource "yandex_vpc_network" "restobot" {
  name = "${local.project_name}-${local.environment}-network"
}

resource "yandex_vpc_subnet" "restobot" {
  name           = "${local.project_name}-${local.environment}-subnet"
  zone           = var.yc_zone
  network_id     = yandex_vpc_network.restobot.id
  v4_cidr_blocks = [var.subnet_cidr]
}

resource "yandex_vpc_security_group" "restobot_data_plane" {
  name        = "${local.project_name}-${local.environment}-data-plane"
  description = "Allows east-west traffic inside the subnet and app access to PostgreSQL/Redis."
  network_id  = yandex_vpc_network.restobot.id

  ingress {
    description       = "Allow any traffic inside the security group."
    protocol          = "ANY"
    predefined_target = "self_security_group"
  }

  ingress {
    description    = "Allow PostgreSQL from the serverless subnet."
    protocol       = "TCP"
    port           = 6432
    v4_cidr_blocks = [var.subnet_cidr]
  }

  ingress {
    description    = "Allow Redis from the serverless subnet."
    protocol       = "TCP"
    port           = 6379
    v4_cidr_blocks = [var.subnet_cidr]
  }

  egress {
    description    = "Allow response traffic and internal egress."
    protocol       = "ANY"
    from_port      = 0
    to_port        = 65535
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}

# API Gateway reaches Serverless Containers through a platform-managed integration rather than
# through a VPC NIC, so no additional SG rule is required for gateway->container HTTP traffic.
