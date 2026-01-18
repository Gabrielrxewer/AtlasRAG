import logging
import time
import uuid
from collections import OrderedDict
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import connections, scans, tables, api_routes, rag

app = FastAPI(title="AtlasRAG API", version="0.1.0")

logger = logging.getLogger("atlasrag")


class RateLimiter:
    def __init__(self, max_keys: int, window_seconds: int):
        self.max_keys = max_keys
        self.window_seconds = window_seconds
        self.cache: OrderedDict[str, list[float]] = OrderedDict()

    def allow(self, key: str, limit: int) -> bool:
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
    if settings.environment == "production" and not origins:
        raise RuntimeError("CORS origins must be set in production")
    if settings.cors_allow_credentials and "*" in origins:
        raise RuntimeError("CORS origin '*' is not allowed with credentials enabled")
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
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    response.headers["x-request-id"] = request_id
    return response


@app.middleware("http")
async def rag_rate_limit(request: Request, call_next):
    if request.url.path.endswith("/rag/ask"):
        key = request.client.host if request.client else "unknown"
        if not rate_limiter.allow(key, settings.rate_limit_per_minute):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return await call_next(request)


app.include_router(connections.router)
app.include_router(scans.router)
app.include_router(tables.router)
app.include_router(api_routes.router)
app.include_router(rag.router)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}
