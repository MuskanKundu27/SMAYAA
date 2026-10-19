from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status
from sqlalchemy import select

from app.auth.dependencies import CurrentPrincipal, DbSession
from app.core.config import get_settings
from app.core.errors import TooManyRequestsError, UnauthorizedError
from app.core.rate_limit import SlidingWindowLimiter
from app.models import Company, Plant
from app.schemas.auth import LoginRequest, MeCompany, MePlant, MeResponse, TokenResponse
from app.services import auth as auth_service
from app.services.auth import IssuedTokens

router = APIRouter(tags=["auth"])

REFRESH_COOKIE = "smayaa_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"  # the browser sends the cookie only to auth endpoints


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,  # JavaScript cannot read it, so XSS cannot steal it
        secure=settings.is_production,  # HTTPS only in production; local dev is plain HTTP
        samesite="strict",
    )


def _token_response(response: Response, tokens: IssuedTokens) -> TokenResponse:
    _set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


def _login_limiter(request: Request) -> SlidingWindowLimiter:
    limiter: SlidingWindowLimiter | None = getattr(request.app.state, "login_limiter", None)
    if limiter is None:
        limiter = SlidingWindowLimiter(get_settings().login_rate_limit_per_minute, 60)
        request.app.state.login_limiter = limiter
    return limiter


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _login_limiter(request).allow(client_ip):
        raise TooManyRequestsError("Too many login attempts. Please wait a minute.")
    return _token_response(response, auth_service.login(db, body.username, body.password))


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenResponse:
    if not refresh_token:
        raise UnauthorizedError(auth_service.SESSION_EXPIRED)
    return _token_response(response, auth_service.refresh(db, refresh_token))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> None:
    if refresh_token:
        auth_service.logout(db, refresh_token)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=MeResponse)
def me(principal: CurrentPrincipal, db: DbSession) -> MeResponse:
    company = db.get(Company, principal.company_id) if principal.company_id else None
    plants: list[Plant] = []
    if company is not None:
        # RLS limits this to the plants the user may see.
        plants = list(
            db.scalars(
                select(Plant)
                .where(Plant.company_id == company.id, Plant.is_active.is_(True))
                .order_by(Plant.name)
            )
        )
    return MeResponse(
        id=principal.user.id,
        username=principal.user.username,
        full_name=principal.user.full_name,
        roles=sorted(principal.role_keys),
        permissions=sorted(principal.permissions),
        company=MeCompany.model_validate(company) if company else None,
        plants=[MePlant.model_validate(p) for p in plants if principal.can_see_plant(p.id)],
    )
