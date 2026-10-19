from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.helpers import PASSWORD, login, make_company, make_user

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"


def test_login_returns_access_token_and_refresh_cookie(
    client: TestClient, owner_db: Session
) -> None:
    make_user(owner_db, "alice", "company_admin", make_company(owner_db))

    response = client.post(LOGIN, json={"username": "alice", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    cookie = response.headers["set-cookie"]
    assert "smayaa_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/api/v1/auth" in cookie


def test_username_is_case_insensitive(client: TestClient, owner_db: Session) -> None:
    make_user(owner_db, "alice", "company_admin", make_company(owner_db))

    assert client.post(LOGIN, json={"username": "ALICE", "password": PASSWORD}).status_code == 200


def test_wrong_password_and_unknown_user_get_the_same_answer(
    client: TestClient, owner_db: Session
) -> None:
    make_user(owner_db, "alice", "company_admin", make_company(owner_db))

    wrong = client.post(LOGIN, json={"username": "alice", "password": "nope-nope-1"})
    unknown = client.post(LOGIN, json={"username": "nobody", "password": "nope-nope-1"})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_account_locks_after_repeated_failures(client: TestClient, owner_db: Session) -> None:
    make_user(owner_db, "alice", "company_admin", make_company(owner_db))
    for _ in range(5):
        client.post(LOGIN, json={"username": "alice", "password": "wrong-pass-1"})

    response = client.post(LOGIN, json={"username": "alice", "password": PASSWORD})

    assert response.status_code == 401
    assert "locked" in response.json()["error"]["message"]


def test_login_is_rate_limited_per_client(client: TestClient, owner_db: Session) -> None:
    statuses = [
        client.post(LOGIN, json={"username": "x", "password": "y"}).status_code for _ in range(21)
    ]

    assert statuses[:20] == [401] * 20
    assert statuses[20] == 429


def test_deactivated_user_cannot_log_in(client: TestClient, owner_db: Session) -> None:
    make_user(owner_db, "alice", "company_admin", make_company(owner_db), is_active=False)

    assert client.post(LOGIN, json={"username": "alice", "password": PASSWORD}).status_code == 401


def test_users_of_a_deactivated_company_cannot_log_in(
    client: TestClient, owner_db: Session
) -> None:
    company = make_company(owner_db)
    make_user(owner_db, "alice", "company_admin", company)
    company.is_active = False
    owner_db.commit()

    assert client.post(LOGIN, json={"username": "alice", "password": PASSWORD}).status_code == 401


def test_deactivated_user_is_locked_out_even_with_a_valid_token(
    client: TestClient, owner_db: Session
) -> None:
    user = make_user(owner_db, "alice", "company_admin", make_company(owner_db))
    headers = login(client, "alice")
    assert client.get("/api/v1/me", headers=headers).status_code == 200

    owner_db.get(User, user.id).is_active = False  # type: ignore[union-attr]
    owner_db.commit()

    assert client.get("/api/v1/me", headers=headers).status_code == 401


def test_requests_without_or_with_a_bad_token_are_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/me").status_code == 401
    bad = client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401
    assert bad.headers["WWW-Authenticate"] == "Bearer"


def test_refresh_rotates_the_token(client: TestClient, owner_db: Session) -> None:
    make_user(owner_db, "alice", "company_admin", make_company(owner_db))
    login(client, "alice")
    first_cookie = client.cookies.get("smayaa_refresh")

    response = client.post(REFRESH)

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert client.cookies.get("smayaa_refresh") != first_cookie


def test_reusing_an_old_refresh_token_revokes_the_whole_session(
    client: TestClient, owner_db: Session
) -> None:
    make_user(owner_db, "alice", "company_admin", make_company(owner_db))
    login(client, "alice")
    stolen = client.cookies.get("smayaa_refresh")
    assert client.post(REFRESH).status_code == 200  # legitimate rotation
    current = client.cookies.get("smayaa_refresh")

    client.cookies.set("smayaa_refresh", stolen, path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401  # reuse detected

    client.cookies.set("smayaa_refresh", current, path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401  # the newer token was revoked too


def test_logout_revokes_the_refresh_token(client: TestClient, owner_db: Session) -> None:
    make_user(owner_db, "alice", "company_admin", make_company(owner_db))
    login(client, "alice")
    token = client.cookies.get("smayaa_refresh")

    assert client.post("/api/v1/auth/logout").status_code == 204

    client.cookies.set("smayaa_refresh", token, path="/api/v1/auth")
    assert client.post(REFRESH).status_code == 401
