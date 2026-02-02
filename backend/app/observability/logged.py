import functools
import time

from app.observability.logging import get_logger


def logged(scope: str):
    logger = get_logger(scope)

    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            logger.debug("method_in", extra={"fn": fn.__name__})
            try:
                result = await fn(*args, **kwargs)
            except Exception:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.exception("method_err", extra={"fn": fn.__name__, "duration_ms": round(duration_ms, 2)})
                raise
            duration_ms = (time.perf_counter() - start) * 1000
            logger.debug("method_out", extra={"fn": fn.__name__, "duration_ms": round(duration_ms, 2)})
            return result

        return wrapper

    return deco
