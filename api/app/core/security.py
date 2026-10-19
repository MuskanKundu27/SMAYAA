"""Password hashing, access tokens (JWT) and refresh tokens."""

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Environment, get_settings

JWT_ALGORITHM = "HS256"


# --- Passwords ------------------------------------------------------------------------------


@lru_cache
def _hasher(environment: Environment) -> PasswordHasher:
    if environment == Environment.TEST:
        # Deliberately weak and fast: tests hash many passwords. Never used outside tests.
        return PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    return PasswordHasher()  # argon2id with the library's recommended parameters


def hash_password(password: str) -> str:
    return _hasher(get_settings().environment).hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher(get_settings().environment).verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher(get_settings().environment).check_needs_rehash(password_hash)


# Used when a username does not exist, so the response takes as long as a real check and
# attackers cannot tell existing usernames from the timing.
@lru_cache
def _dummy_hash(environment: Environment) -> str:
    return _hasher(environment).hash(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    verify_password(_dummy_hash(get_settings().environment), password)


PASSWORD_MIN_LENGTH = 10


def password_problems(password: str, username: str) -> list[str]:
    """Return human-readable reasons the password is not acceptable (empty list = OK)."""
    problems = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        problems.append("Password must contain at least one letter and one digit.")
    if username and username.lower() in password.lower():
        problems.append("Password must not contain the username.")
    return problems


# --- Access tokens --------------------------------------------------------------------------


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    company_id: uuid.UUID | None


class InvalidTokenError(Exception):
    pass


def create_access_token(user_id: uuid.UUID, company_id: uuid.UUID | None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "cid": str(company_id) if company_id else None,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "typ"]},
        )
        if payload["typ"] != "access":
            raise InvalidTokenError("wrong token type")
        cid = payload.get("cid")
        return AccessClaims(uuid.UUID(payload["sub"]), uuid.UUID(cid) if cid else None)
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise InvalidTokenError(str(exc)) from exc


# --- Refresh tokens -------------------------------------------------------------------------


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    # A fast hash is fine here: the token is 256 random bits, so it cannot be guessed.
    return hashlib.sha256(token.encode()).hexdigest()
