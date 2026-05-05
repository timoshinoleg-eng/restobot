resource "yandex_vpc_network" "restobot" {
  name = "${local.project_name}-${local.environment}-network"
}

# The pilot reuses an already provisioned subnet and security group outside Terraform.
