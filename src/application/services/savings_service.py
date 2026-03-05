# finanzmanager/application/services/savings_service.py
from __future__ import annotations

from src.application.dto.savings import SavingsContributionDTO, SavingsGoalDTO
from src.infrastructure.db.orm_models import SavingsContribution, SavingsGoal, SavingsGoalType
from src.infrastructure.unit_of_work import UnitOfWork


class SavingsService:
    def __init__(self, uow_factory=UnitOfWork) -> None:
        self._uow_factory = uow_factory

    def list_goals(self) -> list[SavingsGoalDTO]:
        with self._uow_factory() as uow:
            out: list[SavingsGoalDTO] = []
            for g in uow.savings_goals.list_all():
                out.append(
                    SavingsGoalDTO(
                        id=g.id,
                        name=g.name,
                        type=g.type.value,
                        linked_to_source=g.linked_to_source,
                        notes=g.notes,
                    )
                )
            return out

    def upsert_goal(self, dto: SavingsGoalDTO) -> int:
        with self._uow_factory() as uow:
            obj = uow.savings_goals.get(dto.id) if dto.id else None
            obj = obj or SavingsGoal()

            obj.name = dto.name
            obj.type = SavingsGoalType(dto.type)
            obj.linked_to_source = dto.linked_to_source
            obj.notes = dto.notes

            uow.savings_goals.upsert(obj)
            return obj.id

    def add_contribution(self, dto: SavingsContributionDTO) -> int:
        with self._uow_factory() as uow:
            obj = SavingsContribution()
            obj.goal_id = dto.goal_id
            obj.year = dto.year
            obj.month = dto.month
            obj.amount = dto.amount
            obj.account_id = dto.account_id
            obj.notes = dto.notes

            uow.savings_contribs.upsert(obj)
            return obj.id

    def list_contributions(self, goal_id: int) -> list[SavingsContributionDTO]:
        with self._uow_factory() as uow:
            out: list[SavingsContributionDTO] = []
            for c in uow.savings_contribs.list_for_goal(goal_id):
                out.append(
                    SavingsContributionDTO(
                        id=c.id,
                        goal_id=c.goal_id,
                        year=c.year,
                        month=c.month,
                        amount=c.amount,
                        account_id=c.account_id,
                        notes=c.notes,
                    )
                )
            return out
