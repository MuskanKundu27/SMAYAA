import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel

USERNAME_PATTERN = r"^[A-Za-z0-9._-]{3,50}$"


class NewUserFields(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN, description="3-50 letters, digits, . _ -")
    full_name: str = Field(default="", max_length=200)
    password: str = Field(min_length=1, max_length=200)


class UserCreate(NewUserFields):
    role: str = Field(description="Role key, e.g. manager or operator")
    plant_id: uuid.UUID | None = Field(default=None, description="Required for plant roles")
    company_id: uuid.UUID | None = Field(
        default=None, description="Only for the super admin creating a company admin"
    )


class UserOut(ApiModel):
    id: uuid.UUID
    username: str
    full_name: str
    is_active: bool
    company_id: uuid.UUID | None
    roles: list[str]
    plant_ids: list[uuid.UUID]
    created_at: datetime
    deactivated_at: datetime | None


class DeactivateResponse(BaseModel):
    user: UserOut
    warnings: list[str]
