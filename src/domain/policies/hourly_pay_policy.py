# finanzmanager/domain/policies/hourly_pay_policy.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping

TWOPLACES = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class PayRule:
    """
    Domain representation of a PayRule used for calculation.

    rule_type:
        - HOURLY_WAGE (base hourly wage)
        - NIGHT | SUNDAY | HOLIDAY | OVERTIME (surcharges)
        - SALARY is ignored for hourly calculation (belongs to fixed income).

    unit:
        - EUR_PER_HOUR: additive premium per hour (e.g. 3.50 EUR/h)
        - MULTIPLIER: multiplier on base hourly wage (e.g. 1.25 => +25%)
    """
    rule_type: str
    value: Decimal
    unit: str  # "EUR_PER_HOUR" | "MULTIPLIER" | "EUR_PER_MONTH"


def _q(x: Decimal) -> Decimal:
    return x.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calc_hourly_income(rules: list[PayRule], hours: Mapping[str, Decimal]) -> Decimal:
    """
    Compute calculated hourly income (without special_amount).

    Expected hour keys:
      - hours_normal (regular hours)
      - night (night hours)
      - sunday (Sunday hours)
      - holiday (holiday hours)
      - overtime (overtime hours)

    Behavior:
      - Base pay: HOURLY_WAGE * sum(hours for all buckets)
      - Premium rules apply only to their bucket hours
        - EUR_PER_HOUR: +value * hours
        - MULTIPLIER: +(mult-1) * HOURLY_WAGE * hours
    """
    base_rate = Decimal("0")
    premiums: dict[str, PayRule] = {}

    for r in rules:
        if r.rule_type == "HOURLY_WAGE" and r.unit == "EUR_PER_HOUR":
            base_rate = r.value
        else:
            premiums[r.rule_type] = r

    def _h(key: str) -> Decimal:
        v = hours.get(key, Decimal("0"))
        try:
            return Decimal(v)
        except Exception:
            return Decimal("0")

    buckets = {
        "hours_normal": _h("hours_normal"),
        "night": _h("night"),
        "sunday": _h("sunday"),
        "holiday": _h("holiday"),
        "overtime": _h("overtime"),
    }

    total_hours = sum(buckets.values(), Decimal("0"))
    total = base_rate * total_hours

    mapping = {
        "NIGHT": "night",
        "SUNDAY": "sunday",
        "HOLIDAY": "holiday",
        "OVERTIME": "overtime",
    }

    for rule_type, hour_key in mapping.items():
        h = buckets.get(hour_key, Decimal("0"))
        if h == 0:
            continue
        pr = premiums.get(rule_type)
        if not pr:
            continue

        if pr.unit == "EUR_PER_HOUR":
            total += pr.value * h
        elif pr.unit == "MULTIPLIER":
            total += (pr.value - Decimal("1.0")) * base_rate * h

    return _q(total)
