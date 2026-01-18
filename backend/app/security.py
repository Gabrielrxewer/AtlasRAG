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
        base64.urlsafe_b64decode(key_bytes)
        fernet_key = key_bytes
    except Exception:
        fernet_key = base64.urlsafe_b64encode(key_bytes.ljust(32, b"_"))
    return Fernet(fernet_key)


def encrypt_secret(value: str) -> str:
    fernet = _get_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    fernet = _get_fernet()
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError("Invalid encrypted secret") from exc
