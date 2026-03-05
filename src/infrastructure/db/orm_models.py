# finanzmanager/infrastructure/db/orm_models.py
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Enumerations
class PayoutTiming(str, enum.Enum):
    BEGINNING = "BEGINNING"
    MID = "MID"


# Compatibility alias (loan_service/import_service expect PaymentTiming)
PaymentTiming = PayoutTiming


class PayRuleType(str, enum.Enum):
    HOURLY_WAGE = "HOURLY_WAGE"       # Hourly wage
    SALARY = "SALARY"                # Fixed salary
    NIGHT = "NIGHT"                  # Night surcharge
    SUNDAY = "SUNDAY"                # Sunday surcharge
    HOLIDAY = "HOLIDAY"              # Holiday surcharge
    OVERTIME = "OVERTIME"            # Overtime


class PayRuleUnit(str, enum.Enum):
    EUR_PER_HOUR = "EUR_PER_HOUR"
    EUR_PER_MONTH = "EUR_PER_MONTH"
    MULTIPLIER = "MULTIPLIER"


class ExpenseGroup(str, enum.Enum):
    FIX = "FIX"
    VARIABLE = "VARIABLE"
    LOAN = "LOAN"


class RecurringStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class VariableStatus(str, enum.Enum):
    OPEN = "OPEN"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class PayBucket(str, enum.Enum):
    BEGINNING = "BEGINNING"
    MID = "MID"
    NONE = "NONE"


class AllocationOverride(str, enum.Enum):
    CASHFLOW = "CASHFLOW"
    ALLOCATE_MONTHLY = "ALLOCATE_MONTHLY"
    ALLOCATE_QUARTERLY = "ALLOCATE_QUARTERLY"


class LoanStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class LoanEventType(str, enum.Enum):
    PAYMENT = "PAYMENT"
    EXTRA_PAYMENT = "EXTRA_PAYMENT"
    RATE_CHANGE = "RATE_CHANGE"
    INTEREST_CHANGE = "INTEREST_CHANGE"
    NOTE = "NOTE"


class SavingsGoalType(str, enum.Enum):
    GENERAL = "GENERAL"
    EMERGENCY = "EMERGENCY"
    INVEST = "INVEST"


# ORM Table models
class Account(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_name: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    iban: Mapped[str | None] = mapped_column(String(64), nullable=True)

    role_income: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role_debit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Employer(Base):
    __tablename__ = "employer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    payout_timing: Mapped[PayoutTiming] = mapped_column(Enum(PayoutTiming, name="employer_payout_timing"), nullable=False)
    default_account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    pay_rules: Mapped[list["PayRule"]] = relationship(back_populates="employer")


class PayRule(Base):
    __tablename__ = "pay_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employer.id"), index=True)
    rule_type: Mapped[PayRuleType] = mapped_column(Enum(PayRuleType, name="pay_rule_type"), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    unit: Mapped[PayRuleUnit] = mapped_column(Enum(PayRuleUnit, name="pay_rule_unit"), nullable=False)

    # NEW: rule history (same type can exist multiple times)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, default=date(1900, 1, 1))
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    employer: Mapped["Employer"] = relationship(back_populates="pay_rules")


class IncomeFixed(Base):
    __tablename__ = "income_fixed"
    __table_args__ = (
        Index("ix_income_fixed_year_month", "year", "month"),
        UniqueConstraint("employer_id", "year", "month", name="uq_income_fixed_emp_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employer.id"), index=True)

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    special_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    calc_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)

    payout_timing: Mapped[PayoutTiming] = mapped_column(Enum(PayoutTiming, name="income_fixed_payout_timing"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    employer: Mapped[Employer] = relationship("Employer")
    account: Mapped[Account | None] = relationship("Account")


class IncomeHourly(Base):
    __tablename__ = "income_hourly"
    __table_args__ = (
        Index("ix_income_hourly_year_month", "year", "month"),
        UniqueConstraint("employer_id", "year", "month", name="uq_income_hourly_emp_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employer.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    hours_bw: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)
    hours_by: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)
    hours_normal: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)

    night_bw: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)
    sunday_bw: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)
    night_by: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)
    sunday_by: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)

    night: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)
    sunday: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)
    holiday: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)
    overtime: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"), nullable=False)

    special_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    calc_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)

    payout_timing: Mapped[PayoutTiming] = mapped_column(Enum(PayoutTiming, name="income_hourly_payout_timing"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    employer: Mapped[Employer] = relationship("Employer")
    account: Mapped[Account | None] = relationship("Account")




class IncomeSpecial(Base):
    __tablename__ = "income_special"
    __table_args__ = (Index("ix_income_special_year_month", "year", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)

    payout_timing: Mapped[PayoutTiming] = mapped_column(Enum(PayoutTiming, name="income_special_payout_timing"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped[Account | None] = relationship("Account")

class ExpenseCategory(Base):
    __tablename__ = "expense_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    group: Mapped[ExpenseGroup] = mapped_column(Enum(ExpenseGroup, name="expense_group"), nullable=False)


# Compatibility alias (some newer parts use "Category")
Category = ExpenseCategory


class ExpenseRecurring(Base):
    __tablename__ = "expense_recurring"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_category.id"), index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    frequency_months: Mapped[int] = mapped_column(Integer, nullable=False)  # 1/3/12
    due_day: Mapped[int] = mapped_column(Integer, nullable=False)
    anchor_month: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[RecurringStatus] = mapped_column(Enum(RecurringStatus, name="recurring_status"), nullable=False)

    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), index=True)
    pay_bucket: Mapped[PayBucket] = mapped_column(Enum(PayBucket, name="pay_bucket"), default=PayBucket.NONE)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    allocation_override: Mapped[AllocationOverride | None] = mapped_column(
        Enum(AllocationOverride, name="allocation_override"),
        nullable=True,
    )

    category: Mapped[ExpenseCategory] = relationship("ExpenseCategory")
    account: Mapped[Account] = relationship("Account")


class ExpenseVariable(Base):
    __tablename__ = "expense_variable"
    __table_args__ = (Index("ix_expense_variable_year_month", "year", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_category.id"), index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[VariableStatus] = mapped_column(Enum(VariableStatus, name="variable_status"), nullable=False)

    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"), nullable=True, index=True)
    pay_bucket: Mapped[PayBucket] = mapped_column(Enum(PayBucket, name="variable_pay_bucket"), default=PayBucket.NONE)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped[ExpenseCategory] = relationship("ExpenseCategory")
    account: Mapped[Account | None] = relationship("Account")


class Loan(Base):
    __tablename__ = "loan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    principal_initial: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    annual_interest_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=Decimal("0.0"))
    regular_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    payment_timing: Mapped[PayoutTiming] = mapped_column(Enum(PayoutTiming, name="loan_payment_timing"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), index=True)

    status: Mapped[LoanStatus] = mapped_column(Enum(LoanStatus, name="loan_status"), nullable=False, default=LoanStatus.ACTIVE)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    events: Mapped[list["LoanEvent"]] = relationship("LoanEvent", back_populates="loan")


class LoanEvent(Base):
    __tablename__ = "loan_event"
    __table_args__ = (Index("ix_loan_event_year_month", "year", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loan.id"), index=True)

    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    event_type: Mapped[LoanEventType] = mapped_column(Enum(LoanEventType, name="loan_event_type"), nullable=False)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_regular_payment: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_annual_interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    loan: Mapped[Loan] = relationship("Loan", back_populates="events")


class SavingsGoal(Base):
    __tablename__ = "savings_goal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    type: Mapped[SavingsGoalType] = mapped_column(Enum(SavingsGoalType, name="savings_goal_type"), nullable=False)
    linked_to_source: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SavingsRule(Base):
    __tablename__ = "savings_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employer.id"), index=True)
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("savings_goal.id"), nullable=True, index=True)
    percentage: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.10"), nullable=False)

    valid_from: Mapped[date] = mapped_column(Date, nullable=False, default=date(1900, 1, 1))
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    employer: Mapped[Employer] = relationship("Employer")
    goal: Mapped[SavingsGoal | None] = relationship("SavingsGoal")


class SavingsContribution(Base):
    __tablename__ = "savings_contribution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("savings_goal.id"), index=True)

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    goal: Mapped[SavingsGoal] = relationship("SavingsGoal")
    account: Mapped[Account | None] = relationship("Account")


class ImportRun(Base):
    __tablename__ = "import_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(260), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("file_hash", name="uq_import_run_file_hash"),)


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class I18nString(Base):
    __tablename__ = "i18n_string"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    lang: Mapped[str] = mapped_column(String(8), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
