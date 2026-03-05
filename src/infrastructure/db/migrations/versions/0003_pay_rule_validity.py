# infrastructure/db/migrations/versions/0003_pay_rule_validity.py
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_pay_rule_validity"
down_revision = "0002_pay_rule_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite: non-null columns require a default when added.
    op.add_column(
        "pay_rule",
        sa.Column("valid_from", sa.Date(), nullable=False, server_default="1900-01-01"),
    )
    op.add_column("pay_rule", sa.Column("valid_to", sa.Date(), nullable=True))


def downgrade() -> None:
    # Best-effort: SQLite doesn't support DROP COLUMN in older versions; keep columns.
    pass
