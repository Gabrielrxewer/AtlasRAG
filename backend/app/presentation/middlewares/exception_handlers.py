"""Tratamento de exceções não capturadas."""
from fastapi import Request
from fastapi.responses import JSONResponse

from app.infrastructure.observability.logging import get_logger
from app.core.config import settings

log = get_logger("errors")


def _cors_headers(request: Request) -> dict[str, str]:
    """Reaplica CORS para respostas de erro."""
    origin = request.headers.get("origin")
    if not origin:
        return {}
    allowed = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
    if settings.environment == "development" and not allowed:
        allowed = ["http://localhost:5173", "http://localhost:4173"]
    if "*" in allowed or origin in allowed:
        headers = {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
        if settings.cors_allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"
        return headers
    return {}


async def unhandled_exception_handler(request: Request, exc: Exception):
    """Handler global para erros 500 inesperados."""
    log.exception(
        "unhandled_exception",
        extra={"method": request.method, "path": str(request.url.path)},
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "requestId": request.headers.get("x-request-id")},
        headers=_cors_headers(request),
    )
