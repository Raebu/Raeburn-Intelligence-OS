from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


def utcnow() -> datetime:
    return datetime.now(UTC)


class OpportunityKind(StrEnum):
    AUTOMATION = "automation"
    CONSULTING = "consulting"
    RECRUITMENT = "recruitment"
    SOFTWARE = "software"
    PROCUREMENT = "procurement"
    MA = "ma"
    MARKET_ENTRY = "market_entry"


class SignalKind(StrEnum):
    HIRING_GROWTH = "hiring_growth"
    TECH_HIRING = "tech_hiring"
    PUBLIC_CONTRACT_WIN = "public_contract_win"
    REVENUE_GROWTH = "revenue_growth"
    HEADCOUNT_GROWTH = "headcount_growth"
    NEW_LOCATION = "new_location"
    DIRECTOR_CHANGE = "director_change"
    FUNDING_EVENT = "funding_event"
    AUTOMATION_GAP = "automation_gap"
    DIGITAL_TRANSFORMATION = "digital_transformation"
    PROCUREMENT_ACTIVITY = "procurement_activity"
    DISTRESS = "distress"
    MARKET_GROWTH = "market_growth"


class SourceRecord(BaseModel):
    id: str
    name: str
    canonical_url: HttpUrl
    category: str
    jurisdiction: str | None = None
    licence: str | None = None
    commercial_reuse: bool | None = None
    refresh_cadence: str | None = None
    collection_method: str = "manual"
    entity_types: list[str] = Field(default_factory=list)
    supported_signals: list[SignalKind] = Field(default_factory=list)
    notes: str | None = None


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str
    observed_at: datetime = Field(default_factory=utcnow)
    source_url: HttpUrl | None = None
    subject_id: str
    fact_type: str
    value: Any
    confidence: float = Field(default=1.0, ge=0, le=1)
    raw_reference: str | None = None


class Company(BaseModel):
    id: str
    name: str
    company_number: str | None = None
    jurisdiction: str = "GB"
    website: HttpUrl | None = None
    industry: str | None = None
    employee_count: int | None = Field(default=None, ge=0)
    active: bool = True
    aliases: list[str] = Field(default_factory=list)


class SignalInput(BaseModel):
    kind: SignalKind
    strength: float = Field(ge=0, le=1)
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class Signal(SignalInput):
    id: str = Field(default_factory=lambda: str(uuid4()))
    company_id: str
    detected_at: datetime = Field(default_factory=utcnow)
    explanation: str | None = None


class OpportunityScoreRequest(BaseModel):
    company_id: str
    signals: list[SignalInput]
    kind: OpportunityKind | None = None


class ScoreComponent(BaseModel):
    signal: SignalKind
    weight: float
    strength: float
    confidence: float
    contribution: float


class Opportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    company_id: str
    kind: OpportunityKind
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    rationale: str
    components: list[ScoreComponent]
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
