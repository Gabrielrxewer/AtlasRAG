"""Gerencia request id via contextvars para rastreio de logs."""
import contextvars
import logging
import uuid

# Contexto por request para correlação de logs.
request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    """Recupera o request id atual."""
    return request_id_ctx_var.get() or ""


def set_request_id(value: str) -> None:
    """Define o request id corrente."""
    request_id_ctx_var.set(value)


def new_request_id() -> str:
    """Gera um novo request id."""
    return str(uuid.uuid4())


class RequestIdFilter(logging.Filter):
    """Filtro de log que injeta request_id nos registros."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True
