"""Builders for test data (written as the owner role, so RLS does not get in the way)."""

import uuid
from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Company, Plant, RoleAssignment, User

PASSWORD = "Secret-pass-123"


def make_company(db: Session, name: str = "Acme Cooling Ltd") -> Company:
    company = Company(name=name)
    db.add(company)
    db.commit()
    return company


def make_plant(db: Session, company: Company, name: str = "Plant 1") -> Plant:
    plant = Plant(company_id=company.id, name=name, location="Delhi")
    db.add(plant)
    db.commit()
    return plant


def make_user(
    db: Session,
    username: str,
    role: str,
    company: Company | None = None,
    plant: Plant | None = None,
    *,
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        full_name=username.title(),
        password_hash=hash_password(PASSWORD),
        company_id=company.id if company else None,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    db.add(
        RoleAssignment(
            user_id=user.id,
            role_key=role,
            company_id=company.id if company else None,
            plant_id=plant.id if plant else None,
        )
    )
    db.commit()
    return user


def login(client: TestClient, username: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@dataclass
class Tenant:
    """A company with two plants and one user per role (manager/operator at plant_a)."""

    company: Company
    plant_a: Plant
    plant_b: Plant
    admin: User
    manager: User
    operator: User

    @property
    def company_id(self) -> uuid.UUID:
        return self.company.id


def make_tenant(db: Session, prefix: str) -> Tenant:
    company = make_company(db, f"{prefix.title()} Ltd")
    plant_a = make_plant(db, company, f"{prefix.title()} Plant A")
    plant_b = make_plant(db, company, f"{prefix.title()} Plant B")
    return Tenant(
        company=company,
        plant_a=plant_a,
        plant_b=plant_b,
        admin=make_user(db, f"{prefix}-admin", "company_admin", company),
        manager=make_user(db, f"{prefix}-manager", "manager", company, plant_a),
        operator=make_user(db, f"{prefix}-operator", "operator", company, plant_a),
    )
