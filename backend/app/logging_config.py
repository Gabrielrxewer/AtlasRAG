from __future__ import annotations

import contextvars
import json
import logging
import logging.config
from datetime import datetime, timezone

from app.config import settings

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if getattr(record, "request_id", None):
            payload["request_id"] = record.request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS and key not in {"request_id", "message", "asctime"}
        }
        if extras:
            payload["extra"] = extras
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    level = settings.log_level.upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"request_id": {"()": RequestIdFilter}},
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["request_id"],
                    "level": level,
                }
            },
            "root": {"handlers": ["default"], "level": level},
            "loggers": {
                "atlasrag": {"handlers": ["default"], "level": level, "propagate": False},
                "uvicorn.access": {"level": "WARNING", "propagate": True},
                "uvicorn.error": {"level": level, "propagate": True},
            },
        }
    )
    logging.captureWarnings(True)
    atlas_logger = logging.getLogger("atlasrag")
    atlas_logger.setLevel(level)
    for name, logger in logging.root.manager.loggerDict.items():
        if name.startswith("atlasrag.") and isinstance(logger, logging.Logger):
            logger.setLevel(level)
            logger.propagate = True
    atlas_logger.info("logging_configured", extra={"log_level": level})
