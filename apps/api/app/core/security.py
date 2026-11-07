"""Application-level encryption for identifier columns (GSTIN, Udyam number)."""

from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy import String, TypeDecorator

from app.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().field_encryption_key
    if not key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


class EncryptedString(TypeDecorator):
    """Stores a string Fernet-encrypted; reads it back as plaintext."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _fernet().decrypt(value.encode()).decode()
