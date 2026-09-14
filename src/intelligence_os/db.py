from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Iterator

from sqlalchemy import Column, JSON, delete
from sqlmodel import Field, Session, SQLModel, create_engine, select

from .config import get_settings
from .models import Company, Evidence, Signal


class CompanyRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_number: str | None = Field(default=None, index=True)
    name: str = Field(index=True)
    jurisdiction: str = "GB"
    status: str | None = None
    company_type: str | None = None
    incorporated_on: str | None = None
    sic_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    registered_office: dict = Field(default_factory=dict, sa_column=Column(JSON))
    website: str | None = None
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class EvidenceRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    source_id: str = Field(index=True)
    fact_type: str = Field(index=True)
    observed_at: datetime = Field(index=True)
    source_url: str | None = None
    value: dict = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: float = 1.0
    raw_reference: str | None = None


class SignalRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    kind: str = Field(index=True)
    title: str
    summary: str
    observed_at: datetime = Field(index=True)
    strength: float = 0.5
    confidence: float = 0.8
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))


class SnapshotRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    snapshot_type: str = Field(index=True)
    captured_at: datetime = Field(index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    payload_hash: str = Field(index=True)


class RelationRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    source_type: str = Field(index=True)
    source_id: str = Field(index=True)
    relation: str = Field(index=True)
    target_type: str = Field(index=True)
    target_id: str = Field(index=True)
    confidence: float = 0.8
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class PersonRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    name: str = Field(index=True)
    role: str
    role_family: str = Field(index=True)
    appointed_on: str | None = None
    resigned_on: str | None = None
    confidence: float = 0.8
    source_url: str | None = None
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class WatchlistRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    company_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    minimum_score: float = 70.0
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AlertRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    watchlist_id: str = Field(index=True)
    company_id: str = Field(index=True)
    opportunity_id: str | None = None
    title: str
    summary: str
    score: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    acknowledged: bool = False


class ActionRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    action_type: str = Field(index=True)
    status: str = Field(default="proposed", index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    approved_at: datetime | None = None
    executed_at: datetime | None = None


class OutcomeRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    outcome_type: str = Field(index=True)
    value: float = 1.0
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        _engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def upsert_company(company: Company) -> CompanyRow:
    row = CompanyRow(**company.model_dump())
    with session_scope() as session:
        existing = session.get(CompanyRow, row.id)
        if existing:
            for key, value in row.model_dump().items():
                setattr(existing, key, value)
            row = existing
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def get_company(company_id: str) -> CompanyRow | None:
    with session_scope() as session:
        row = session.get(CompanyRow, company_id)
        if row:
            session.expunge(row)
        return row


def list_companies(limit: int = 500) -> list[CompanyRow]:
    with session_scope() as session:
        rows = list(session.exec(select(CompanyRow).limit(limit)).all())
        for row in rows:
            session.expunge(row)
        return rows


def save_evidence(rows: list[EvidenceRow]) -> None:
    with session_scope() as session:
        for row in rows:
            existing = session.get(EvidenceRow, row.id)
            if existing:
                for key, value in row.model_dump().items():
                    setattr(existing, key, value)
            else:
                session.add(row)
        session.commit()


def list_evidence(company_id: str) -> list[EvidenceRow]:
    with session_scope() as session:
        rows = list(session.exec(select(EvidenceRow).where(EvidenceRow.company_id == company_id)).all())
        for row in rows:
            session.expunge(row)
        return rows


def replace_signals(company_id: str, rows: list[SignalRow]) -> None:
    with session_scope() as session:
        session.exec(delete(SignalRow).where(SignalRow.company_id == company_id))
        session.flush()
        session.add_all(rows)
        session.commit()


def list_signals(company_id: str) -> list[SignalRow]:
    with session_scope() as session:
        rows = list(session.exec(select(SignalRow).where(SignalRow.company_id == company_id)).all())
        for row in rows:
            session.expunge(row)
        return rows


def save_snapshot(row: SnapshotRow) -> SnapshotRow:
    with session_scope() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row


def list_snapshots(company_id: str, snapshot_type: str | None = None) -> list[SnapshotRow]:
    with session_scope() as session:
        statement = select(SnapshotRow).where(SnapshotRow.company_id == company_id)
        if snapshot_type:
            statement = statement.where(SnapshotRow.snapshot_type == snapshot_type)
        rows = list(session.exec(statement.order_by(SnapshotRow.captured_at.desc())).all())
        for row in rows:
            session.expunge(row)
        return rows


def replace_relations(source_type: str, source_id: str, rows: list[RelationRow]) -> None:
    with session_scope() as session:
        session.exec(
            delete(RelationRow).where(
                RelationRow.source_type == source_type,
                RelationRow.source_id == source_id,
            )
        )
        session.flush()
        session.add_all(rows)
        session.commit()


def list_relations(entity_type: str, entity_id: str) -> list[RelationRow]:
    with session_scope() as session:
        rows = list(
            session.exec(
                select(RelationRow).where(
                    (RelationRow.source_type == entity_type) & (RelationRow.source_id == entity_id)
                    | (RelationRow.target_type == entity_type) & (RelationRow.target_id == entity_id)
                )
            ).all()
        )
        for row in rows:
            session.expunge(row)
        return rows


def replace_people(company_id: str, rows: list[PersonRow]) -> None:
    with session_scope() as session:
        session.exec(delete(PersonRow).where(PersonRow.company_id == company_id))
        session.flush()
        session.add_all(rows)
        session.commit()


def list_people(company_id: str) -> list[PersonRow]:
    with session_scope() as session:
        rows = list(session.exec(select(PersonRow).where(PersonRow.company_id == company_id)).all())
        for row in rows:
            session.expunge(row)
        return rows


def save_watchlist(row: WatchlistRow) -> WatchlistRow:
    with session_scope() as session:
        existing = session.get(WatchlistRow, row.id)
        if existing:
            for key, value in row.model_dump().items():
                setattr(existing, key, value)
            row = existing
        session.add(row)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row


def list_watchlists() -> list[WatchlistRow]:
    with session_scope() as session:
        rows = list(session.exec(select(WatchlistRow)).all())
        for row in rows:
            session.expunge(row)
        return rows


def save_alerts(rows: list[AlertRow]) -> None:
    with session_scope() as session:
        for row in rows:
            existing = session.get(AlertRow, row.id)
            if existing:
                for key, value in row.model_dump().items():
                    setattr(existing, key, value)
            else:
                session.add(row)
        session.commit()


def list_alerts(limit: int = 100) -> list[AlertRow]:
    with session_scope() as session:
        rows = list(session.exec(select(AlertRow).order_by(AlertRow.created_at.desc()).limit(limit)).all())
        for row in rows:
            session.expunge(row)
        return rows


def save_action(row: ActionRow) -> ActionRow:
    with session_scope() as session:
        existing = session.get(ActionRow, row.id)
        if existing:
            for key, value in row.model_dump().items():
                setattr(existing, key, value)
            row = existing
        session.add(row)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row


def get_action(action_id: str) -> ActionRow | None:
    with session_scope() as session:
        row = session.get(ActionRow, action_id)
        if row:
            session.expunge(row)
        return row


def list_actions(company_id: str | None = None, limit: int = 100) -> list[ActionRow]:
    with session_scope() as session:
        statement = select(ActionRow)
        if company_id:
            statement = statement.where(ActionRow.company_id == company_id)
        rows = list(session.exec(statement.order_by(ActionRow.created_at.desc()).limit(limit)).all())
        for row in rows:
            session.expunge(row)
        return rows


def save_outcome(row: OutcomeRow) -> OutcomeRow:
    with session_scope() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row


def list_outcomes(company_id: str | None = None, limit: int = 500) -> list[OutcomeRow]:
    with session_scope() as session:
        statement = select(OutcomeRow)
        if company_id:
            statement = statement.where(OutcomeRow.company_id == company_id)
        rows = list(session.exec(statement.order_by(OutcomeRow.occurred_at.desc()).limit(limit)).all())
        for row in rows:
            session.expunge(row)
        return rows


def company_to_model(row: CompanyRow) -> Company:
    return Company(**row.model_dump())


def evidence_to_model(row: EvidenceRow) -> Evidence:
    return Evidence(**row.model_dump())


def signal_to_model(row: SignalRow) -> Signal:
    return Signal(**row.model_dump())
