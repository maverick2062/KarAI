"""Auth, password hashing, field-level encryption, and rate limiting helpers.

Encryption note: this uses AES-256-GCM with a key derived from the
ENCRYPTION_KEY env var via SHA-256 (so any passphrase length works), stored
alongside a random nonce, base64-encoded in the database column. This is
prototype-grade key management — a single symmetric key from an environment
variable. Production deployments need a KMS/HSM-backed key with rotation,
not a static .env secret.
"""

import base64
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

# --- Password hashing (bcrypt, cost factor 12) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# --- JWT ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.jwt_expiry_hours)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# NOTE: the get_current_user FastAPI dependency lives in app.routers.deps,
# not here — it needs the User model, and importing models here would create
# a circular import (models -> security for field encryption -> models).


# --- Rate limiting: 100 requests/minute per authenticated user (falls back to IP) ---
def _rate_limit_key(request) -> str:
    # Decode the bearer token directly here (rather than reading
    # request.state.user_id) because SlowAPIMiddleware evaluates this key
    # BEFORE FastAPI resolves route dependencies — get_current_user hasn't
    # run yet at this point, so state alone would always look anonymous.
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            return f"user:{payload['sub']}"
        except (JWTError, KeyError):
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_limit_key, default_limits=[f"{settings.rate_limit_per_minute}/minute"])


# --- Field-level encryption (AES-256-GCM) ---
def _derive_key() -> bytes:
    return hashlib.sha256(settings.encryption_key.encode("utf-8")).digest()


def encrypt_field(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    key = _derive_key()
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(stored_value: str | None) -> str | None:
    if stored_value is None:
        return None
    key = _derive_key()
    raw = base64.b64decode(stored_value.encode("ascii"))
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
