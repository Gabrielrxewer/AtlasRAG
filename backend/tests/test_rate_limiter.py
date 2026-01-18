import pytest

pytest.importorskip("fastapi")
from app.main import RateLimiter


def test_rate_limiter_blocks_after_limit():
    limiter = RateLimiter(max_keys=10, window_seconds=60)
    assert limiter.allow("client", 2) is True
    assert limiter.allow("client", 2) is True
    assert limiter.allow("client", 2) is False
