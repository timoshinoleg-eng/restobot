# ---------------------------------------------------------------------------
# YC Serverless Containers service subnet ingress rules
# ---------------------------------------------------------------------------
# This is NOT an empirically discovered / guessed range.
# 198.19.0.0/16 is the documented Yandex Cloud Serverless service subnet
# CIDR used by Serverless Containers (and Cloud Functions) runtime for
# outbound NAT / service traffic.  When connectivity is enabled on a
# serverless container, traffic to managed DB/Redis exits from IPs within
# this range.  Without explicit SG rules allowing this CIDR, the managed
# services drop SYN packets → TCP timeout → container execution timeout
# → 504 from API Gateway.
# ---------------------------------------------------------------------------

locals {
  # CIDR documented for Yandex Cloud Serverless Containers service subnet.
  yc_serverless_service_cidr = "198.19.0.0/16"
}

# PostgreSQL (Managed PostgreSQL cluster: restobot-mvp-postgres)
resource "yandex_vpc_security_group_rule" "serverless_to_postgres" {
  security_group_binding = "enpalmp64msgpupnbh75"
  direction              = "ingress"
  description            = "Allow PostgreSQL from YC Serverless Containers service subnet (198.19.0.0/16)"
  protocol               = "TCP"
  port                   = 6432
  v4_cidr_blocks         = [local.yc_serverless_service_cidr]
}

# Redis (Managed Redis cluster: restobot-mvp-redis)
resource "yandex_vpc_security_group_rule" "serverless_to_redis" {
  security_group_binding = "enpalmp64msgpupnbh75"
  direction              = "ingress"
  description            = "Allow Redis from YC Serverless Containers service subnet (198.19.0.0/16)"
  protocol               = "TCP"
  port                   = 6379
  v4_cidr_blocks         = [local.yc_serverless_service_cidr]
}

# Redis TLS (Managed Redis cluster: restobot-mvp-redis)
resource "yandex_vpc_security_group_rule" "serverless_to_redis_tls" {
  security_group_binding = "enpalmp64msgpupnbh75"
  direction              = "ingress"
  description            = "Allow Redis TLS from YC Serverless Containers service subnet (198.19.0.0/16)"
  protocol               = "TCP"
  port                   = 6380
  v4_cidr_blocks         = [local.yc_serverless_service_cidr]
}
