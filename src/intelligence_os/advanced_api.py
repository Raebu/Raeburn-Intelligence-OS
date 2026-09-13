from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .accounts import enrich_latest_accounts
from .advanced import (
    analyst,
    approve_action,
    capture_snapshot,
    create_watchlist,
    evaluate_watchlists,
    feedback_summary,
    financial_trends,
    graph,
    infer_people,
    peer_anomalies,
    propose_actions,
    record_outcome,
    snapshot_changes,
    tender_score,
)
from .db import list_actions, list_alerts, list_people, list_watchlists
from .graph_engine import rebuild_enriched_graph
from .learning import calibrated_opportunities, calibration
from .ownership import enrich_ownership
from .uk import ExternalServiceError

router = APIRouter(prefix="/v1", tags=["advanced-intelligence"])


class AnalystRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class WatchlistRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company_ids: list[str]
    signal_kinds: list[str] = []
    minimum_strength: float = Field(default=0.5, ge=0, le=1)


class TenderScoreRequest(BaseModel):
    record: dict[str, Any]
    profile: dict[str, Any] | None = None


class OutcomeRequest(BaseModel):
    company_id: str
    opportunity_kind: str
    outcome: str
    action_id: str | None = None
    revenue_gbp: float | None = None
    notes: str | None = None


@router.post("/companies/{company_id}/snapshots")
def create_snapshot(company_id: str) -> dict:
    try:
        return capture_snapshot(company_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc


@router.get("/companies/{company_id}/changes")
def changes(company_id: str) -> dict:
    return snapshot_changes(company_id)


@router.post("/companies/{company_id}/people/rebuild")
def people_rebuild(company_id: str) -> list[dict]:
    try:
        return infer_people(company_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc


@router.get("/companies/{company_id}/people")
def people(company_id: str) -> list[dict]:
    return [row.model_dump() for row in list_people(company_id)]


@router.post("/companies/{company_id}/ownership/enrich")
def ownership_enrich(company_id: str) -> dict:
    try:
        return enrich_ownership(company_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/companies/{company_id}/accounts/enrich")
def accounts_enrich(company_id: str) -> dict:
    try:
        return enrich_latest_accounts(company_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/companies/{company_id}/graph/rebuild")
def graph_rebuild(company_id: str) -> dict:
    try:
        return rebuild_enriched_graph(company_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc


@router.get("/graph/{entity_type}/{entity_id}")
def read_graph(entity_type: str, entity_id: str) -> dict:
    return graph(entity_type, entity_id)


@router.get("/companies/{company_id}/financial-trends")
def company_financial_trends(company_id: str) -> dict:
    return financial_trends(company_id)


@router.get("/companies/{company_id}/anomalies")
def company_anomalies(company_id: str) -> dict:
    try:
        return peer_anomalies(company_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc


@router.post("/procurement/score")
def procurement_score(request: TenderScoreRequest) -> dict:
    return tender_score(request.record, request.profile)


@router.post("/watchlists")
def watchlist_create(request: WatchlistRequest) -> dict:
    return create_watchlist(
        request.name,
        request.company_ids,
        request.signal_kinds,
        request.minimum_strength,
    )


@router.get("/watchlists")
def watchlists() -> list[dict]:
    return [row.model_dump() for row in list_watchlists()]


@router.post("/watchlists/evaluate")
def watchlists_evaluate() -> list[dict]:
    return evaluate_watchlists()


@router.get("/alerts")
def alerts() -> list[dict]:
    return [row.model_dump() for row in list_alerts()]


@router.post("/companies/{company_id}/analyst")
def ask_analyst(company_id: str, request: AnalystRequest) -> dict:
    try:
        return analyst(company_id, request.question)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc


@router.post("/companies/{company_id}/actions/propose")
def actions_propose(company_id: str, minimum_score: float = 60.0) -> list[dict]:
    try:
        return propose_actions(company_id, minimum_score)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc


@router.get("/actions")
def actions() -> list[dict]:
    return [row.model_dump() for row in list_actions()]


@router.post("/actions/{action_id}/approve")
def action_approve(action_id: str) -> dict:
    try:
        return approve_action(action_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Action not found") from exc


@router.post("/outcomes")
def outcome_create(request: OutcomeRequest) -> dict:
    return record_outcome(
        company_id=request.company_id,
        opportunity_kind=request.opportunity_kind,
        outcome=request.outcome,
        action_id=request.action_id,
        revenue_gbp=request.revenue_gbp,
        notes=request.notes,
    )


@router.get("/feedback")
def feedback() -> dict:
    return feedback_summary()


@router.get("/feedback/calibration")
def feedback_calibration() -> dict:
    return calibration()


@router.get("/companies/{company_id}/opportunities/calibrated")
def learned_opportunities(company_id: str) -> list[dict]:
    try:
        return calibrated_opportunities(company_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc
