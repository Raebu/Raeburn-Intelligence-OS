from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import JSON, Column, delete
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


class SnapshotRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    snapshot_type: str = Field(index=True)
    captured_at: datetime = Field(index=True)
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class RelationRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    source_type: str = Field(index=True)
    source_id: str = Field(index=True)
    relation: str = Field(index=True)
    target_type: str = Field(index=True)
    target_id: str = Field(index=True)
    confidence: float = 1.0
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    observed_at: datetime


class PersonRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    name: str
    role: str | None = Field(default=None, index=True)
    role_family: str | None = Field(default=None, index=True)
    appointed_on: str | None = None
    resigned_on: str | None = None
    confidence: float = 1.0
    source_url: str | None = None
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime


class WatchlistRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    company_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    signal_kinds: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    minimum_strength: float = 0.5
    active: bool = True
    created_at: datetime
    updated_at: datetime


class AlertRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    watchlist_id: str = Field(index=True)
    company_id: str = Field(index=True)
    signal_kind: str = Field(index=True)
    strength: float
    summary: str
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(index=True)
    acknowledged: bool = False


class ActionRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    opportunity_kind: str = Field(index=True)
    action_type: str = Field(index=True)
    status: str = Field(default="proposed", index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime
    approved_at: datetime | None = None
    completed_at: datetime | None = None


class OutcomeRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    company_id: str = Field(index=True)
    action_id: str | None = Field(default=None, index=True)
    opportunity_kind: str = Field(index=True)
    outcome: str = Field(index=True)
    revenue_gbp: float | None = None
    notes: str | None = None
    created_at: datetime


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


def _detach(session: Session, row):
    if row is not None:
        session.expunge(row)
    return row


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
        return _detach(session, row)


def save_evidence(rows: list[EvidenceRow]) -> None:
    if not rows:
        return
    with session_scope() as session:
        for row in rows:
            existing = session.get(EvidenceRow, row.id)
            if existing:
                for key, value in row.model_dump().items():
                    setattr(existing, key, value)
            else:
                session.add(row)
        session.commit()


def replace_signals(company_id: str, rows: list[SignalRow]) -> None:
    with session_scope() as session:
        session.exec(delete(SignalRow).where(SignalRow.company_id == company_id))
        session.flush()
        session.add_all(rows)
        session.commit()


def get_company(company_id: str) -> CompanyRow | None:
    with session_scope() as session:
        return _detach(session, session.get(CompanyRow, company_id))


def get_company_by_number(company_number: str) -> CompanyRow | None:
    with session_scope() as session:
        row = session.exec(
            select(CompanyRow).where(CompanyRow.company_number == company_number.upper())
        ).first()
        return _detach(session, row)


def list_companies(limit: int = 100) -> list[CompanyRow]:
    with session_scope() as session:
        rows = list(session.exec(select(CompanyRow).limit(limit)).all())
        for row in rows:
            session.expunge(row)
        return rows


def list_evidence(company_id: str) -> list[EvidenceRow]:
    with session_scope() as session:
        rows = list(
            session.exec(
                select(EvidenceRow)
                .where(EvidenceRow.company_id == company_id)
                .order_by(EvidenceRow.observed_at.desc())
            ).all()
        )
        for row in rows:
            session.expunge(row)
        return rows


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
        return _detach(session, row)


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
        return _detach(session, row)


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
        return _detach(session, row)


def get_action(action_id: str) -> ActionRow | None:
    with session_scope() as session:
        return _detach(session, session.get(ActionRow, action_id))


def list_actions(limit: int = 100) -> list[ActionRow]:
    with session_scope() as session:
        rows = list(session.exec(select(ActionRow).order_by(ActionRow.created_at.desc()).limit(limit)).all())
        for row in rows:
            session.expunge(row)
        return rows


def save_outcome(row: OutcomeRow) -> OutcomeRow:
    with session_scope() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return _detach(session, row)


def list_outcomes(limit: int = 1000) -> list[OutcomeRow]:
    with session_scope() as session:
        rows = list(session.exec(select(OutcomeRow).order_by(OutcomeRow.created_at.desc()).limit(limit)).all())
        for row in rows:
            session.expunge(row)
        return rows
