from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import Column, JSON
from sqlmodel import Field, Session, SQLModel, create_engine, select

from .config import get_settings


class CompanyRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    company_number: str | None = Field(default=None, index=True, unique=True)
    jurisdiction: str = "GB"
    status: str | None = None
    company_type: str | None = None
    sic_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    registered_address: dict = Field(default_factory=dict, sa_column=Column(JSON))
    incorporated_at: datetime | None = None
    updated_at: datetime


class EvidenceRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    source_id: str = Field(index=True)
    fact_type: str = Field(index=True)
    observed_at: datetime
    source_url: str | None = None
    value: dict = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: float = 1.0
    raw_reference: str | None = None


class SignalRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    kind: str = Field(index=True)
    strength: float
    confidence: float
    detected_at: datetime
    explanation: str | None = None
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))


def _engine():
    settings = get_settings()
    args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=args, pool_pre_ping=True)


engine = _engine()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def session_scope():
    with Session(engine) as session:
        yield session


def upsert_company(row: CompanyRow) -> CompanyRow:
    with session_scope() as session:
        existing = session.get(CompanyRow, row.id)
        if existing is None and row.company_number:
            existing = session.exec(
                select(CompanyRow).where(CompanyRow.company_number == row.company_number)
            ).first()
        if existing:
            for key, value in row.model_dump().items():
                setattr(existing, key, value)
            row = existing
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def save_evidence(rows: list[EvidenceRow]) -> None:
    if not rows:
        return
    with session_scope() as session:
        for row in rows:
            if session.get(EvidenceRow, row.id) is None:
                session.add(row)
        session.commit()


def replace_signals(company_id: str, rows: list[SignalRow]) -> None:
    with session_scope() as session:
        existing = session.exec(select(SignalRow).where(SignalRow.company_id == company_id)).all()
        for row in existing:
            session.delete(row)
        session.add_all(rows)
        session.commit()


def get_company(company_id: str) -> CompanyRow | None:
    with session_scope() as session:
        return session.get(CompanyRow, company_id)


def get_company_by_number(company_number: str) -> CompanyRow | None:
    with session_scope() as session:
        return session.exec(
            select(CompanyRow).where(CompanyRow.company_number == company_number.upper())
        ).first()


def list_companies(limit: int = 100) -> list[CompanyRow]:
    with session_scope() as session:
        return list(session.exec(select(CompanyRow).limit(limit)).all())


def list_evidence(company_id: str) -> list[EvidenceRow]:
    with session_scope() as session:
        return list(
            session.exec(
                select(EvidenceRow)
                .where(EvidenceRow.company_id == company_id)
                .order_by(EvidenceRow.observed_at.desc())
            ).all()
        )


def list_signals(company_id: str) -> list[SignalRow]:
    with session_scope() as session:
        return list(session.exec(select(SignalRow).where(SignalRow.company_id == company_id)).all())
