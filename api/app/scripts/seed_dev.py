"""Create demo data for local development. Safe to run repeatedly.

    cd api && .venv/Scripts/python.exe -m app.scripts.seed_dev

Refuses to run when ENVIRONMENT=production. Connects as the schema owner (MIGRATION_DATABASE_URL)
because it creates data across tenants, which the runtime role is not allowed to do.
"""

import os
import sys

from dotenv import dotenv_values
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, Environment, get_settings
from app.core.security import hash_password
from app.models import Company, Plant, RoleAssignment, User
from app.services.templates import apply_template
from app.templates.default import DEFAULT_TEMPLATE

DEMO_PASSWORD = "Demo@12345"  # noqa: S105  (development only; meets the password policy)

COMPANY = "Demo Power Ltd"
PLANT = ("Unit 1 – Cooling Tower", "Delhi")  # noqa: RUF001  (name as given in the brief)
USERS = [
    # username, full name, role, belongs to company?, assigned to plant?
    ("smayaaadmin", "SMAYAA Platform Admin", "super_admin", False, False),
    ("companyadmin", "Demo Company Admin", "company_admin", True, False),
    ("manager1", "Demo Manager", "manager", True, True),
    ("operator1", "Demo Operator", "operator", True, True),
]


def _owner_url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL") or dotenv_values(
        REPO_ROOT / ".env", encoding="utf-8-sig"
    ).get("MIGRATION_DATABASE_URL")
    if not url:
        raise SystemExit("MIGRATION_DATABASE_URL is not set")
    return url


def seed(db: Session) -> list[str]:
    created: list[str] = []
    company = db.scalar(select(Company).where(Company.name == COMPANY))
    if company is None:
        company = Company(name=COMPANY)
        db.add(company)
        db.flush()
        created.append(f"company {COMPANY}")

    plant = db.scalar(select(Plant).where(Plant.company_id == company.id, Plant.name == PLANT[0]))
    if plant is None:
        plant = Plant(company_id=company.id, name=PLANT[0], location=PLANT[1])
        db.add(plant)
        db.flush()
        created.append(f"plant {PLANT[0]}")

    for username, full_name, role, in_company, at_plant in USERS:
        if db.scalar(select(User.id).where(User.username == username)):
            continue
        user = User(
            username=username,
            full_name=full_name,
            password_hash=hash_password(DEMO_PASSWORD),
            company_id=company.id if in_company else None,
        )
        db.add(user)
        db.flush()
        db.add(
            RoleAssignment(
                user_id=user.id,
                role_key=role,
                company_id=company.id if in_company else None,
                plant_id=plant.id if at_plant else None,
            )
        )
        created.append(f"user {username} ({role})")

    # Standard configuration (parameters, rules, modules, ...). Only adds what is missing.
    added = apply_template(db, company, DEFAULT_TEMPLATE, actor_id=None)
    if any(added.values()):
        created.append("template " + ", ".join(f"{n} {k}" for k, n in added.items() if n))
    db.commit()
    return created


def main() -> None:
    if get_settings().environment == Environment.PRODUCTION:
        sys.exit("Refusing to seed demo data: ENVIRONMENT=production")
    with Session(create_engine(_owner_url())) as db:
        created = seed(db)
    print("Created:", ", ".join(created) if created else "nothing (already seeded)")
    print(f"Demo users: {', '.join(u[0] for u in USERS)} - password {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
