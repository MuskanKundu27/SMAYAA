import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel
from app.schemas.users import NewUserFields, UserOut


class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    admin: NewUserFields = Field(description="The company's first company admin")


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    is_active: bool | None = None


class CompanyOut(ApiModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime


class CompanyCreated(BaseModel):
    company: CompanyOut
    admin: UserOut


class PlantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    location: str = Field(default="", max_length=200)


class PlantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class PlantOut(ApiModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    location: str
    is_active: bool
    created_at: datetime
