import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import ConflictError, NotFoundError
from app.models import Company, Role, User
from app.schemas.common import PageParams
from app.schemas.tenancy import CompanyCreate, CompanyUpdate
from app.services import audit
from app.services.users import create_user_record

COMPANY_FIELDS = ["name", "is_active"]

# Every new company gets one first admin with this role. This is the only place a role key is
# named in code, because "the role that owns a company" is part of the product definition.
COMPANY_OWNER_ROLE = "company_admin"


def list_companies(
    db: Session, principal: Principal, page: PageParams
) -> tuple[list[Company], int]:
    principal.require("companies.read")
    total = db.scalar(select(func.count()).select_from(Company)) or 0
    companies = db.scalars(
        select(Company).order_by(Company.name).limit(page.limit).offset(page.offset)
    ).all()
    return list(companies), total


def _ensure_name_free(db: Session, name: str, exclude: uuid.UUID | None = None) -> None:
    query = select(Company.id).where(func.lower(Company.name) == name.lower())
    if exclude:
        query = query.where(Company.id != exclude)
    if db.scalar(query) is not None:
        raise ConflictError(f"A company named '{name}' already exists.")


def create_company(db: Session, principal: Principal, data: CompanyCreate) -> tuple[Company, User]:
    principal.require("companies.manage")
    principal.require(f"users.manage:{COMPANY_OWNER_ROLE}")
    _ensure_name_free(db, data.name)

    company = Company(name=data.name)
    db.add(company)
    db.flush()
    audit.record(
        db, principal, "company.create", "company", company.id,
        company_id=company.id, after=audit.snapshot(company, COMPANY_FIELDS),
    )  # fmt: skip

    role = db.get(Role, COMPANY_OWNER_ROLE)
    if role is None:  # the migration seeds it; missing means a broken database
        raise RuntimeError(f"Role '{COMPANY_OWNER_ROLE}' is missing")
    admin = create_user_record(
        db, principal, username=data.admin.username, full_name=data.admin.full_name,
        password=data.admin.password, role=role, company_id=company.id, plant_id=None,
    )  # fmt: skip
    db.commit()
    return company, admin


def update_company(
    db: Session, principal: Principal, company_id: uuid.UUID, data: CompanyUpdate
) -> Company:
    principal.require("companies.manage")
    company = db.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company not found.")
    before = audit.snapshot(company, COMPANY_FIELDS)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != company.name:
        _ensure_name_free(db, changes["name"], exclude=company.id)
    for field, value in changes.items():
        setattr(company, field, value)
    audit.record(
        db, principal, "company.update", "company", company.id,
        company_id=company.id, before=before, after=audit.snapshot(company, COMPANY_FIELDS),
    )  # fmt: skip
    db.commit()
    return company
