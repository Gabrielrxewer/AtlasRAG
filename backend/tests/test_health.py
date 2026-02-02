"""Teste simples do endpoint de saúde."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    # Valida que o endpoint /health responde com status ok.
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
