import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class EncryptionError(RuntimeError):
    pass


def _decode_secret_bytes(raw: bytes) -> str:
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1252", errors="strict")
        except UnicodeDecodeError:
            try:
                return raw.decode("latin-1", errors="strict")
            except UnicodeDecodeError:
                return raw.decode("utf-8", errors="replace")


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = (settings.app_encryption_key or "").strip()
    if not key:
        raise EncryptionError("APP_ENCRYPTION_KEY is required")
    key_bytes = key.encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(key_bytes)
    except Exception as exc:
        raise EncryptionError("APP_ENCRYPTION_KEY must be a valid Fernet key") from exc
    if len(decoded) != 32:
        raise EncryptionError("APP_ENCRYPTION_KEY must be a 32-byte urlsafe base64 value")
    return Fernet(key_bytes)


def encrypt_secret(value: str) -> str:
    fernet = _get_fernet()
    token = fernet.encrypt((value or "").encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(value: str) -> str:
    fernet = _get_fernet()
    if not value:
        return ""
    try:
        raw = fernet.decrypt(value.encode("utf-8"))
    except InvalidToken as exc:
        raise EncryptionError("Invalid encrypted secret") from exc
    return _decode_secret_bytes(raw)
