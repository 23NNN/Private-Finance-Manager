# scripts/build_demo_data.py
from __future__ import annotations

"""Generate a fully populated demo database (dummy data) for the Finance Manager."""

import argparse
import os
import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from src.config.settings import get_settings  # noqa: E402
from src.infrastructure.db.engine import SessionLocal, init_engine  # noqa: E402
from src.infrastructure.db.migrations.runner import upgrade_db_if_possible  # noqa: E402
from src.infrastructure.logging_setup import configure_logging  # noqa: E402
from src.infrastructure.db import orm_models as orm  # noqa: E402


def _r2(x: Decimal) -> Decimal:
    return (Decimal(x) if x is not None else Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _eur_from_cents(cents: int) -> Decimal:
    return _r2(Decimal(cents) / Decimal("100"))


def _set_if_has(obj: Any, field: str, value: Any) -> None:
    if hasattr(obj, field):
        setattr(obj, field, value)


def _pick_active_by_valid_from(rows: list[Any], at: date) -> Any | None:
    active = []
    for r in rows:
        vf = getattr(r, "valid_from", None) or date(1900, 1, 1)
        vt = getattr(r, "valid_to", None)
        if vf <= at and (vt is None or at <= vt):
            active.append(r)
    if not active:
        return None
    active.sort(key=lambda r: getattr(r, "valid_from", date(1900, 1, 1)) or date(1900, 1, 1), reverse=True)
    return active[0]


def _calc_hourly_amount(rules: list[orm.PayRule], hours: dict[str, Decimal], special: Decimal) -> Decimal:
    """Kompatibel zu mehreren calc_hourly_income-Varianten im Repo."""
    from src.domain.policies.hourly_pay_policy import PayRule, calc_hourly_income  # local import

    prules = [PayRule(rule_type=r.rule_type.value, unit=r.unit.value, value=r.value) for r in rules]

    try:
        base = calc_hourly_income(rules=prules, hours=hours)
    except TypeError:
        base = calc_hourly_income(prules, hours)

    if hasattr(base, "total"):
        base = getattr(base, "total")
    try:
        base_d = Decimal(base)
    except Exception:
        base_d = Decimal("0.00")
    return _r2(base_d + (special or Decimal("0.00")))


@dataclass(frozen=True)
class DemoIds:
    giro_id: int
    savings_id: int
    creditcard_id: int
    cash_id: int
    employer_main_id: int
    employer_side_id: int
    goal_emergency_id: int
    goal_vacation_id: int
    cat_rent_id: int
    cat_util_id: int
    cat_inet_id: int
    cat_ins_id: int
    cat_food_id: int
    cat_fuel_id: int
    cat_fun_id: int
    cat_loan_id: int
    cat_loan_extra_id: int
    loan_car_id: int
    loan_consumer_id: int


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="build_demo_data", description="Generate a demo DB with dummy data")
    p.add_argument("--data-dir", type=str, default=str(ROOT_DIR / "demo_data"), help="Target data directory (DB/logs)")
    p.add_argument("--keep", action="store_true", help="Keep existing DB and try to extend it")
    p.add_argument("--seed", type=int, default=42, help="Random seed (deterministic)")
    p.add_argument("--year", type=int, default=date.today().year, help="Base year (default: current year)")
    p.add_argument("--mini", action="store_true", help="Current + next month only (fast)")
    return p.parse_args(argv)


def _init_db(data_dir: Path, *, keep: bool) -> Path:
    os.environ["FINANZMANAGER_DATA_DIR"] = str(data_dir)
    os.environ["FINANZMANAGER_LOG_DIR"] = str(data_dir / "logs")

    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    configure_logging(settings.log_path())

    db_path = settings.db_path()
    if db_path.exists() and not keep:
        db_path.unlink()

    init_engine(settings.sqlite_url())
    upgrade_db_if_possible()
    return db_path


def _periods_to_seed(base_year: int, *, mini: bool) -> list[tuple[int, int]]:
    if not mini:
        return [(base_year, m) for m in range(1, 13)] + [(base_year + 1, 1)]

    today = date.today()
    start_month = today.month if base_year == today.year else 1
    periods: list[tuple[int, int]] = [(base_year, start_month)]
    if start_month == 12:
        periods.append((base_year + 1, 1))
    else:
        periods.append((base_year, start_month + 1))
    return periods


def _seed_all(year: int, rnd: random.Random, *, mini: bool) -> None:
    periods = _periods_to_seed(year, mini=mini)

    s = SessionLocal()
    try:
        ids = _seed_master_data(s, year=year)
        _seed_rules(s, ids=ids, year=year)
        _seed_incomes(s, ids=ids, periods=periods, rnd=rnd)
        _seed_expenses(s, ids=ids, periods=periods, rnd=rnd)
        _seed_loans(s, ids=ids, periods=periods, mini=mini)
        s.commit()
    except IntegrityError as e:
        s.rollback()
        raise SystemExit(f"DB IntegrityError: {e}") from e
    finally:
        s.close()


def _get_or_create_account(
    s,
    *,
    label: str,
    bank: str,
    name: str,
    iban: str | None,
    role_income: bool,
    role_debit: bool,
) -> orm.Account:
    obj = s.execute(select(orm.Account).where(orm.Account.label == label)).scalar_one_or_none()
    if obj:
        return obj
    obj = orm.Account()
    _set_if_has(obj, "label", label)
    _set_if_has(obj, "bank_name", bank)
    _set_if_has(obj, "account_name", name)
    _set_if_has(obj, "iban", iban)
    _set_if_has(obj, "role_income", role_income)
    _set_if_has(obj, "role_debit", role_debit)
    _set_if_has(obj, "notes", "Demo Data")
    s.add(obj)
    s.flush()
    return obj


def _get_or_create_employer(s, *, name: str, payout: orm.PayoutTiming, default_account_id: int) -> orm.Employer:
    obj = s.execute(select(orm.Employer).where(orm.Employer.name == name)).scalar_one_or_none()
    if obj:
        return obj
    obj = orm.Employer()
    _set_if_has(obj, "name", name)
    _set_if_has(obj, "payout_timing", payout)
    _set_if_has(obj, "default_account_id", default_account_id)
    _set_if_has(obj, "notes", "Demo Employer")
    s.add(obj)
    s.flush()
    return obj


def _get_or_create_goal(s, *, name: str, goal_type: orm.SavingsGoalType) -> orm.SavingsGoal:
    obj = s.execute(select(orm.SavingsGoal).where(orm.SavingsGoal.name == name)).scalar_one_or_none()
    if obj:
        return obj
    obj = orm.SavingsGoal()
    _set_if_has(obj, "name", name)
    _set_if_has(obj, "type", goal_type)
    _set_if_has(obj, "linked_to_source", False)
    _set_if_has(obj, "notes", "Demo Goal")
    s.add(obj)
    s.flush()
    return obj


def _get_or_create_category(s, *, name: str, group: orm.ExpenseGroup) -> orm.ExpenseCategory:
    obj = s.execute(select(orm.ExpenseCategory).where(orm.ExpenseCategory.name == name)).scalar_one_or_none()
    if obj:
        return obj
    obj = orm.ExpenseCategory()
    _set_if_has(obj, "name", name)
    _set_if_has(obj, "group", group)
    s.add(obj)
    s.flush()
    return obj


def _seed_master_data(s, *, year: int) -> DemoIds:
    giro = _get_or_create_account(
        s,
        label="Checking Account",
        bank="DemoBank",
        name="Checking",
        iban="DE00 0000 0000 0000 0000 00",
        role_income=True,
        role_debit=True,
    )
    savings = _get_or_create_account(
        s,
        label="Savings Account",
        bank="DemoBank",
        name="Savings",
        iban="DE00 1111 1111 1111 1111 11",
        role_income=False,
        role_debit=False,
    )
    cc = _get_or_create_account(
        s,
        label="Credit Card",
        bank="DemoCard",
        name="Visa",
        iban=None,
        role_income=False,
        role_debit=True,
    )
    cash = _get_or_create_account(
        s,
        label="Cash",
        bank="",
        name="Cash",
        iban=None,
        role_income=False,
        role_debit=True,
    )

    emp_main = _get_or_create_employer(s, name="Example Corp", payout=orm.PayoutTiming.MID, default_account_id=giro.id)
    emp_side = _get_or_create_employer(s, name="Side Job Café", payout=orm.PayoutTiming.BEGINNING, default_account_id=giro.id)

    goal_em = _get_or_create_goal(
        s,
        name="Emergency Fund",
        goal_type=getattr(orm.SavingsGoalType, "EMERGENCY", orm.SavingsGoalType.GENERAL),
    )
    goal_vac = _get_or_create_goal(
        s,
        name="Vacation",
        goal_type=getattr(orm.SavingsGoalType, "GENERAL", orm.SavingsGoalType.GENERAL),
    )

    cat_rent = _get_or_create_category(s, name="Rent", group=orm.ExpenseGroup.FIX)
    cat_util = _get_or_create_category(s, name="Electricity & Gas", group=orm.ExpenseGroup.FIX)
    cat_inet = _get_or_create_category(s, name="Internet & Mobile", group=orm.ExpenseGroup.FIX)
    cat_ins = _get_or_create_category(s, name="Insurance", group=orm.ExpenseGroup.FIX)

    cat_food = _get_or_create_category(s, name="Groceries", group=orm.ExpenseGroup.VARIABLE)
    cat_fuel = _get_or_create_category(s, name="Fuel", group=orm.ExpenseGroup.VARIABLE)
    cat_fun = _get_or_create_category(s, name="Leisure", group=orm.ExpenseGroup.VARIABLE)

    cat_loan = _get_or_create_category(s, name="Loan Payment", group=orm.ExpenseGroup.LOAN)
    cat_loan_extra = _get_or_create_category(s, name="Extra Repayment", group=orm.ExpenseGroup.LOAN)

    return DemoIds(
        giro_id=giro.id,
        savings_id=savings.id,
        creditcard_id=cc.id,
        cash_id=cash.id,
        employer_main_id=emp_main.id,
        employer_side_id=emp_side.id,
        goal_emergency_id=goal_em.id,
        goal_vacation_id=goal_vac.id,
        cat_rent_id=cat_rent.id,
        cat_util_id=cat_util.id,
        cat_inet_id=cat_inet.id,
        cat_ins_id=cat_ins.id,
        cat_food_id=cat_food.id,
        cat_fuel_id=cat_fuel.id,
        cat_fun_id=cat_fun.id,
        cat_loan_id=cat_loan.id,
        cat_loan_extra_id=cat_loan_extra.id,
        loan_car_id=-1,
        loan_consumer_id=-1,
    )


def _upsert_pay_rule(
    s,
    *,
    employer_id: int,
    rule_type: orm.PayRuleType,
    unit: orm.PayRuleUnit,
    value: Decimal,
    valid_from: date,
    valid_to: date | None,
    notes: str | None = None,
) -> orm.PayRule:
    stmt = select(orm.PayRule).where(
        orm.PayRule.employer_id == employer_id,
        orm.PayRule.rule_type == rule_type,
        orm.PayRule.valid_from == valid_from,
    )
    obj = s.execute(stmt).scalar_one_or_none()
    if obj is None:
        obj = orm.PayRule()
        s.add(obj)

    _set_if_has(obj, "employer_id", employer_id)
    _set_if_has(obj, "rule_type", rule_type)
    _set_if_has(obj, "unit", unit)
    _set_if_has(obj, "value", _r2(value) if unit != orm.PayRuleUnit.MULTIPLIER else Decimal(value))
    _set_if_has(obj, "valid_from", valid_from)
    _set_if_has(obj, "valid_to", valid_to)
    _set_if_has(obj, "notes", notes)
    s.flush()
    return obj


def _upsert_savings_rule(
    s,
    *,
    employer_id: int,
    percentage: Decimal,
    goal_id: int | None,
    valid_from: date,
    valid_to: date | None,
) -> orm.SavingsRule:
    stmt = select(orm.SavingsRule).where(
        orm.SavingsRule.employer_id == employer_id,
        orm.SavingsRule.valid_from == valid_from,
    )
    obj = s.execute(stmt).scalar_one_or_none()
    if obj is None:
        obj = orm.SavingsRule()
        s.add(obj)

    _set_if_has(obj, "employer_id", employer_id)
    _set_if_has(obj, "goal_id", goal_id)
    _set_if_has(obj, "percentage", percentage)
    _set_if_has(obj, "valid_from", valid_from)
    _set_if_has(obj, "valid_to", valid_to)
    s.flush()
    return obj


def _seed_rules(s, *, ids: DemoIds, year: int) -> None:
    y1 = date(year, 1, 1)
    y7 = date(year, 7, 1)
    y7m1 = y7 - timedelta(days=1)

    _upsert_pay_rule(
        s,
        employer_id=ids.employer_main_id,
        rule_type=orm.PayRuleType.SALARY,
        unit=orm.PayRuleUnit.EUR_PER_MONTH,
        value=Decimal("3200.00"),
        valid_from=y1,
        valid_to=y7m1,
        notes="Salary at year start",
    )
    _upsert_pay_rule(
        s,
        employer_id=ids.employer_main_id,
        rule_type=orm.PayRuleType.SALARY,
        unit=orm.PayRuleUnit.EUR_PER_MONTH,
        value=Decimal("3400.00"),
        valid_from=y7,
        valid_to=None,
        notes="Salary adjustment from July",
    )

    _upsert_pay_rule(
        s,
        employer_id=ids.employer_side_id,
        rule_type=orm.PayRuleType.HOURLY_WAGE,
        unit=orm.PayRuleUnit.EUR_PER_HOUR,
        value=Decimal("15.50"),
        valid_from=y1,
        valid_to=None,
        notes="Base hourly rate",
    )
    _upsert_pay_rule(
        s,
        employer_id=ids.employer_side_id,
        rule_type=orm.PayRuleType.NIGHT,
        unit=orm.PayRuleUnit.MULTIPLIER,
        value=Decimal("1.25"),
        valid_from=y1,
        valid_to=None,
        notes="+25% Night",
    )
    _upsert_pay_rule(
        s,
        employer_id=ids.employer_side_id,
        rule_type=orm.PayRuleType.SUNDAY,
        unit=orm.PayRuleUnit.MULTIPLIER,
        value=Decimal("1.50"),
        valid_from=y1,
        valid_to=None,
        notes="+50% Sunday",
    )
    _upsert_pay_rule(
        s,
        employer_id=ids.employer_side_id,
        rule_type=orm.PayRuleType.HOLIDAY,
        unit=orm.PayRuleUnit.MULTIPLIER,
        value=Decimal("2.00"),
        valid_from=y1,
        valid_to=None,
        notes="+100% Holiday",
    )
    _upsert_pay_rule(
        s,
        employer_id=ids.employer_side_id,
        rule_type=orm.PayRuleType.OVERTIME,
        unit=orm.PayRuleUnit.MULTIPLIER,
        value=Decimal("1.20"),
        valid_from=y1,
        valid_to=None,
        notes="+20% Overtime",
    )

    y10 = date(year, 10, 1)
    y9m1 = y10 - timedelta(days=1)

    _upsert_savings_rule(
        s,
        employer_id=ids.employer_main_id,
        percentage=Decimal("0.20"),
        goal_id=ids.goal_emergency_id,
        valid_from=y1,
        valid_to=y9m1,
    )
    _upsert_savings_rule(
        s,
        employer_id=ids.employer_main_id,
        percentage=Decimal("0.25"),
        goal_id=ids.goal_emergency_id,
        valid_from=y10,
        valid_to=None,
    )
    _upsert_savings_rule(
        s,
        employer_id=ids.employer_side_id,
        percentage=Decimal("0.10"),
        goal_id=ids.goal_vacation_id,
        valid_from=y1,
        valid_to=None,
    )


def _salary_for_month(s, employer_id: int, at: date) -> Decimal:
    rows = list(
        s.execute(
            select(orm.PayRule).where(
                orm.PayRule.employer_id == employer_id,
                orm.PayRule.rule_type == orm.PayRuleType.SALARY,
            )
        ).scalars()
    )
    rule = _pick_active_by_valid_from(rows, at)
    if not rule:
        return Decimal("0.00")
    return _r2(getattr(rule, "value", Decimal("0.00")))


def _active_hourly_rules(s, employer_id: int, at: date) -> list[orm.PayRule]:
    rows = list(s.execute(select(orm.PayRule).where(orm.PayRule.employer_id == employer_id)).scalars())
    best: dict[str, orm.PayRule] = {}
    for r in rows:
        vf = getattr(r, "valid_from", None) or date(1900, 1, 1)
        vt = getattr(r, "valid_to", None)
        if not (vf <= at and (vt is None or at <= vt)):
            continue
        rt = r.rule_type.value
        cur = best.get(rt)
        if cur is None:
            best[rt] = r
        else:
            if (getattr(r, "valid_from", date(1900, 1, 1)) or date(1900, 1, 1)) > (
                getattr(cur, "valid_from", date(1900, 1, 1)) or date(1900, 1, 1)
            ):
                best[rt] = r
    return [r for r in best.values() if r.rule_type.value != "SALARY"]


def _seed_incomes(s, *, ids: DemoIds, periods: list[tuple[int, int]], rnd: random.Random) -> None:
    emp_main = s.get(orm.Employer, ids.employer_main_id)
    emp_side = s.get(orm.Employer, ids.employer_side_id)

    for y, m in periods:
        at = date(y, m, 1)

        base = _salary_for_month(s, ids.employer_main_id, at)
        special = _eur_from_cents(rnd.choice([0, 0, 0, 15000, 25000, 5000]))
        calc = _r2(base + special)

        actual = calc
        if rnd.random() < 0.15:
            actual = _r2(calc - _eur_from_cents(rnd.randint(500, 2500)))

        fixed = s.execute(
            select(orm.IncomeFixed).where(
                orm.IncomeFixed.employer_id == ids.employer_main_id,
                orm.IncomeFixed.year == y,
                orm.IncomeFixed.month == m,
            )
        ).scalar_one_or_none()
        if fixed is None:
            fixed = orm.IncomeFixed()
            s.add(fixed)

        _set_if_has(fixed, "employer_id", ids.employer_main_id)
        _set_if_has(fixed, "year", y)
        _set_if_has(fixed, "month", m)
        _set_if_has(fixed, "base_amount", base)
        _set_if_has(fixed, "special_amount", special)
        _set_if_has(fixed, "calc_amount", calc)
        _set_if_has(fixed, "actual_amount", actual)
        _set_if_has(fixed, "payout_timing", getattr(emp_main, "payout_timing", orm.PayoutTiming.MID))
        _set_if_has(fixed, "account_id", ids.giro_id)
        _set_if_has(fixed, "notes", "Demo Fixed Salary")

        hours = Decimal(rnd.randint(18, 42))
        night = Decimal(rnd.choice([0, 2, 4, 6, 8]))
        sunday = Decimal(rnd.choice([0, 0, 3, 5]))
        holiday = Decimal(rnd.choice([0, 0, 0, 4]))
        overtime = Decimal(rnd.choice([0, 1, 2, 3]))
        special2 = _eur_from_cents(rnd.choice([0, 0, 0, 1000, 2500, 5000]))

        rules = _active_hourly_rules(s, ids.employer_side_id, at)
        calc2 = _calc_hourly_amount(
            rules,
            hours={
                "hours_normal": hours,
                "night": night,
                "sunday": sunday,
                "holiday": holiday,
                "overtime": overtime,
            },
            special=special2,
        )

        hourly = s.execute(
            select(orm.IncomeHourly).where(
                orm.IncomeHourly.employer_id == ids.employer_side_id,
                orm.IncomeHourly.year == y,
                orm.IncomeHourly.month == m,
            )
        ).scalar_one_or_none()
        if hourly is None:
            hourly = orm.IncomeHourly()
            s.add(hourly)

        _set_if_has(hourly, "employer_id", ids.employer_side_id)
        _set_if_has(hourly, "year", y)
        _set_if_has(hourly, "month", m)

        for fld in ("hours_bw", "hours_by", "night_bw", "sunday_bw", "night_by", "sunday_by"):
            _set_if_has(hourly, fld, Decimal("0"))

        _set_if_has(hourly, "hours_normal", _r2(hours))
        _set_if_has(hourly, "night", _r2(night))
        _set_if_has(hourly, "sunday", _r2(sunday))
        _set_if_has(hourly, "holiday", _r2(holiday))
        _set_if_has(hourly, "overtime", _r2(overtime))
        _set_if_has(hourly, "special_amount", special2)
        _set_if_has(hourly, "calc_amount", calc2)
        _set_if_has(hourly, "actual_amount", calc2)
        _set_if_has(hourly, "payout_timing", getattr(emp_side, "payout_timing", orm.PayoutTiming.BEGINNING))
        _set_if_has(hourly, "account_id", ids.giro_id)
        _set_if_has(hourly, "notes", "Demo Hourly Wage")

        if (y, m) == periods[0]:
            name = "Demo Bonus"
            amt = _eur_from_cents(25000)
            sp = s.execute(
                select(orm.IncomeSpecial).where(
                    orm.IncomeSpecial.year == y,
                    orm.IncomeSpecial.month == m,
                    orm.IncomeSpecial.name == name,
                )
            ).scalar_one_or_none()
            if sp is None:
                sp = orm.IncomeSpecial()
                s.add(sp)

            _set_if_has(sp, "year", y)
            _set_if_has(sp, "month", m)
            _set_if_has(sp, "name", name)
            _set_if_has(sp, "amount", amt)
            _set_if_has(sp, "actual_amount", amt)
            _set_if_has(sp, "payout_timing", orm.PayoutTiming.MID)
            _set_if_has(sp, "account_id", ids.giro_id)
            _set_if_has(sp, "notes", "Demo Special Income")

    s.flush()


def _seed_expenses(s, *, ids: DemoIds, periods: list[tuple[int, int]], rnd: random.Random) -> None:
    def upsert_rec(name: str, cat_id: int, amount: Decimal, freq: int, due: int, acc_id: int, bucket: orm.PayBucket):
        obj = s.execute(select(orm.ExpenseRecurring).where(orm.ExpenseRecurring.name == name)).scalar_one_or_none()
        if obj is None:
            obj = orm.ExpenseRecurring()
            s.add(obj)
        _set_if_has(obj, "name", name)
        _set_if_has(obj, "category_id", cat_id)
        _set_if_has(obj, "amount", _r2(amount))
        _set_if_has(obj, "frequency_months", int(freq))
        _set_if_has(obj, "due_day", int(due))
        _set_if_has(obj, "anchor_month", None)
        _set_if_has(obj, "status", orm.RecurringStatus.ACTIVE)
        _set_if_has(obj, "account_id", acc_id)
        _set_if_has(obj, "pay_bucket", bucket)
        _set_if_has(obj, "notes", "Demo Fixed Costs")
        _set_if_has(obj, "allocation_override", None)

    upsert_rec("Rent", ids.cat_rent_id, Decimal("1050.00"), 1, 1, ids.giro_id, orm.PayBucket.BEGINNING)
    upsert_rec("Electricity & Gas", ids.cat_util_id, Decimal("110.00"), 1, 15, ids.giro_id, orm.PayBucket.MID)
    upsert_rec("Internet & Mobile", ids.cat_inet_id, Decimal("45.00"), 1, 10, ids.giro_id, orm.PayBucket.MID)
    upsert_rec("Insurance", ids.cat_ins_id, Decimal("65.00"), 1, 5, ids.giro_id, orm.PayBucket.BEGINNING)
    upsert_rec("Loan Payment (Bank)", ids.cat_loan_id, Decimal("250.00"), 1, 3, ids.giro_id, orm.PayBucket.BEGINNING)

    for y, m in periods:
        for i in range(4):
            amt = _eur_from_cents(rnd.randint(3500, 9500))
            v = orm.ExpenseVariable()
            _set_if_has(v, "name", f"Grocery Shopping {i+1}")
            _set_if_has(v, "category_id", ids.cat_food_id)
            _set_if_has(v, "amount", amt)
            _set_if_has(v, "year", y)
            _set_if_has(v, "month", m)
            _set_if_has(v, "status", orm.VariableStatus.PAID)
            _set_if_has(v, "account_id", ids.creditcard_id if rnd.random() < 0.6 else ids.giro_id)
            _set_if_has(v, "pay_bucket", orm.PayBucket.MID)
            _set_if_has(v, "notes", "Demo")
            s.add(v)

        v = orm.ExpenseVariable()
        _set_if_has(v, "name", "Leisure")
        _set_if_has(v, "category_id", ids.cat_fun_id)
        _set_if_has(v, "amount", _eur_from_cents(rnd.randint(1500, 12000)))
        _set_if_has(v, "year", y)
        _set_if_has(v, "month", m)
        _set_if_has(v, "status", orm.VariableStatus.PAID)
        _set_if_has(v, "account_id", ids.giro_id if rnd.random() < 0.4 else ids.creditcard_id)
        _set_if_has(v, "pay_bucket", orm.PayBucket.MID)
        _set_if_has(v, "notes", None)
        s.add(v)

    s.flush()


def _seed_loans(s, *, ids: DemoIds, periods: list[tuple[int, int]], mini: bool) -> None:
    def upsert_loan(name: str, principal: Decimal, regular: Decimal, start: date, timing: orm.PayoutTiming) -> orm.Loan:
        obj = s.execute(select(orm.Loan).where(orm.Loan.name == name)).scalar_one_or_none()
        if obj is None:
            obj = orm.Loan()
            s.add(obj)
        _set_if_has(obj, "name", name)
        _set_if_has(obj, "principal_initial", _r2(principal))
        _set_if_has(obj, "regular_payment", _r2(regular))
        _set_if_has(obj, "status", orm.LoanStatus.ACTIVE)
        _set_if_has(obj, "notes", "Demo Loan")
        _set_if_has(obj, "start_date", start)
        _set_if_has(obj, "annual_interest_rate", Decimal("0.035"))
        _set_if_has(obj, "payment_timing", timing)
        _set_if_has(obj, "account_id", ids.giro_id)
        s.flush()
        return obj

    base_year = periods[0][0]
    car = upsert_loan("Car Loan", Decimal("12000.00"), Decimal("250.00"), date(base_year, 1, 1), orm.PayoutTiming.BEGINNING)
    cons = upsert_loan("Laptop Installment", Decimal("1800.00"), Decimal("75.00"), date(base_year, 3, 1), orm.PayoutTiming.MID)

    def add_event(
        loan_id: int,
        y: int,
        m: int,
        et: orm.LoanEventType,
        amount: Decimal | None = None,
        new_payment: Decimal | None = None,
        note: str | None = None,
    ):
        ev = orm.LoanEvent()
        _set_if_has(ev, "loan_id", loan_id)
        _set_if_has(ev, "event_type", et)
        _set_if_has(ev, "year", y)
        _set_if_has(ev, "month", m)
        _set_if_has(ev, "amount", _r2(amount) if amount is not None else None)
        _set_if_has(ev, "new_regular_payment", _r2(new_payment) if new_payment is not None else None)
        _set_if_has(ev, "notes", note)
        _set_if_has(ev, "event_date", date(y, m, min(28, 5)))
        _set_if_has(ev, "new_annual_interest_rate", None)
        s.add(ev)

    months_for_events = sorted(set(periods)) if mini else [(base_year, m) for m in range(1, 13)] + [(base_year + 1, 1)]
    for y, m in months_for_events:
        add_event(car.id, y, m, orm.LoanEventType.PAYMENT, amount=None, note="Regular Payment")
        if (y, m) == (base_year, 6):
            add_event(car.id, y, m, orm.LoanEventType.RATE_CHANGE, amount=None, new_payment=Decimal("275.00"), note="Payment adjusted")

        if (y, m) >= (base_year, 3):
            add_event(cons.id, y, m, orm.LoanEventType.PAYMENT, amount=None, note="Regular Payment")

    s.flush()


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    data_dir = Path(args.data_dir).expanduser().resolve()
    rnd = random.Random(int(args.seed))

    db_path = _init_db(data_dir, keep=bool(args.keep))
    _seed_all(year=int(args.year), rnd=rnd, mini=bool(args.mini))

    mode = "Mini" if args.mini else "Full"
    print(f"\n✅ Demo database created ({mode}).")
    print(f"DB:  {db_path}")
    print(f"Logs:{(data_dir / 'logs')}")
    print("\nStart (Demo):")
    print(f"  python app.py --data-dir \"{data_dir}\" --log-dir \"{data_dir / 'logs'}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
