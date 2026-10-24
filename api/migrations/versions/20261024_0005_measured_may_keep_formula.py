"""A measured (input) parameter may keep its formula, so a company can switch it between
measured and calculated (e.g. filter dP from a transmitter, or fan power from V, I and PF).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_parameters_formula_iff_calculated"), "parameters", type_="check")
    op.create_check_constraint(
        op.f("ck_parameters_calculated_has_formula"),
        "parameters",
        "kind <> 'calculated' OR formula IS NOT NULL",
    )


def downgrade() -> None:
    # Measured parameters lose their kept formula before the stricter rule comes back.
    op.execute("UPDATE parameters SET formula = NULL WHERE kind = 'input'")
    op.drop_constraint(op.f("ck_parameters_calculated_has_formula"), "parameters", type_="check")
    op.create_check_constraint(
        op.f("ck_parameters_formula_iff_calculated"),
        "parameters",
        "(kind = 'calculated') = (formula IS NOT NULL)",
    )
