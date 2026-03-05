from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.orm_models import Base, Account
from src.infrastructure.repositories.accounts import AccountRepository


def test_account_repository_crud(tmp_path: Path):
    db = tmp_path / "t.db"
    engine = create_engine(f"sqlite:///{db}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False, autoflush=False)

    with Session() as s:
        repo = AccountRepository(s)
        a = Account(account_name="Giro", label="GIRO", bank_name="Bank", iban=None, role_income=True, role_debit=True)
        repo.upsert(a)
        s.commit()
        assert a.id is not None

    with Session() as s:
        repo = AccountRepository(s)
        rows = repo.list_all()
        assert len(rows) == 1
        assert rows[0].label == "GIRO"
