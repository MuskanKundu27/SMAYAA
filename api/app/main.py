from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware
from app.routers import (
    audit,
    auth,
    companies,
    config,
    health,
    limits,
    operator_profiles,
    plants,
    readings,
    users,
)

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="SMAYAA.ai API",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # refresh token travels in an httpOnly cookie
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    v1 = APIRouter(prefix=API_PREFIX)
    for module in (
        health, auth, companies, plants, users, config, limits, readings, operator_profiles, audit,
    ):  # fmt: skip
        v1.include_router(module.router)
    app.include_router(v1)
    return app


app = create_app()
