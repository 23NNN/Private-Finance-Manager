from decimal import Decimal
from src.domain.policies.loan_policy import compute_month_status


def test_loan_month_status_no_interest():
    events = [
        {"event_type": "PAYMENT", "year": 2026, "month": 1, "amount": Decimal("100.00"), "new_regular_payment": None},
        {"event_type": "EXTRA_PAYMENT", "year": 2026, "month": 1, "amount": Decimal("50.00"), "new_regular_payment": None},
    ]
    st = compute_month_status(
        principal_initial=Decimal("1000.00"),
        regular_payment=Decimal("100.00"),
        events=events,
        year=2026,
        month=1,
    )
    assert st.open_before == Decimal("1000.00")
    assert st.payment == Decimal("100.00")
    assert st.extra == Decimal("50.00")
    assert st.open_after == Decimal("850.00")
