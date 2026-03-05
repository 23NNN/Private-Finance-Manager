# src/infrastructure/unit_of_work.py
from __future__ import annotations

from sqlalchemy.orm import Session

from src.infrastructure.db.engine import SessionLocal
from src.infrastructure.repositories.accounts import AccountRepository
from src.infrastructure.repositories.employers import EmployerRepository
from src.infrastructure.repositories.expenses import CategoryRepository, ExpenseRecurringRepository, ExpenseVariableRepository
from src.infrastructure.repositories.import_runs import ImportRunRepository
from src.infrastructure.repositories.income_fixed import IncomeFixedRepository
from src.infrastructure.repositories.income_hourly import IncomeHourlyRepository
from src.infrastructure.repositories.income_special import IncomeSpecialRepository
from src.infrastructure.repositories.loan_events import LoanEventRepository
from src.infrastructure.repositories.loans import LoanRepository
from src.infrastructure.repositories.pay_rules import PayRuleRepository
from src.infrastructure.repositories.savings import SavingsContributionRepository, SavingsGoalRepository, SavingsRuleRepository
from src.infrastructure.repositories.app_settings import AppSettingRepository
from src.infrastructure.repositories.i18n_strings import I18nStringRepository

__all__ = ["UnitOfWork"]


class UnitOfWork:
    """Transaction boundary + repository registry."""

    def __init__(self) -> None:
        self._session: Session | None = None

    def __enter__(self) -> "UnitOfWork":
        self._session = SessionLocal()

        self.accounts = AccountRepository(self._session)
        self.employers = EmployerRepository(self._session)
        self.pay_rules = PayRuleRepository(self._session)

        self.categories = CategoryRepository(self._session)
        self.expense_categories = self.categories  # Alias (robust)

        self.expense_recurring = ExpenseRecurringRepository(self._session)
        self.expense_variable = ExpenseVariableRepository(self._session)

        self.income_fixed = IncomeFixedRepository(self._session)
        self.income_hourly = IncomeHourlyRepository(self._session)
        self.income_special = IncomeSpecialRepository(self._session)

        self.loans = LoanRepository(self._session)
        self.loan_events = LoanEventRepository(self._session)

        self.savings_goals = SavingsGoalRepository(self._session)
        self.savings_rules = SavingsRuleRepository(self._session)
        self.savings_contributions = SavingsContributionRepository(self._session)

        self.app_settings = AppSettingRepository(self._session)
        self.i18n_strings = I18nStringRepository(self._session)

        self.import_runs = ImportRunRepository(self._session)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._session is not None
        try:
            if exc_type is None:
                self._session.commit()
            else:
                self._session.rollback()
        finally:
            self._session.close()
            self._session = None
