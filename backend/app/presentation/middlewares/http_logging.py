"""Middleware para logging de requests HTTP."""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure.observability.request_id import new_request_id, set_request_id
from app.infrastructure.observability.logging import get_logger

log = get_logger("http")
SENSITIVE_HEADERS = {"authorization", "cookie"}


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    """Oculta headers sensíveis antes de logar."""
    output: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            output[key] = "***"
        else:
            output[key] = value
    return output


class HttpLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware que adiciona request_id e métricas de tempo."""
    async def dispatch(self, request: Request, call_next):
        # Gera/propaga request_id para rastreio.
        request_id = (
            request.headers.get("x-request-id")
            or request.headers.get("x-correlation-id")
            or new_request_id()
        )
        set_request_id(request_id)
        start = time.perf_counter()

        log.info(
            "http_in",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "query": dict(request.query_params),
                "headers": _safe_headers(dict(request.headers)),
            },
        )

        try:
            response: Response = await call_next(request)
        except Exception:
            # Loga exceções durante processamento.
            log.exception(
                "http_exception",
                extra={"method": request.method, "path": str(request.url.path)},
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        if response.status_code >= 500:
            level = log.error
        elif response.status_code >= 400:
            level = log.warning
        else:
            level = log.info

        level(
            "http_out",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        response.headers["x-request-id"] = request_id
        return response
