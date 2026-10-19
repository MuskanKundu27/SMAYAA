"""Login, token refresh, logout, and building the Principal for each request."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.auth.provider import AuthProvider, PasswordAuthProvider
from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
)
from app.db.tenant import TenantContext, set_tenant_context
from app.models import Company, RefreshToken, Role, RoleAssignment, RolePermission, User

logger = logging.getLogger(__name__)

# One message for every login failure, so attackers learn nothing about which part was wrong.
BAD_CREDENTIALS = "Incorrect username or password."
SESSION_EXPIRED = "Your session has expired. Please log in again."


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    expires_in: int  # seconds
    refresh_token: str


def _now() -> datetime:
    return datetime.now(UTC)


def _find_identity(
    db: Session, *, username: str | None = None, user_id: uuid.UUID | None = None
) -> tuple[uuid.UUID, uuid.UUID | None] | None:
    """(user_id, company_id) via the auth_find_user() SECURITY DEFINER function - the only
    lookup allowed before the tenant is known."""
    row = db.execute(
        text("SELECT id, company_id FROM auth_find_user(:username, :user_id)"),
        {"username": username, "user_id": user_id},
    ).first()
    return (row.id, row.company_id) if row else None


def _enter_user_scope(db: Session, user_id: uuid.UUID, company_id: uuid.UUID | None) -> User:
    """Narrow the session to this user's own row and company, then load the user."""
    set_tenant_context(db, TenantContext(user_id=user_id, company_id=company_id))
    user = db.get(User, user_id)
    if user is None:  # deleted between lookup and load; treat as unknown
        raise UnauthorizedError(BAD_CREDENTIALS)
    return user


def _account_usable(db: Session, user: User) -> bool:
    if not user.is_active:
        return False
    if user.company_id is not None:
        company = db.get(Company, user.company_id)
        if company is None or not company.is_active:
            return False
    return True


def _issue_tokens(db: Session, user: User, family_id: uuid.UUID | None = None) -> IssuedTokens:
    settings = get_settings()
    raw_refresh = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=_now() + timedelta(days=settings.refresh_token_days),
        )
    )
    return IssuedTokens(
        access_token=create_access_token(user.id, user.company_id),
        expires_in=settings.access_token_minutes * 60,
        refresh_token=raw_refresh,
    )


def login(
    db: Session, username: str, password: str, provider: AuthProvider | None = None
) -> IssuedTokens:
    provider = provider or PasswordAuthProvider()
    settings = get_settings()

    identity = _find_identity(db, username=username.strip().lower())
    if identity is None:
        burn_password_check(password)
        raise UnauthorizedError(BAD_CREDENTIALS)

    user = _enter_user_scope(db, *identity)
    if user.locked_until and user.locked_until > _now():
        raise UnauthorizedError(
            "Too many failed attempts. This account is locked for a few minutes."
        )

    if not provider.verify(user, password):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.login_max_failures:
            user.locked_until = _now() + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_count = 0
            logger.warning("account locked", extra={"fields": {"user_id": str(user.id)}})
        db.commit()
        raise UnauthorizedError(BAD_CREDENTIALS)

    # Checked only after the password is right, so inactive accounts are not revealed.
    if not _account_usable(db, user):
        raise UnauthorizedError(BAD_CREDENTIALS)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = _now()
    tokens = _issue_tokens(db, user)
    db.commit()
    logger.info("login", extra={"fields": {"user_id": str(user.id)}})
    return tokens


def refresh(db: Session, raw_refresh: str) -> IssuedTokens:
    token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_refresh))
    )
    if token is None:
        raise UnauthorizedError(SESSION_EXPIRED)

    if token.revoked_at is not None:
        # A token that was already used is being used again: it was probably stolen.
        # Revoke the whole chain so neither the thief nor the victim can continue.
        revoke_family(db, token.family_id)
        db.commit()
        logger.warning(
            "refresh token reuse detected", extra={"fields": {"user_id": str(token.user_id)}}
        )
        raise UnauthorizedError(SESSION_EXPIRED)

    if token.expires_at <= _now():
        raise UnauthorizedError(SESSION_EXPIRED)

    token.revoked_at = _now()
    identity = _find_identity(db, user_id=token.user_id)
    if identity is None:
        raise UnauthorizedError(SESSION_EXPIRED)
    user = _enter_user_scope(db, *identity)
    if not _account_usable(db, user):
        db.commit()
        raise UnauthorizedError(SESSION_EXPIRED)

    tokens = _issue_tokens(db, user, family_id=token.family_id)
    db.commit()
    return tokens


def logout(db: Session, raw_refresh: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(raw_refresh),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=_now())
    )
    db.commit()


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def revoke_all_for_user(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def load_principal(db: Session, user_id: uuid.UUID, company_id: uuid.UUID | None) -> Principal:
    """Build the Principal from the database and narrow the session to its scope.

    Runs on every authenticated request, so a deactivated user (or company) is locked out
    immediately, even while their access token has not expired yet.
    """
    # Until roles are known, the session may only see this user's own row and company.
    set_tenant_context(db, TenantContext(user_id=user_id, company_id=company_id))
    user = db.get(User, user_id)
    if user is None or user.company_id != company_id or not _account_usable(db, user):
        raise UnauthorizedError(SESSION_EXPIRED)

    rows = db.execute(
        select(RoleAssignment, Role)
        .join(Role, Role.key == RoleAssignment.role_key)
        .where(RoleAssignment.user_id == user.id)
    ).all()
    if not rows:
        raise UnauthorizedError("This account has no role assigned.")

    role_keys = frozenset(role.key for _, role in rows)
    permissions = frozenset(
        db.scalars(select(RolePermission.permission).where(RolePermission.role_key.in_(role_keys)))
    )
    scopes = {role.scope for _, role in rows}
    plant_ids = (
        None
        if "company" in scopes
        else frozenset(a.plant_id for a, _ in rows if a.plant_id is not None)
    )
    principal = Principal(
        user=user,
        role_keys=role_keys,
        rank=max(role.rank for _, role in rows),
        permissions=permissions,
        company_id=user.company_id,
        plant_ids=plant_ids,
        is_platform="platform" in scopes,
    )
    set_tenant_context(db, principal.tenant_context())
    return principal
