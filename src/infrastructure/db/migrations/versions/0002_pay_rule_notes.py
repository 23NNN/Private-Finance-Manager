# infrastructure/db/migrations/versions/0002_pay_rule_notes.py
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_pay_rule_notes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pay_rule", sa.Column("notes", sa.Text(), nullable=True))

    # Best-effort rule-type normalization (legacy -> new)
    op.execute(
        """
        UPDATE pay_rule
        SET rule_type = 'HOURLY_WAGE'
        WHERE rule_type IN ('BASE', 'BASE_BW', 'BASE_BY');
        """
    )
    op.execute(
        """
        UPDATE pay_rule
        SET rule_type = 'NIGHT'
        WHERE rule_type IN ('NIGHT_BW', 'NIGHT_BY');
        """
    )
    op.execute(
        """
        UPDATE pay_rule
        SET rule_type = 'SUNDAY'
        WHERE rule_type IN ('SUNDAY_BW', 'SUNDAY_BY');
        """
    )


def downgrade() -> None:
    # SQLite: drop column not supported in a simple way -> no-op
    pass
