import pytest

pytest.importorskip("sqlalchemy")
from app.services.scan import ConnectionInfo, _build_client_engine


def test_build_client_engine_allows_special_chars():
    info = ConnectionInfo(
        host="localhost",
        port=5432,
        database="atlas",
        username="user",
        password="p@ss:word/123",
        ssl_mode="prefer",
    )
    engine = _build_client_engine(info)
    assert engine.url.password == "p@ss:word/123"
    hidden = engine.url.render_as_string(hide_password=True)
    assert "p@ss:word/123" not in hidden
