"""JSON logging helpers with request-id propagation."""

import json
import logging
import sys
from contextvars import ContextVar, Token

from shared.config import get_settings

settings = get_settings()
request_id_context: ContextVar[str] = ContextVar("request_id", default="-")

try:
    from pythonjsonlogger import jsonlogger
except ImportError:  # pragma: no cover - fallback for partially provisioned local envs
    jsonlogger = None


class RequestIdFilter(logging.Filter):
    """Inject the current request id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get("-")
        return True


def set_request_id(value: str) -> Token[str]:
    """Store request id in context variables."""
    return request_id_context.set(value)


def reset_request_id(token: Token[str]) -> None:
    """Reset request id context."""
    request_id_context.reset(token)


def configure_logging() -> None:
    """Configure root logging for apps and workers."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())

    if settings.LOG_FORMAT == "json" and jsonlogger is not None:
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
        )
    elif settings.LOG_FORMAT == "json":
        formatter = _FallbackJsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        )

    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.LOG_LEVEL)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "asyncpg"):
        logging.getLogger(logger_name).handlers = [handler]
        logging.getLogger(logger_name).setLevel(settings.LOG_LEVEL)


class _FallbackJsonFormatter(logging.Formatter):
    """Minimal JSON formatter used when python-json-logger is not installed yet."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "asctime": self.formatTime(record, self.datefmt),
            "levelname": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)
