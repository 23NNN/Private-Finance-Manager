# finanzmanager/application/services/loan_service.py
from __future__ import annotations

import re
from decimal import Decimal

from src.application.dto.loans import LoanDTO, LoanEventDTO
from src.domain.models.period import Period
from src.domain.policies.loan_policy import compute_month_status
from src.infrastructure.db.orm_models import Loan, LoanEvent, LoanEventType, LoanStatus, PaymentTiming
from src.infrastructure.unit_of_work import UnitOfWork

_SETTINGS_RE = re.compile(r"\[\[SETTINGS(?P<body>.*?)\]\]", re.IGNORECASE | re.DOTALL)


def _strip_settings(notes: str | None) -> str | None:
    if not notes:
        return None
    cleaned = _SETTINGS_RE.sub("", notes).strip()
    return cleaned or None


def _parse_settings(notes: str | None) -> dict[str, str]:
    if not notes:
        return {}
    m = _SETTINGS_RE.search(notes)
    if not m:
        return {}
    body = (m.group("body") or "").strip()
    out: dict[str, str] = {}
    for part in body.split():
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip().lower()] = v.strip()
    return out


def _apply_settings(
    notes_user: str | None,
    *,
    override_account_id: int | None,
    override_payment_timing: str | None,
) -> str | None:
    base = (_strip_settings(notes_user) or "").strip()
    parts = []
    if override_account_id is not None:
        parts.append(f"account_id={int(override_account_id)}")
    if override_payment_timing:
        parts.append(f"payment_timing={override_payment_timing}")
    if not parts:
        return base or None
    marker = f"[[SETTINGS {' '.join(parts)}]]"
    if base:
        return f"{base}\n{marker}"
    return marker


class LoanService:
    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory

    def list_loans(self) -> list[LoanDTO]:
        with self._uow_factory() as uow:
            return [
                LoanDTO(
                    id=l.id,
                    name=l.name,
                    start_date=l.start_date,
                    principal_initial=l.principal_initial,
                    annual_interest_rate=l.annual_interest_rate,
                    regular_payment=l.regular_payment,
                    payment_timing=l.payment_timing.value,
                    account_id=l.account_id,
                    status=l.status.value,
                    notes=l.notes,
                )
                for l in uow.loans.list_all()
            ]

    def upsert_loan(self, dto: LoanDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.loans.get(dto.id) if dto.id else None
            obj = obj or Loan()
            obj.name = dto.name
            obj.start_date = dto.start_date
            obj.principal_initial = dto.principal_initial
            obj.annual_interest_rate = dto.annual_interest_rate
            obj.regular_payment = dto.regular_payment
            obj.payment_timing = PaymentTiming(dto.payment_timing)
            obj.account_id = dto.account_id
            obj.status = LoanStatus(dto.status)
            obj.notes = dto.notes
            uow.loans.upsert(obj)
            return obj.id

    def set_status(self, loan_id: int, status: str) -> None:
        with self._uow_factory() as uow:
            uow.loans.set_status(loan_id, LoanStatus(status))


    # Backwards-compat alias (UI used older name)
    def set_loan_status(self, loan_id: int, status: str) -> None:
        """Alias for set_status (for UI/Presenter compatibility)."""
        self.set_status(loan_id, status)

    def close_loan(self, loan_id: int) -> None:
        """Convenience method: close loan."""
        self.set_status(loan_id, "CLOSED")

    def reopen_loan(self, loan_id: int) -> None:
        """Convenience method: reopen loan."""
        self.set_status(loan_id, "ACTIVE")

    def delete_loan(self, loan_id: int) -> None:
        with self._uow_factory() as uow:
            uow.loans.delete(loan_id)

    # -------------------- events --------------------
    def get_event(self, event_id: int) -> LoanEventDTO | None:
        with self._uow_factory() as uow:
            e = uow.loan_events.get(event_id)
            if not e:
                return None
            settings = _parse_settings(e.notes)
            return LoanEventDTO(
                id=e.id,
                loan_id=e.loan_id,
                event_date=e.event_date,
                event_type=e.event_type.value,
                amount=e.amount,
                new_regular_payment=e.new_regular_payment,
                new_annual_interest_rate=e.new_annual_interest_rate,
                notes=_strip_settings(e.notes),
                override_account_id=int(settings["account_id"]) if "account_id" in settings else None,
                override_payment_timing=settings.get("payment_timing"),
            )

    def add_event(self, dto: LoanEventDTO) -> int:
        return self.upsert_event(dto)

    def upsert_event(self, dto: LoanEventDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.loan_events.get(dto.id) if dto.id else None
            obj = obj or LoanEvent()

            obj.loan_id = dto.loan_id
            obj.event_date = dto.event_date
            obj.year = dto.event_date.year
            obj.month = dto.event_date.month
            obj.event_type = LoanEventType(dto.event_type)
            obj.amount = dto.amount
            obj.new_regular_payment = dto.new_regular_payment
            obj.new_annual_interest_rate = dto.new_annual_interest_rate

            obj.notes = _apply_settings(
                dto.notes,
                override_account_id=dto.override_account_id,
                override_payment_timing=dto.override_payment_timing,
            )

            uow.loan_events.upsert(obj)
            return obj.id

    def list_events(self, loan_id: int) -> list[LoanEventDTO]:
        with self._uow_factory() as uow:
            out: list[LoanEventDTO] = []
            for e in uow.loan_events.list_by_loan(loan_id):
                settings = _parse_settings(e.notes)
                out.append(
                    LoanEventDTO(
                        id=e.id,
                        loan_id=e.loan_id,
                        event_date=e.event_date,
                        event_type=e.event_type.value,
                        amount=e.amount,
                        new_regular_payment=e.new_regular_payment,
                        new_annual_interest_rate=e.new_annual_interest_rate,
                        notes=_strip_settings(e.notes),
                        override_account_id=int(settings["account_id"]) if "account_id" in settings else None,
                        override_payment_timing=settings.get("payment_timing"),
                    )
                )
            return out

    def has_event_in_period(self, loan_id: int, period: Period) -> bool:
        with self._uow_factory() as uow:
            ev = uow.loan_events.list_for_loan_month(loan_id, period.year, period.month)
            return bool(ev)

    def delete_event(self, event_id: int) -> None:
        with self._uow_factory() as uow:
            uow.loan_events.delete(event_id)

    def get_effective_settings(self, loan_id: int, period: Period) -> dict:
        """Determines account + timing taking events up to and including period into account."""
        with self._uow_factory() as uow:
            loan = uow.loans.get(loan_id)
            if not loan:
                return {"account_id": None, "payment_timing": None}

            account_id = loan.account_id
            payment_timing = loan.payment_timing.value

            events = uow.loan_events.list_for_loan_until(loan_id, period, include_current=True)
            for e in events:
                s = _parse_settings(e.notes)
                if "account_id" in s:
                    try:
                        account_id = int(s["account_id"])
                    except Exception:
                        pass
                if "payment_timing" in s:
                    try:
                        payment_timing = PaymentTiming(s["payment_timing"]).value
                    except Exception:
                        pass

            return {"account_id": account_id, "payment_timing": payment_timing}

    def get_month_status(self, loan_id: int, period: Period) -> dict:
        with self._uow_factory() as uow:
            loan = uow.loans.get(loan_id)
            if not loan:
                return {
                    "open_before": Decimal("0"),
                    "payment": Decimal("0"),
                    "extra": Decimal("0"),
                    "open_after": Decimal("0"),
                }

            try:
                ev_rows = uow.loan_events.list_for_loan_until(loan_id, period)
            except AttributeError:
                ev_rows = uow.loan_events.list_by_loan(loan_id)

            events = [
                {
                    "event_type": e.event_type.value,
                    "year": e.year,
                    "month": e.month,
                    "amount": e.amount,
                    "new_regular_payment": e.new_regular_payment,
                }
                for e in ev_rows
            ]

            st = compute_month_status(
                principal_initial=loan.principal_initial,
                regular_payment=loan.regular_payment,
                events=events,
                year=period.year,
                month=period.month,
            )
            return {
                "open_before": st.open_before,
                "payment": st.payment,
                "extra": st.extra,
                "open_after": st.open_after,
            }
