"""Application-level encryption (identifier columns, KYC files) and KYC case tokens."""

import hashlib
import hmac
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


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet().decrypt(token)


def scoped_token(scope: str, obj_id: int) -> str:
    """HMAC capability token for one object. Never stored; re-derived to verify.

    Without these, sequential ids would let anyone read anyone's quote, KYC or
    order (IDOR). Signed with JWT_SECRET.
    """
    secret = get_settings().jwt_secret.encode()
    sig = hmac.new(secret, f"{scope}:{obj_id}".encode(), hashlib.sha256).hexdigest()[:40]
    return f"{obj_id}.{sig}"


def verify_scoped_token(scope: str, obj_id: int, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(scoped_token(scope, obj_id), token)


def kyc_token(business_id: int) -> str:
    """Owner token for a business: quotes, checkout, KYC and order tracking.
    Stands in for OTP login (JWT) until that lands."""
    return scoped_token("kyc", business_id)


def verify_kyc_token(business_id: int, token: str | None) -> bool:
    return verify_scoped_token("kyc", business_id, token)


def quote_share_token(quote_id: int) -> str:
    """Read-only link to one quote, safe to forward to a partner or accountant."""
    return scoped_token("quote", quote_id)


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


# --- console accounts ----------------------------------------------------------

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password: str) -> str:
    import base64
    import os

    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    import base64

    try:
        scheme, salt_b64, digest_b64 = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


def console_jwt(user_id: int, username: str, role: str, city: str | None) -> str:
    from datetime import UTC, datetime, timedelta

    import jwt

    s = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "usr": username,
        "role": role,
        "city": city,
        "aud": "udyam-console",
        "iat": now,
        "exp": now + timedelta(minutes=s.console_token_minutes),
    }
    return jwt.encode(claims, s.jwt_secret, algorithm="HS256")


def decode_console_jwt(token: str) -> dict | None:
    import jwt

    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"], audience="udyam-console")
    except jwt.PyJWTError:
        return None
