import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105  (OAuth2 token type, not a secret)
    expires_in: int


class MeCompany(ApiModel):
    id: uuid.UUID
    name: str


class MePlant(ApiModel):
    id: uuid.UUID
    name: str
    location: str


class MeResponse(BaseModel):
    """Who is logged in and what they may do. The frontend builds its menu from this."""

    id: uuid.UUID
    username: str
    full_name: str
    roles: list[str]
    permissions: list[str]
    company: MeCompany | None
    plants: list[MePlant]
