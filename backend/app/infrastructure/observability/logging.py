"""Setup básico de logging para ambientes locais."""
import logging
import os
from logging.config import dictConfig

_CONFIGURED = False


def setup_logging() -> None:
    """Configura logger raiz com formatter JSON e filtros."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"

    # Remove handlers anteriores para evitar duplicidade.
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "fmt": log_format,
                },
            },
            "filters": {"request_id": {"()": "app.infrastructure.observability.request_id.RequestIdFilter"}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["request_id"],
                    "level": level,
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                "uvicorn": {"level": level, "propagate": True},
                "uvicorn.error": {"level": level, "propagate": True},
                "uvicorn.access": {"level": level, "propagate": True},
                "alembic": {"level": level, "propagate": True},
                "atlasrag": {"level": level, "propagate": True},
            },
        }
    )
    # Encaminha warnings para o logging padrão.
    logging.captureWarnings(True)
    logging.getLogger("atlasrag").info("logging_configured", extra={"log_level": level})


def get_logger(name: str) -> logging.Logger:
    """Helper para recuperar logger nomeado."""
    return logging.getLogger(name)
