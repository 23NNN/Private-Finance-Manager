# src/infrastructure/db/migrations/versions/0002_income_special_and_savings_rule_validity.py
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_income_special_and_savings_rule_validity"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("savings_rule") as b:
        b.add_column(sa.Column("valid_from", sa.Date(), nullable=False, server_default=sa.text("'1900-01-01'")))
        b.add_column(sa.Column("valid_to", sa.Date(), nullable=True))

    op.create_table(
        "income_special",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("actual_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payout_timing", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_income_special_year_month", "income_special", ["year", "month"])
    op.create_index("ix_income_special_account_id", "income_special", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_income_special_account_id", table_name="income_special")
    op.drop_index("ix_income_special_year_month", table_name="income_special")
    op.drop_table("income_special")

    with op.batch_alter_table("savings_rule") as b:
        b.drop_column("valid_to")
        b.drop_column("valid_from")