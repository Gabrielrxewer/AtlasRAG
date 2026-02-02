"""Testes de construção de queries de amostra."""
import pytest

pytest.importorskip("sqlalchemy")
from app.application.services.scan import build_sample_query


def test_build_sample_query_valid():
    # Deve construir query quando schema e tabela são válidos.
    query = build_sample_query("public", "orders", ["id"])
    assert query == "SELECT * FROM public.orders ORDER BY id LIMIT :limit"


def test_build_sample_query_invalid():
    # Deve recusar entradas com caracteres inválidos.
    query = build_sample_query("public;drop", "orders", ["id"])
    assert query is None
