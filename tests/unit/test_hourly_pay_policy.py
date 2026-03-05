from decimal import Decimal

from src.domain.policies.hourly_pay_policy import PayRule, calc_hourly_income


def test_hourly_income_base_plus_night_multiplier():
    rules = [
        PayRule("HOURLY_WAGE", Decimal("20.00"), "EUR_PER_HOUR"),
        PayRule("NIGHT", Decimal("1.25"), "MULTIPLIER"),  # +25%
    ]
    hours = {
        "hours_normal": Decimal("10"),
        "night": Decimal("4"),
        "sunday": Decimal("0"),
        "holiday": Decimal("0"),
        "overtime": Decimal("0"),
    }
    # base: (10+4)*20 = 280
    # night premium: 4*20*(1.25-1)=20
    # total = 300
    assert calc_hourly_income(rules, hours) == Decimal("300.00")
