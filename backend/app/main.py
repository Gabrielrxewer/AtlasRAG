import time
import uuid
from pathlib import Path
from collections import OrderedDict
from threading import Lock
from urllib.parse import urlparse
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from alembic import command
from alembic.config import Config

from app.config import settings
from app.observability.logging import setup_logging, get_logger
from app.observability.request_id import set_request_id, new_request_id, get_request_id
from app.middlewares.http_logging import HttpLoggingMiddleware
from app.middlewares.exception_handlers import unhandled_exception_handler
from app.api import connections, scans, tables, api_routes, rag, agents

setup_logging()

app = FastAPI(title="AtlasRAG API", version="0.1.0")
app.add_middleware(HttpLoggingMiddleware)
app.add_exception_handler(Exception, unhandled_exception_handler)

logger = get_logger("atlasrag")


def _run_migrations() -> None:
    config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    alembic_cfg = Config(str(config_path))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    origin = request.headers.get("origin")
    headers = {"X-Request-ID": request_id}
    if origin and (origin in cors_origins or "*" in cors_origins):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
        if settings.cors_allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
        headers=headers,
    )


class RateLimiter:
    def __init__(self, max_keys: int, window_seconds: int):
        self.max_keys = max_keys
        self.window_seconds = window_seconds
        self.cache: OrderedDict[str, list[float]] = OrderedDict()
        self.lock = Lock()

    def allow(self, key: str, limit: int) -> bool:
        # Sliding window rate limiter stored in-memory (per-process).
        with self.lock:
            now = time.time()
            timestamps = self.cache.get(key, [])
            timestamps = [ts for ts in timestamps if now - ts < self.window_seconds]
            if len(timestamps) >= limit:
                self.cache[key] = timestamps
                return False
            timestamps.append(now)
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = timestamps
            self._cleanup()
            return True

    def _cleanup(self) -> None:
        while len(self.cache) > self.max_keys:
            self.cache.popitem(last=False)


rate_limiter = RateLimiter(max_keys=10_000, window_seconds=60)


def _parse_cors_origins(raw: str) -> list[str]:
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if settings.environment == "development" and not origins:
        origins = ["http://localhost:5173", "http://localhost:4173"]
    if settings.environment == "production" and not origins:
        raise RuntimeError("CORS origins must be set in production")
    if settings.cors_allow_credentials and "*" in origins:
        raise RuntimeError("CORS origin '*' is not allowed with credentials enabled")
    if settings.cors_allow_credentials:
        for origin in origins:
            parsed = urlparse(origin)
            if not parsed.scheme or not parsed.netloc:
                raise RuntimeError("CORS origin must include scheme and host")
    return origins


cors_origins = _parse_cors_origins(settings.cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", get_request_id() or new_request_id())
    request.state.request_id = request_id
    set_request_id(request_id)
    start = time.perf_counter()

    if request.url.path.endswith("/rag/ask"):
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        key = _extract_client_ip(forwarded_for, request.client.host if request.client else None)
        if not rate_limiter.allow(key, settings.rate_limit_per_minute):
            duration_ms = (time.perf_counter() - start) * 1000
            _log_request(request, request_id, key, 429, duration_ms)
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "request_id": request_id},
            )
            response.headers["X-Request-ID"] = request_id
            return response

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        client_ip = request.client.host if request.client else None
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": round(duration_ms, 2),
                "client_ip": client_ip,
            },
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start) * 1000
        _log_request(
            request,
            request_id,
            request.client.host if request.client else None,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        set_request_id("")


def _extract_client_ip(x_forwarded_for: str, fallback: str | None) -> str:
    if x_forwarded_for:
        for value in x_forwarded_for.split(","):
            candidate = value.strip()
            if candidate:
                return candidate
    return fallback or "unknown"


def _log_request(request: Request, request_id: str, client_ip: str | None, status_code: int, duration_ms: float) -> None:
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": client_ip or "unknown",
        },
    )


app.include_router(connections.router)
app.include_router(scans.router)
app.include_router(tables.router)
app.include_router(api_routes.router)
app.include_router(rag.router)
app.include_router(agents.router)


@app.on_event("startup")
def run_migrations_on_startup() -> None:
    logger.info("Running database migrations")
    _run_migrations()


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}
