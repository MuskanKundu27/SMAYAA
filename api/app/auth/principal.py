import uuid
from dataclasses import dataclass

from app.core.errors import PermissionDeniedError
from app.db.tenant import ALL_PLANTS, TenantContext
from app.models import User


@dataclass(frozen=True)
class Principal:
    """The authenticated user of the current request: identity, scope and permissions.

    Built from the database on every request (never from client input). Code asks
    `principal.has("plants.manage")`, never "is this a manager?".
    """

    user: User
    role_keys: frozenset[str]
    rank: int
    permissions: frozenset[str]
    company_id: uuid.UUID | None
    # None = every plant of the company (company-wide role); otherwise the assigned plants.
    plant_ids: frozenset[uuid.UUID] | None
    is_platform: bool

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, permission: str) -> None:
        if permission not in self.permissions:
            raise PermissionDeniedError("You do not have permission to do this.")

    def can_see_plant(self, plant_id: uuid.UUID) -> bool:
        if self.company_id is None:
            return False
        return self.plant_ids is None or plant_id in self.plant_ids

    def tenant_context(self) -> TenantContext:
        if self.is_platform:
            return TenantContext(user_id=self.user_id, platform=True)
        plants = ALL_PLANTS if self.plant_ids is None else tuple(sorted(self.plant_ids))
        return TenantContext(user_id=self.user_id, company_id=self.company_id, plant_ids=plants)
