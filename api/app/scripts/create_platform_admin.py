"""Create the first platform (super) admin. Works in every environment, including production.

    cd api && .venv/bin/python -m app.scripts.create_platform_admin

Asks for the username, full name and password on the terminal (the password is never echoed,
logged or passed on the command line). Connects as the schema owner (MIGRATION_DATABASE_URL),
because no user exists yet who could be logged in to do this through the API.
"""

import getpass
import re
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, password_problems
from app.models import RoleAssignment, User
from app.schemas.users import USERNAME_PATTERN
from app.scripts.seed_dev import owner_url
from app.services.audit import record_for

ROLE = "super_admin"


def create(db: Session, username: str, full_name: str, password: str) -> User:
    username = username.lower()
    if not re.fullmatch(USERNAME_PATTERN, username):
        raise ValueError("Username must be 3-50 letters, digits, '.', '_' or '-'.")
    if db.scalar(select(User.id).where(User.username == username)):
        raise ValueError(f"Username '{username}' is already taken.")
    problems = password_problems(password, username)
    if problems:
        raise ValueError(" ".join(problems))
    user = User(username=username, full_name=full_name, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    db.add(RoleAssignment(user_id=user.id, role_key=ROLE))
    record_for(
        db, None, "create", "user", user.id,
        company_id=None, after={"username": username, "role": ROLE, "via": "cli"},
    )  # fmt: skip
    db.commit()
    return user


def main() -> None:
    username = input("Username: ").strip()
    full_name = input("Full name: ").strip() or username
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    with Session(create_engine(owner_url())) as db:
        try:
            create(db, username, full_name, password)
        except ValueError as exc:
            sys.exit(str(exc))
    print(f"Platform admin '{username}' created.")


if __name__ == "__main__":
    main()
