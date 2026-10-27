"""Predicted-problem rules get a priority, an expected-benefit text and an optional ETA
expression (hours until the problem is expected), for the predicted-problems and
recommended-actions tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rules", sa.Column("priority", sa.String(10), server_default="medium", nullable=False)
    )
    op.add_column("rules", sa.Column("benefit_text", sa.Text(), server_default="", nullable=False))
    op.add_column("rules", sa.Column("eta_expr", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_rules_priority_valid"), "rules", "priority IN ('high', 'medium', 'low')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_rules_priority_valid"), "rules", type_="check")
    op.drop_column("rules", "eta_expr")
    op.drop_column("rules", "benefit_text")
    op.drop_column("rules", "priority")
