"""Cliente HTTPX com hooks de observabilidade."""
import time

import httpx

from app.infrastructure.observability.logging import get_logger

log = get_logger("httpx")


def build_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """Constrói AsyncClient com logs de requisição/response."""
    async def on_request(request: httpx.Request):
        # Marca início para calcular latência da requisição externa.
        request.extensions["start_time"] = time.perf_counter()
        log.info("out_req", extra={"method": request.method, "url": str(request.url)})

    async def on_response(response: httpx.Response):
        # Usa o timestamp salvo para medir duração.
        start = response.request.extensions.get("start_time")
        duration_ms = (time.perf_counter() - start) * 1000 if start else None
        log.info(
            "out_res",
            extra={
                "method": response.request.method,
                "url": str(response.request.url),
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2) if duration_ms else None,
            },
        )

    # Centraliza hooks de observabilidade para clientes outbound.
    return httpx.AsyncClient(timeout=timeout, event_hooks={"request": [on_request], "response": [on_response]})
