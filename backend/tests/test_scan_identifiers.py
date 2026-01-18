import pytest

pytest.importorskip("sqlalchemy")
from app.services.scan import build_sample_query


def test_build_sample_query_valid():
    query = build_sample_query("public", "orders", ["id"])
    assert query == "SELECT * FROM public.orders ORDER BY id LIMIT :limit"


def test_build_sample_query_invalid():
    query = build_sample_query("public;drop", "orders", ["id"])
    assert query is None
