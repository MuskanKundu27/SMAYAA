"""FastAPI dependencies: the single place where every request resolves identity, scope and
permission. Routers use `CurrentPrincipal` or `require(...)`; they never read company or plant
ids from the client to decide access."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import UnauthorizedError
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.services import auth as auth_service

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_principal(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise UnauthorizedError("Please log in.")
    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise UnauthorizedError(auth_service.SESSION_EXPIRED) from exc
    return auth_service.load_principal(db, claims.user_id, claims.company_id)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require(permission: str) -> Callable[[Principal], Principal]:
    """Dependency factory: `principal: Annotated[Principal, Depends(require("plants.manage"))]`."""

    def check(principal: CurrentPrincipal) -> Principal:
        principal.require(permission)
        return principal

    return check
