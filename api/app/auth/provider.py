"""How a user proves who they are.

Login code depends only on the AuthProvider protocol, so SSO (OIDC/SAML) can be added later
as another provider without touching permissions or tenancy.
"""

from typing import Protocol

from app.core.security import hash_password, password_needs_rehash, verify_password
from app.models import User


class AuthProvider(Protocol):
    def verify(self, user: User, secret: str) -> bool:
        """Return True if `secret` proves the identity of `user`."""
        ...


class PasswordAuthProvider:
    def verify(self, user: User, secret: str) -> bool:
        if not verify_password(user.password_hash, secret):
            return False
        if password_needs_rehash(user.password_hash):
            # Hashing parameters were strengthened since this hash was made; upgrade it now.
            user.password_hash = hash_password(secret)
        return True
