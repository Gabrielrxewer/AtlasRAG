from fastapi import Request
from fastapi.responses import JSONResponse

from app.observability.logging import get_logger

log = get_logger("errors")


async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception(
        "unhandled_exception",
        extra={"method": request.method, "path": str(request.url.path)},
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "requestId": request.headers.get("x-request-id")},
    )
