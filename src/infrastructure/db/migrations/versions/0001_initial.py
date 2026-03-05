# finanzmanager/infrastructure/db/migrations/versions/0001_initial.py
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # enums
    op.execute("PRAGMA foreign_keys=ON;")

    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bank_name", sa.String(length=120), nullable=True),
        sa.Column("account_name", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("iban", sa.String(length=64), nullable=True),
        sa.Column("role_income", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("role_debit", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "employer",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("payout_timing", sa.String(length=32), nullable=False),
        sa.Column("default_account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("name", name="uq_employer_name"),
    )
    op.create_index("ix_employer_default_account_id", "employer", ["default_account_id"])

    op.create_table(
        "pay_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employer_id", sa.Integer(), sa.ForeignKey("employer.id"), nullable=False),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(10, 4), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_pay_rule_employer_id", "pay_rule", ["employer_id"])

    op.create_table(
        "income_fixed",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employer_id", sa.Integer(), sa.ForeignKey("employer.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("base_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("special_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("calc_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("actual_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payout_timing", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("employer_id", "year", "month", name="uq_income_fixed_emp_period"),
    )
    op.create_index("ix_income_fixed_year_month", "income_fixed", ["year", "month"])
    op.create_index("ix_income_fixed_employer_id", "income_fixed", ["employer_id"])
    op.create_index("ix_income_fixed_account_id", "income_fixed", ["account_id"])

    op.create_table(
        "income_hourly",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employer_id", sa.Integer(), sa.ForeignKey("employer.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("hours_bw", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("hours_by", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("hours_normal", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("night_bw", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("sunday_bw", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("night_by", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("sunday_by", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("night", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("sunday", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("holiday", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("overtime", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("special_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("calc_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("actual_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payout_timing", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("employer_id", "year", "month", name="uq_income_hourly_emp_period"),
    )
    op.create_index("ix_income_hourly_year_month", "income_hourly", ["year", "month"])
    op.create_index("ix_income_hourly_employer_id", "income_hourly", ["employer_id"])
    op.create_index("ix_income_hourly_account_id", "income_hourly", ["account_id"])

    op.create_table(
        "expense_category",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("group", sa.String(length=16), nullable=False),
        sa.UniqueConstraint("name", name="uq_expense_category_name"),
    )

    op.create_table(
        "expense_recurring",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("expense_category.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("frequency_months", sa.Integer(), nullable=False),
        sa.Column("due_day", sa.Integer(), nullable=False),
        sa.Column("anchor_month", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("pay_bucket", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("allocation_override", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_expense_recurring_category_id", "expense_recurring", ["category_id"])
    op.create_index("ix_expense_recurring_account_id", "expense_recurring", ["account_id"])

    op.create_table(
        "expense_variable",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("expense_category.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
        sa.Column("pay_bucket", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_expense_variable_year_month", "expense_variable", ["year", "month"])
    op.create_index("ix_expense_variable_category_id", "expense_variable", ["category_id"])
    op.create_index("ix_expense_variable_account_id", "expense_variable", ["account_id"])

    op.create_table(
        "loan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("principal_initial", sa.Numeric(12, 2), nullable=False),
        sa.Column("annual_interest_rate", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("regular_payment", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_timing", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("name", name="uq_loan_name"),
    )
    op.create_index("ix_loan_account_id", "loan", ["account_id"])

    op.create_table(
        "loan_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("loan_id", sa.Integer(), sa.ForeignKey("loan.id"), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_regular_payment", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_annual_interest_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_loan_event_year_month", "loan_event", ["year", "month"])
    op.create_index("ix_loan_event_loan_id", "loan_event", ["loan_id"])

    op.create_table(
        "savings_goal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("linked_to_source", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("name", name="uq_savings_goal_name"),
    )

    op.create_table(
        "savings_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employer_id", sa.Integer(), sa.ForeignKey("employer.id"), nullable=False),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("savings_goal.id"), nullable=True),
        sa.Column("percentage", sa.Numeric(6, 4), nullable=False, server_default="0.10"),
    )
    op.create_index("ix_savings_rule_employer_id", "savings_rule", ["employer_id"])
    op.create_index("ix_savings_rule_goal_id", "savings_rule", ["goal_id"])

    op.create_table(
        "savings_contribution",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("savings_goal.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_savings_contribution_goal_id", "savings_contribution", ["goal_id"])
    op.create_index("ix_savings_contribution_account_id", "savings_contribution", ["account_id"])

    op.create_table(
        "import_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=260), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("file_hash", name="uq_import_run_file_hash"),
    )
    op.create_index("ix_import_run_file_hash", "import_run", ["file_hash"])


def downgrade() -> None:
    op.drop_index("ix_import_run_file_hash", table_name="import_run")
    op.drop_table("import_run")

    op.drop_index("ix_savings_contribution_account_id", table_name="savings_contribution")
    op.drop_index("ix_savings_contribution_goal_id", table_name="savings_contribution")
    op.drop_table("savings_contribution")

    op.drop_index("ix_savings_rule_goal_id", table_name="savings_rule")
    op.drop_index("ix_savings_rule_employer_id", table_name="savings_rule")
    op.drop_table("savings_rule")

    op.drop_table("savings_goal")

    op.drop_index("ix_loan_event_loan_id", table_name="loan_event")
    op.drop_index("ix_loan_event_year_month", table_name="loan_event")
    op.drop_table("loan_event")

    op.drop_index("ix_loan_account_id", table_name="loan")
    op.drop_table("loan")

    op.drop_index("ix_expense_variable_account_id", table_name="expense_variable")
    op.drop_index("ix_expense_variable_category_id", table_name="expense_variable")
    op.drop_index("ix_expense_variable_year_month", table_name="expense_variable")
    op.drop_table("expense_variable")

    op.drop_index("ix_expense_recurring_account_id", table_name="expense_recurring")
    op.drop_index("ix_expense_recurring_category_id", table_name="expense_recurring")
    op.drop_table("expense_recurring")

    op.drop_table("expense_category")

    op.drop_index("ix_income_hourly_account_id", table_name="income_hourly")
    op.drop_index("ix_income_hourly_employer_id", table_name="income_hourly")
    op.drop_index("ix_income_hourly_year_month", table_name="income_hourly")
    op.drop_table("income_hourly")

    op.drop_index("ix_income_fixed_account_id", table_name="income_fixed")
    op.drop_index("ix_income_fixed_employer_id", table_name="income_fixed")
    op.drop_index("ix_income_fixed_year_month", table_name="income_fixed")
    op.drop_table("income_fixed")

    op.drop_index("ix_pay_rule_employer_id", table_name="pay_rule")
    op.drop_table("pay_rule")

    op.drop_index("ix_employer_default_account_id", table_name="employer")
    op.drop_table("employer")

    op.drop_table("account")
