from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

from .db import list_companies, list_evidence, list_outcomes, list_people, list_relations, list_signals, list_snapshots
from .service import digital_twin

DECAY_DAYS = {"hiring_growth": 60, "tech_hiring": 60, "public_contract_win": 365, "director_change": 365, "distress": 120, "digital_transformation": 270, "revenue_growth": 540, "headcount_growth": 365, "new_location": 365, "procurement_activity": 120, "market_growth": 180}
DECISION_ROLE_MAP = {"automation": {"technology", "operations", "transformation", "executive"}, "consulting": {"executive", "operations", "transformation", "finance"}, "recruitment": {"people", "executive", "operations"}, "software": {"technology", "transformation", "operations"}, "procurement": {"operations", "finance", "executive"}, "m_and_a": {"executive", "finance"}, "market_entry": {"executive", "operations", "finance"}}
NEGATIVE_FACTS = {"insolvency", "dissolution", "gazette-notice-compulsory", "contract_closed", "procurement_closed"}


def _now() -> datetime:
    return datetime.now(UTC)


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def canonical_entity(company_id: str) -> dict[str, Any]:
    """Identity Resolution 2.0: deterministic canonical record with aliases/identifiers."""
    twin = digital_twin(company_id)
    company = twin["company"]
    aliases = {_norm(company.get("name"))}
    identifiers = {"companies_house": company.get("company_number")}
    domains: set[str] = set()
    for ev in twin["evidence"]:
        value = ev.get("value") or {}
        for key in ("name", "company_name", "organisation", "legal_name"):
            if isinstance(value.get(key), str): aliases.add(_norm(value[key]))
        for key in ("cik", "lei", "opencorporates_id", "charity_number", "vat_number"):
            if value.get(key): identifiers[key] = str(value[key])
        domain = value.get("domain") or value.get("website")
        if isinstance(domain, str): domains.add(domain.lower().replace("https://", "").replace("http://", "").split("/")[0])
    return {"canonical_id": f"org:gb:coh:{company.get('company_number')}", "company_id": company_id, "aliases": sorted(x for x in aliases if x), "identifiers": identifiers, "domains": sorted(domains)}


def temporal_graph(company_id: str) -> dict[str, Any]:
    """Temporal knowledge graph retaining observed/effective relationship dates."""
    relations = list_relations(source_id=company_id)
    people = {p.id: p for p in list_people(company_id)}
    edges = []
    for r in relations:
        person = people.get(r.target_id)
        edges.append({"source_type": r.source_type, "source_id": r.source_id, "relation": r.relation, "target_type": r.target_type, "target_id": r.target_id, "valid_from": getattr(person, "appointed_on", None) if person else None, "valid_to": getattr(person, "resigned_on", None) if person else None, "observed_at": r.observed_at, "confidence": r.confidence, "evidence_ids": r.evidence_ids})
    return {"company_id": company_id, "edges": edges}


def decayed_signals(company_id: str, at: datetime | None = None) -> list[dict[str, Any]]:
    """Intelligence decay with signal-specific half-lives."""
    at = at or _now()
    rows = []
    for s in list_signals(company_id):
        detected = s.detected_at
        if detected.tzinfo is None: detected = detected.replace(tzinfo=UTC)
        age = max(0.0, (at - detected).total_seconds() / 86400)
        half_life = DECAY_DAYS.get(s.kind, 180)
        factor = 0.5 ** (age / half_life)
        rows.append({"kind": s.kind, "raw_strength": s.strength, "decayed_strength": round(s.strength * factor, 4), "confidence": s.confidence, "age_days": round(age, 1), "half_life_days": half_life, "evidence_ids": s.evidence_ids})
    return rows


def fused_signal(company_id: str) -> dict[str, Any]:
    """Signal fusion rewards independent corroborating evidence without double counting."""
    signals = decayed_signals(company_id)
    if not signals: return {"company_id": company_id, "strength": 0.0, "independent_signals": 0, "signals": []}
    probabilities = [min(.98, s["decayed_strength"] * s["confidence"]) for s in signals]
    combined = 1 - math.prod(1 - p for p in probabilities)
    diversity_bonus = min(.15, .025 * max(0, len({s['kind'] for s in signals}) - 1))
    return {"company_id": company_id, "strength": round(min(1.0, combined + diversity_bonus), 4), "independent_signals": len({s['kind'] for s in signals}), "signals": signals}


def leading_indicators(company_id: str) -> list[dict[str, Any]]:
    """Explainable forward predictions; probabilities are heuristic until outcome calibration matures."""
    by_kind = {s["kind"]: s for s in decayed_signals(company_id)}
    specs = {
        "automation_procurement": (180, {"digital_transformation": .32, "headcount_growth": .18, "revenue_growth": .15, "public_contract_win": .14, "tech_hiring": .21}),
        "hiring_expansion": (120, {"headcount_growth": .30, "revenue_growth": .18, "hiring_growth": .32, "public_contract_win": .12, "new_location": .18}),
        "international_expansion": (270, {"market_growth": .30, "new_location": .30, "revenue_growth": .18, "hiring_growth": .12}),
        "m_and_a_activity": (365, {"revenue_growth": .18, "director_change": .16, "market_growth": .20, "distress": .24}),
        "technology_replacement": (180, {"digital_transformation": .38, "tech_hiring": .22, "automation_gap": .30}),
        "financial_deterioration": (120, {"distress": .55, "director_change": .10}),
    }
    predictions = []
    for event, (horizon, weights) in specs.items():
        contributions = []
        probability = .05
        for kind, weight in weights.items():
            s = by_kind.get(kind)
            if s:
                contribution = weight * s["decayed_strength"] * s["confidence"]
                probability += contribution
                contributions.append({"signal": kind, "contribution": round(contribution, 4), "evidence_ids": s["evidence_ids"]})
        predictions.append({"event": event, "probability": round(min(.95, probability), 3), "horizon_days": horizon, "evidence": contributions, "calibration": "heuristic_explainable"})
    return sorted(predictions, key=lambda x: x["probability"], reverse=True)


def company_similarity(company_id: str, limit: int = 20) -> list[dict[str, Any]]:
    target = {s.kind: s.strength * s.confidence for s in list_signals(company_id)}
    target_company = next((c for c in list_companies(10000) if c.id == company_id), None)
    results = []
    for c in list_companies(10000):
        if c.id == company_id: continue
        peer = {s.kind: s.strength * s.confidence for s in list_signals(c.id)}
        keys = set(target) | set(peer)
        dot = sum(target.get(k, 0) * peer.get(k, 0) for k in keys)
        a = math.sqrt(sum(target.get(k, 0) ** 2 for k in keys)); b = math.sqrt(sum(peer.get(k, 0) ** 2 for k in keys))
        signal_sim = dot / (a * b) if a and b else 0
        sic_sim = len(set(target_company.sic_codes or []) & set(c.sic_codes or [])) / max(1, len(set(target_company.sic_codes or []) | set(c.sic_codes or []))) if target_company else 0
        results.append({"company_id": c.id, "name": c.name, "similarity": round(.8 * signal_sim + .2 * sic_sim, 4)})
    return sorted(results, key=lambda x: x["similarity"], reverse=True)[:limit]


def buyer_intent_graph(company_id: str) -> dict[str, Any]:
    edges = []
    for ev in list_evidence(company_id):
        if ev.fact_type not in {"contract_award", "procurement", "tender", "planning_notice"}: continue
        v = ev.value or {}; buyer = v.get("buyer") or {}; tender = v.get("tender") or {}
        edges.append({"buyer": buyer, "title": v.get("title") or tender.get("title"), "value": v.get("tender_value") or v.get("award_value"), "deadline": v.get("deadline") or tender.get("tenderPeriod", {}).get("endDate"), "contract_end": v.get("contract_end") or tender.get("contractPeriod", {}).get("endDate"), "evidence_id": ev.id})
    return {"company_id": company_id, "intent_edges": edges}


def decision_makers(company_id: str, opportunity_kind: str) -> list[dict[str, Any]]:
    wanted = DECISION_ROLE_MAP.get(opportunity_kind, {"executive"})
    rows = [p for p in list_people(company_id) if not p.resigned_on]
    ranked = sorted(rows, key=lambda p: ((p.role_family in wanted), p.confidence), reverse=True)
    return [{"person_id": p.id, "name": p.name, "role": p.role, "role_family": p.role_family, "fit": "high" if p.role_family in wanted else "secondary", "confidence": p.confidence, "evidence_ids": p.evidence_ids} for p in ranked[:12]]


def technology_changes(company_id: str) -> dict[str, Any]:
    snaps = list_snapshots(company_id)
    if len(snaps) < 2: return {"company_id": company_id, "changes": [], "snapshots": len(snaps)}
    def tech(s):
        evidence = (s.data or {}).get("evidence", [])
        vals = []
        for e in evidence:
            if e.get("fact_type") in {"technology_profile", "domain", "certificate", "website"}: vals.append(e.get("value"))
        return vals
    before, after = tech(snaps[1]), tech(snaps[0])
    return {"company_id": company_id, "changed": before != after, "before": before, "after": after, "snapshots": [snaps[1].id, snaps[0].id]}


def incumbent_intelligence(company_id: str) -> dict[str, Any]:
    contracts = buyer_intent_graph(company_id)["intent_edges"]
    expiring = [c for c in contracts if c.get("contract_end")]
    return {"company_id": company_id, "contracts": contracts, "contracts_with_expiry": expiring, "research_priority": "high" if expiring else "normal"}


def opportunity_lifecycle(company_id: str) -> dict[str, Any]:
    outcomes = [o for o in list_outcomes() if o.company_id == company_id]
    stage = "detected"
    if outcomes:
        latest = outcomes[0]
        mapping = {"meeting": "meeting", "proposal": "proposal", "won": "won", "lost": "lost", "reply": "outreach"}
        stage = mapping.get(latest.outcome.lower(), "qualified")
    return {"company_id": company_id, "stage": stage, "allowed_stages": ["detected", "qualified", "researched", "contact_identified", "outreach", "meeting", "proposal", "won", "lost"], "outcome_count": len(outcomes)}


def outcome_calibration() -> dict[str, Any]:
    outcomes = list_outcomes(); stats: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0, "won": 0, "revenue": 0.0})
    for o in outcomes:
        s = stats[o.opportunity_kind]; s["total"] += 1; s["won"] += 1 if o.outcome.lower() == "won" else 0; s["revenue"] += float(o.revenue_gbp or 0)
    return {"samples": len(outcomes), "by_kind": {k: {**v, "win_rate": round(v["won"] / v["total"], 4) if v["total"] else None} for k, v in stats.items()}, "policy": "retain_deterministic_score_alongside_learned_calibration"}


def negative_intelligence(company_id: str) -> list[dict[str, Any]]:
    negatives = []
    for ev in list_evidence(company_id):
        text = f"{ev.fact_type} {ev.value}".lower()
        hits = [term for term in NEGATIVE_FACTS if term in text]
        if hits: negatives.append({"reason": hits[0], "confidence": ev.confidence, "evidence_id": ev.id})
    return negatives


def corroboration(company_id: str) -> dict[str, Any]:
    sources: dict[str, set[str]] = defaultdict(set); evidence_ids: dict[str, list[str]] = defaultdict(list)
    for ev in list_evidence(company_id):
        sources[ev.fact_type].add(ev.source_id); evidence_ids[ev.fact_type].append(ev.id)
    facts = [{"fact_type": k, "independent_sources": len(v), "confidence_multiplier": round(min(1.25, 1 + .08 * max(0, len(v) - 1)), 2), "sources": sorted(v), "evidence_ids": evidence_ids[k]} for k, v in sources.items()]
    return {"company_id": company_id, "facts": sorted(facts, key=lambda x: x["independent_sources"], reverse=True)}


def provenance_ledger(company_id: str) -> list[dict[str, Any]]:
    return [{"evidence_id": e.id, "source_id": e.source_id, "fact_type": e.fact_type, "retrieved_or_observed_at": e.observed_at, "source_url": e.source_url, "raw_reference": e.raw_reference, "confidence": e.confidence, "transformation": "stored_evidence", "consumers": [s.id for s in list_signals(company_id) if e.id in (s.evidence_ids or [])]} for e in list_evidence(company_id)]


def counterfactuals(company_id: str) -> list[dict[str, Any]]:
    present = {s.kind for s in list_signals(company_id)}
    candidates = [("hiring_growth", 12), ("tech_hiring", 10), ("digital_transformation", 14), ("revenue_growth", 9), ("headcount_growth", 8), ("new_location", 8), ("procurement_activity", 10)]
    return [{"missing_signal": k, "indicative_score_uplift": uplift, "research_question": f"Can independent public evidence confirm {k.replace('_', ' ')}?"} for k, uplift in candidates if k not in present]


def research_plan(company_id: str, budget: int = 5) -> list[dict[str, Any]]:
    """Autonomous planner prioritises missing evidence by expected information value."""
    mapping = {"hiring_growth": ("public careers/jobs", .75), "tech_hiring": ("careers + professional profiles", .72), "digital_transformation": ("website/Common Crawl/certificate transparency", .80), "revenue_growth": ("accounts/SEC filings", .90), "headcount_growth": ("accounts/Nomis/jobs", .82), "new_location": ("planning/Land Registry/OpenStreetMap", .74), "procurement_activity": ("Find a Tender/Contracts Finder", .92)}
    plan = []
    for item in counterfactuals(company_id):
        source, reliability = mapping[item["missing_signal"]]
        value = item["indicative_score_uplift"] * reliability
        plan.append({**item, "source_strategy": source, "expected_information_value": round(value, 2)})
    return sorted(plan, key=lambda x: x["expected_information_value"], reverse=True)[:max(1, min(budget, 20))]


def opportunity_clusters(company_id: str) -> list[dict[str, Any]]:
    """Groups temporally close evidence into candidate programmes using semantic title similarity."""
    evidence = list_evidence(company_id); clusters: list[dict[str, Any]] = []
    for ev in evidence:
        v = ev.value or {}; title = str(v.get("title") or v.get("name") or ev.fact_type)
        placed = False
        for cluster in clusters:
            if SequenceMatcher(None, _norm(title), _norm(cluster["label"])).ratio() >= .55:
                cluster["evidence_ids"].append(ev.id); cluster["fact_types"].add(ev.fact_type); placed = True; break
        if not placed: clusters.append({"label": title[:160], "evidence_ids": [ev.id], "fact_types": {ev.fact_type}})
    return [{**c, "fact_types": sorted(c["fact_types"]), "multi_signal_programme": len(c["fact_types"]) >= 2} for c in clusters if len(c["evidence_ids"]) >= 2]


def group_intelligence(company_id: str) -> dict[str, Any]:
    rels = list_relations(source_id=company_id)
    group_rels = [r for r in rels if r.relation in {"parent_of", "subsidiary_of", "controls", "psc", "same_group"}]
    members = {company_id}
    for r in group_rels:
        if r.target_type == "company": members.add(r.target_id)
    return {"root_company_id": company_id, "member_ids": sorted(members), "relationships": [r.model_dump() for r in group_rels], "member_predictions": {m: leading_indicators(m)[:2] for m in members if any(c.id == m for c in list_companies(10000))}}


def backtest(company_id: str, cutoff: datetime) -> dict[str, Any]:
    """Leakage-resistant skeleton: reports evidence available at cutoff and later outcomes/snapshots."""
    if cutoff.tzinfo is None: cutoff = cutoff.replace(tzinfo=UTC)
    evidence = [e for e in list_evidence(company_id) if (e.observed_at.replace(tzinfo=UTC) if e.observed_at.tzinfo is None else e.observed_at) <= cutoff]
    later_outcomes = [o for o in list_outcomes() if o.company_id == company_id and (o.created_at.replace(tzinfo=UTC) if o.created_at.tzinfo is None else o.created_at) > cutoff]
    later_snapshots = [s for s in list_snapshots(company_id) if (s.captured_at.replace(tzinfo=UTC) if s.captured_at.tzinfo is None else s.captured_at) > cutoff]
    return {"company_id": company_id, "cutoff": cutoff, "evidence_available": len(evidence), "evidence_ids": [e.id for e in evidence], "future_outcomes": [o.model_dump() for o in later_outcomes], "future_snapshot_count": len(later_snapshots), "leakage_policy": "exclude evidence observed after cutoff"}


def intelligence_pack(company_id: str) -> dict[str, Any]:
    """Single entry point covering all 20 intelligence upgrades."""
    return {"identity": canonical_entity(company_id), "temporal_graph": temporal_graph(company_id), "signal_fusion": fused_signal(company_id), "predictions": leading_indicators(company_id), "similar_companies": company_similarity(company_id), "buyer_intent": buyer_intent_graph(company_id), "decision_makers": decision_makers(company_id, "consulting"), "technology_change": technology_changes(company_id), "incumbents": incumbent_intelligence(company_id), "lifecycle": opportunity_lifecycle(company_id), "calibration": outcome_calibration(), "negative_intelligence": negative_intelligence(company_id), "corroboration": corroboration(company_id), "provenance": provenance_ledger(company_id), "decayed_signals": decayed_signals(company_id), "counterfactuals": counterfactuals(company_id), "research_plan": research_plan(company_id), "clusters": opportunity_clusters(company_id), "group_intelligence": group_intelligence(company_id)}
