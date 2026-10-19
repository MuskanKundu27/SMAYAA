import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAt, UuidPk


class Role(Base):
    """A named bundle of permissions. Seeded by migration; custom roles can be added later.

    rank: users may only create/deactivate users whose role rank is lower than their own.
    scope: where an assignment of this role applies - "platform", "company" or "plant".
    """

    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("scope IN ('platform', 'company', 'plant')", name="scope_valid"),
    )

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    rank: Mapped[int] = mapped_column(Integer)
    scope: Mapped[str] = mapped_column(String(20))


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_key: Mapped[str] = mapped_column(ForeignKey("roles.key"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(100), primary_key=True)


class User(Base):
    """A person who can log in. company_id is NULL only for platform (super admin) users."""

    __tablename__ = "users"

    id: Mapped[UuidPk]
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"), index=True)
    # Stored lower-case so "Manager1" and "manager1" cannot both exist.
    username: Mapped[str] = mapped_column(String(100), unique=True)
    full_name: Mapped[str] = mapped_column(String(200), server_default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[CreatedAt]
    deactivated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoleAssignment(Base):
    """Gives a user a role within a scope. Plant-scoped roles have plant_id; company-scoped
    roles have company_id only; the platform role has neither."""

    __tablename__ = "role_assignments"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "role_key", "company_id", "plant_id", name="uq_role_assignment"
        ),
        CheckConstraint("plant_id IS NULL OR company_id IS NOT NULL", name="plant_needs_company"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role_key: Mapped[str] = mapped_column(ForeignKey("roles.key"))
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"), index=True)
    plant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plants.id"), index=True)
    created_at: Mapped[CreatedAt]


class OperatorProfile(Base):
    """What an operator may see and do at one plant. NULL lists mean "everything"."""

    __tablename__ = "operator_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id"), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    visible_modules: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)))
    visible_parameters: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)))
    can_edit_readings: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    show_alerts: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class RefreshToken(Base):
    """Only a SHA-256 hash of the token is stored. family_id links a chain of rotated tokens,
    so reuse of an old token can revoke the whole chain."""

    __tablename__ = "refresh_tokens"

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
