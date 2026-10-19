"""Company A must never see or change company B's data: through the API (application layer)
and directly in SQL (row-level security layer)."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.db.tenant import ALL_PLANTS, TenantContext, set_tenant_context
from tests.helpers import login, make_tenant

# --- Through the API ------------------------------------------------------------------------


def test_company_admin_sees_only_own_plants(client: TestClient, owner_db: Session) -> None:
    make_tenant(owner_db, "acme")
    make_tenant(owner_db, "beta")

    response = client.get("/api/v1/plants", headers=login(client, "acme-admin"))

    assert {p["name"] for p in response.json()["items"]} == {"Acme Plant A", "Acme Plant B"}


def test_cannot_rename_another_companys_plant(client: TestClient, owner_db: Session) -> None:
    beta = make_tenant(owner_db, "beta")
    make_tenant(owner_db, "acme")

    response = client.patch(
        f"/api/v1/plants/{beta.plant_a.id}", json={"name": "Hacked"},
        headers=login(client, "acme-admin"),
    )  # fmt: skip

    assert response.status_code == 404


def test_cannot_create_a_user_in_another_companys_plant(
    client: TestClient, owner_db: Session
) -> None:
    beta = make_tenant(owner_db, "beta")
    make_tenant(owner_db, "acme")
    body = {
        "username": "intruder", "password": "Intruder-pass-1", "role": "operator",
        "plant_id": str(beta.plant_a.id),
    }  # fmt: skip

    response = client.post("/api/v1/users", json=body, headers=login(client, "acme-admin"))

    assert response.status_code == 404


def test_cannot_deactivate_another_companys_user(client: TestClient, owner_db: Session) -> None:
    beta = make_tenant(owner_db, "beta")
    make_tenant(owner_db, "acme")

    response = client.delete(
        f"/api/v1/users/{beta.operator.id}", headers=login(client, "acme-admin")
    )

    assert response.status_code == 404


def test_company_admin_cannot_attach_a_user_to_another_company(
    client: TestClient, owner_db: Session
) -> None:
    beta = make_tenant(owner_db, "beta")
    make_tenant(owner_db, "acme")
    body = {
        "username": "intruder", "password": "Intruder-pass-1", "role": "manager",
        "plant_id": str(beta.plant_a.id), "company_id": str(beta.company_id),
    }  # fmt: skip

    response = client.post("/api/v1/users", json=body, headers=login(client, "acme-admin"))

    assert response.status_code == 404


# --- Directly in the database (RLS) ---------------------------------------------------------


def _visible(app_engine: Engine, context: TenantContext | None, sql: str) -> list[str]:
    """Run raw SQL as the runtime role with the given tenant context (None = none set)."""
    with Session(app_engine) as session:
        if context is not None:
            set_tenant_context(session, context)
        return [str(v) for v in session.execute(text(sql)).scalars()]


def test_without_tenant_context_the_database_returns_nothing(
    app_engine: Engine, owner_db: Session
) -> None:
    make_tenant(owner_db, "acme")

    for table in ("companies", "plants", "users", "role_assignments", "audit_log"):
        assert _visible(app_engine, None, f"SELECT id FROM {table}") == [], table  # noqa: S608


def test_rls_limits_rows_to_the_current_company(app_engine: Engine, owner_db: Session) -> None:
    acme = make_tenant(owner_db, "acme")
    make_tenant(owner_db, "beta")
    context = TenantContext(user_id=acme.admin.id, company_id=acme.company_id, plant_ids=ALL_PLANTS)

    assert _visible(app_engine, context, "SELECT name FROM companies") == ["Acme Ltd"]
    assert sorted(_visible(app_engine, context, "SELECT name FROM plants")) == [
        "Acme Plant A",
        "Acme Plant B",
    ]
    users = _visible(app_engine, context, "SELECT username FROM users")
    assert sorted(users) == ["acme-admin", "acme-manager", "acme-operator"]


def test_rls_limits_plants_to_assigned_plants(app_engine: Engine, owner_db: Session) -> None:
    acme = make_tenant(owner_db, "acme")
    context = TenantContext(
        user_id=acme.manager.id, company_id=acme.company_id, plant_ids=(acme.plant_a.id,)
    )

    assert _visible(app_engine, context, "SELECT name FROM plants") == ["Acme Plant A"]


def test_rls_blocks_writing_rows_for_another_company(app_engine: Engine, owner_db: Session) -> None:
    acme = make_tenant(owner_db, "acme")
    beta = make_tenant(owner_db, "beta")
    context = TenantContext(user_id=acme.admin.id, company_id=acme.company_id, plant_ids=ALL_PLANTS)

    with Session(app_engine) as session:
        set_tenant_context(session, context)
        updated = session.execute(
            text("UPDATE plants SET name = 'Hacked' WHERE company_id = :cid"),
            {"cid": beta.company_id},
        ).rowcount  # type: ignore[attr-defined]
        session.commit()
    assert updated == 0


def test_rls_forged_company_id_cannot_insert_into_another_company(
    app_engine: Engine, owner_db: Session
) -> None:
    acme = make_tenant(owner_db, "acme")
    beta = make_tenant(owner_db, "beta")
    context = TenantContext(user_id=acme.admin.id, company_id=acme.company_id, plant_ids=ALL_PLANTS)

    with Session(app_engine) as session:
        set_tenant_context(session, context)
        try:
            session.execute(
                text("INSERT INTO plants (company_id, name) VALUES (:cid, 'Planted')"),
                {"cid": beta.company_id},
            )
            session.commit()
            inserted = True
        except Exception as exc:  # psycopg raises InsufficientPrivilege for RLS violations
            assert "row-level security" in str(exc)
            inserted = False
    assert inserted is False


def test_platform_context_sees_companies_but_never_has_a_tenant(
    app_engine: Engine, owner_db: Session
) -> None:
    make_tenant(owner_db, "acme")
    make_tenant(owner_db, "beta")
    context = TenantContext(user_id=uuid.uuid4(), platform=True)

    assert sorted(_visible(app_engine, context, "SELECT name FROM companies")) == [
        "Acme Ltd",
        "Beta Ltd",
    ]


def test_context_survives_commit_within_a_session(app_engine: Engine, owner_db: Session) -> None:
    acme = make_tenant(owner_db, "acme")
    context = TenantContext(user_id=acme.admin.id, company_id=acme.company_id, plant_ids=ALL_PLANTS)

    with Session(app_engine) as session:
        set_tenant_context(session, context)
        session.execute(text("SELECT 1"))
        session.commit()  # new transaction begins below; context must be re-applied
        names = session.execute(text("SELECT name FROM companies")).scalars().all()
    assert names == ["Acme Ltd"]
