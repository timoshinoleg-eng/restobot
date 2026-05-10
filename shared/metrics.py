# shared/metrics.py
"""Prometheus metrics for RestoBot services."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, Info, generate_latest

APP_INFO = Info("restobot_app", "Application information")
APP_INFO.info({"version": "1.0.0"})

# Order metrics
ORDERS_CREATED = Counter(
    "restobot_orders_created_total",
    "Total orders created",
    ["tenant", "type"],
)

ORDERS_PAID = Counter(
    "restobot_orders_paid_total",
    "Total orders paid",
    ["tenant"],
)

# Payment metrics
PAYMENTS_PROCESSED = Counter(
    "restobot_payments_processed_total",
    "Total payments processed",
    ["tenant", "status"],
)

# AI metrics
AI_REQUESTS = Counter(
    "restobot_ai_requests_total",
    "Total AI requests",
    ["tenant", "source"],
)

AI_LATENCY = Histogram(
    "restobot_ai_latency_seconds",
    "AI request latency",
    ["tenant", "source"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Bot metrics
BOT_COMMANDS = Counter(
    "restobot_bot_commands_total",
    "Total bot commands received",
    ["command"],
)


def metrics_endpoint() -> bytes:
    """Generate Prometheus metrics exposition format."""
    return generate_latest()
