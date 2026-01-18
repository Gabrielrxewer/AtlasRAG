import time
import uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import connections, scans, tables, api_routes, rag

app = FastAPI(title="AtlasRAG API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

rate_limit_state: dict[str, list[float]] = {}


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.middleware("http")
async def rag_rate_limit(request: Request, call_next):
    if request.url.path.endswith("/rag/ask"):
        now = time.time()
        window = 60
        key = request.client.host if request.client else "unknown"
        recent = [timestamp for timestamp in rate_limit_state.get(key, []) if now - timestamp < window]
        if len(recent) >= settings.rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        recent.append(now)
        rate_limit_state[key] = recent
    return await call_next(request)


app.include_router(connections.router)
app.include_router(scans.router)
app.include_router(tables.router)
app.include_router(api_routes.router)
app.include_router(rag.router)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}
