"""Testes do módulo de segurança."""
import pytest

pytest.importorskip("cryptography")
from app.infrastructure.security import EncryptionError, encrypt_secret
from app.core.config import settings


def test_invalid_encryption_key():
    # Deve falhar com chave inválida.
    original = settings.app_encryption_key
    settings.app_encryption_key = "invalid"
    with pytest.raises(EncryptionError):
        encrypt_secret("secret")
    settings.app_encryption_key = original
