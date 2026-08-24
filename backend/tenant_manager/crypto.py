from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    key = settings.CREDENTIAL_ENCRYPTION_KEY
    if not key:
        raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY is not configured")
    return Fernet(key)


def encrypt_secret(raw: str) -> bytes:
    return _fernet().encrypt(raw.encode())


def decrypt_secret(token: bytes) -> str:
    return _fernet().decrypt(bytes(token)).decode()
