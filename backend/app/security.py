import base64
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class EncryptionError(RuntimeError):
    pass


def _get_fernet() -> Fernet:
    if not settings.app_encryption_key:
        raise EncryptionError("APP_ENCRYPTION_KEY is required")
    key_bytes = settings.app_encryption_key.encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(key_bytes)
    except Exception as exc:
        raise EncryptionError("APP_ENCRYPTION_KEY must be a valid Fernet key") from exc
    if len(decoded) != 32:
        raise EncryptionError("APP_ENCRYPTION_KEY must be a 32-byte urlsafe base64 value")
    return Fernet(key_bytes)


def encrypt_secret(value: str) -> str:
    fernet = _get_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    fernet = _get_fernet()
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError("Invalid encrypted secret") from exc
