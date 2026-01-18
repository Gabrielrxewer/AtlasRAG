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
    url = engine.url.render_as_string(hide_password=False)
    assert "p@ss:word/123" not in url
    assert "p%40ss%3Aword%2F123" in url
