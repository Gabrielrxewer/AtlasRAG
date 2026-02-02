import contextvars
import logging
import uuid

request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    return request_id_ctx_var.get() or ""


def set_request_id(value: str) -> None:
    request_id_ctx_var.set(value)


def new_request_id() -> str:
    return str(uuid.uuid4())


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True
