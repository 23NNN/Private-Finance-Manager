from decimal import Decimal
from src.domain.policies.savings_policy import calc_savings_per_employer


def test_savings_10_percent_per_employer():
    incomes = [(1, "A", Decimal("1000.00")), (2, "B", Decimal("500.00"))]
    res = calc_savings_per_employer(incomes, Decimal("0.10"))
    assert res[0].savings_amount == Decimal("100.00")
    assert res[1].savings_amount == Decimal("50.00")
