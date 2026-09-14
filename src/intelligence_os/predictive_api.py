from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from .predictive_engine import (
    backtest, buyer_intent_graph, canonical_entity, company_similarity, corroboration,
    counterfactuals, decayed_signals, decision_makers, fused_signal, group_intelligence,
    incumbent_intelligence, intelligence_pack, leading_indicators, negative_intelligence,
    opportunity_clusters, opportunity_lifecycle, outcome_calibration, provenance_ledger,
    research_plan, technology_changes, temporal_graph,
)

router = APIRouter(prefix="/v1/intelligence", tags=["predictive-intelligence"])

@router.get("/{company_id}/pack")
def pack(company_id: str): return intelligence_pack(company_id)
@router.get("/{company_id}/identity")
def identity(company_id: str): return canonical_entity(company_id)
@router.get("/{company_id}/temporal-graph")
def graph(company_id: str): return temporal_graph(company_id)
@router.get("/{company_id}/fusion")
def fusion(company_id: str): return fused_signal(company_id)
@router.get("/{company_id}/predictions")
def predictions(company_id: str): return leading_indicators(company_id)
@router.get("/{company_id}/similar")
def similar(company_id: str, limit: int = Query(20, ge=1, le=100)): return company_similarity(company_id, limit)
@router.get("/{company_id}/buyer-intent")
def buyer_intent(company_id: str): return buyer_intent_graph(company_id)
@router.get("/{company_id}/decision-makers/{opportunity_kind}")
def people(company_id: str, opportunity_kind: str): return decision_makers(company_id, opportunity_kind)
@router.get("/{company_id}/technology-changes")
def technology(company_id: str): return technology_changes(company_id)
@router.get("/{company_id}/incumbents")
def incumbents(company_id: str): return incumbent_intelligence(company_id)
@router.get("/{company_id}/lifecycle")
def lifecycle(company_id: str): return opportunity_lifecycle(company_id)
@router.get("/calibration/outcomes")
def calibration(): return outcome_calibration()
@router.get("/{company_id}/negative")
def negative(company_id: str): return negative_intelligence(company_id)
@router.get("/{company_id}/corroboration")
def corroborate(company_id: str): return corroboration(company_id)
@router.get("/{company_id}/provenance")
def provenance(company_id: str): return provenance_ledger(company_id)
@router.get("/{company_id}/decay")
def decay(company_id: str): return decayed_signals(company_id)
@router.get("/{company_id}/counterfactuals")
def counterfactual(company_id: str): return counterfactuals(company_id)
@router.get("/{company_id}/research-plan")
def planner(company_id: str, budget: int = Query(5, ge=1, le=20)): return research_plan(company_id, budget)
@router.get("/{company_id}/clusters")
def clusters(company_id: str): return opportunity_clusters(company_id)
@router.get("/{company_id}/group")
def group(company_id: str): return group_intelligence(company_id)
@router.get("/{company_id}/backtest")
def historical_test(company_id: str, cutoff: datetime): return backtest(company_id, cutoff)
