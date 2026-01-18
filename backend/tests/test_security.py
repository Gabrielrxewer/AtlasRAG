import pytest

pytest.importorskip("cryptography")
from app.security import EncryptionError, encrypt_secret
from app.config import settings


def test_invalid_encryption_key():
    original = settings.app_encryption_key
    settings.app_encryption_key = "invalid"
    with pytest.raises(EncryptionError):
        encrypt_secret("secret")
    settings.app_encryption_key = original
