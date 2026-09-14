from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

from .db import (
    list_companies,
    list_evidence,
    list_outcomes,
    list_people,
    list_relations,
    list_signals,
    list_snapshots,
)
from .service import digital_twin

DECAY_DAYS = {
    "hiring_growth": 60,
    "tech_hiring": 60,
    "public_contract_win": 365,
    "director_change": 365,
    "distress": 120,
    "digital_transformation": 270,
    "revenue_growth": 540,
    "headcount_growth": 365,
    "new_location": 365,
    "procurement_activity": 120,
    "market_growth": 180,
}

DECISION_ROLE_MAP = {
    "automation": {"technology", "operations", "transformation", "executive"},
    "consulting": {"executive", "operations", "transformation", "finance"},
    "recruitment": {"people", "executive", "operations"},
    "software": {"technology", "transformation", "operations"},
    "procurement": {"operations", "finance", "executive"},
    "m_and_a": {"executive", "finance"},
    "market_entry": {"executive", "operations", "finance"},
}

NEGATIVE_FACTS = {
    "insolvency",
    "dissolution",
    "gazette-notice-compulsory",
    "contract_closed",
    "procurement_closed",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def canonical_entity(company_id: str) -> dict[str, Any]:
    """Return a deterministic canonical organisation identity record."""
    twin = digital_twin(company_id)
    company = twin["company"]
    aliases = {_norm(company.get("name"))}
    identifiers = {"companies_house": company.get("company_number")}
    domains: set[str] = set()

    for evidence in twin["evidence"]:
        value = evidence.get("value") or {}
        for key in ("name", "company_name", "organisation", "legal_name"):
            raw = value.get(key)
            if isinstance(raw, str):
                aliases.add(_norm(raw))
        for key in (
            "cik",
            "lei",
            "opencorporates_id",
            "charity_number",
            "vat_number",
        ):
            if value.get(key):
                identifiers[key] = str(value[key])
        domain = value.get("domain") or value.get("website")
        if isinstance(domain, str):
            clean = domain.lower().replace("https://", "").replace("http://", "")
            domains.add(clean.split("/")[0])

    return {
        "canonical_id": f"org:gb:coh:{company.get('company_number')}",
        "company_id": company_id,
        "aliases": sorted(alias for alias in aliases if alias),
        "identifiers": identifiers,
        "domains": sorted(domains),
    }


def temporal_graph(company_id: str) -> dict[str, Any]:
    """Return graph relationships with observed and effective dates."""
    relations = list_relations("company", company_id)
    people = {person.id: person for person in list_people(company_id)}
    edges = []

    for relation in relations:
        person = people.get(relation.target_id)
        edges.append(
            {
                "source_type": relation.source_type,
                "source_id": relation.source_id,
                "relation": relation.relation,
                "target_type": relation.target_type,
                "target_id": relation.target_id,
                "valid_from": getattr(person, "appointed_on", None) if person else None,
                "valid_to": getattr(person, "resigned_on", None) if person else None,
                "observed_at": relation.observed_at,
                "confidence": relation.confidence,
                "evidence_ids": relation.evidence_ids,
            }
        )
    return {"company_id": company_id, "edges": edges}


def decayed_signals(
    company_id: str,
    at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Apply signal-specific half-lives so stale evidence loses influence."""
    at = _aware(at or _now())
    rows = []
    for signal in list_signals(company_id):
        detected = _aware(signal.detected_at)
        age = max(0.0, (at - detected).total_seconds() / 86400)
        half_life = DECAY_DAYS.get(signal.kind, 180)
        factor = 0.5 ** (age / half_life)
        rows.append(
            {
                "kind": signal.kind,
                "raw_strength": signal.strength,
                "decayed_strength": round(signal.strength * factor, 4),
                "confidence": signal.confidence,
                "age_days": round(age, 1),
                "half_life_days": half_life,
                "evidence_ids": signal.evidence_ids,
            }
        )
    return rows


def fused_signal(company_id: str) -> dict[str, Any]:
    """Fuse independent signals while limiting saturation and double counting."""
    signals = decayed_signals(company_id)
    if not signals:
        return {
            "company_id": company_id,
            "strength": 0.0,
            "independent_signals": 0,
            "signals": [],
        }

    probabilities = [
        min(0.98, signal["decayed_strength"] * signal["confidence"])
        for signal in signals
    ]
    combined = 1 - math.prod(1 - probability for probability in probabilities)
    kinds = {signal["kind"] for signal in signals}
    diversity_bonus = min(0.15, 0.025 * max(0, len(kinds) - 1))
    return {
        "company_id": company_id,
        "strength": round(min(1.0, combined + diversity_bonus), 4),
        "independent_signals": len(kinds),
        "signals": signals,
    }


def leading_indicators(company_id: str) -> list[dict[str, Any]]:
    """Produce explainable forward-event estimates pending empirical calibration."""
    by_kind = {signal["kind"]: signal for signal in decayed_signals(company_id)}
    specs = {
        "automation_procurement": (
            180,
            {
                "digital_transformation": 0.32,
                "headcount_growth": 0.18,
                "revenue_growth": 0.15,
                "public_contract_win": 0.14,
                "tech_hiring": 0.21,
            },
        ),
        "hiring_expansion": (
            120,
            {
                "headcount_growth": 0.30,
                "revenue_growth": 0.18,
                "hiring_growth": 0.32,
                "public_contract_win": 0.12,
                "new_location": 0.18,
            },
        ),
        "international_expansion": (
            270,
            {
                "market_growth": 0.30,
                "new_location": 0.30,
                "revenue_growth": 0.18,
                "hiring_growth": 0.12,
            },
        ),
        "m_and_a_activity": (
            365,
            {
                "revenue_growth": 0.18,
                "director_change": 0.16,
                "market_growth": 0.20,
                "distress": 0.24,
            },
        ),
        "technology_replacement": (
            180,
            {
                "digital_transformation": 0.38,
                "tech_hiring": 0.22,
                "automation_gap": 0.30,
            },
        ),
        "financial_deterioration": (
            120,
            {"distress": 0.55, "director_change": 0.10},
        ),
    }

    predictions = []
    for event, (horizon, weights) in specs.items():
        contributions = []
        probability = 0.05
        for kind, weight in weights.items():
            signal = by_kind.get(kind)
            if not signal:
                continue
            contribution = (
                weight * signal["decayed_strength"] * signal["confidence"]
            )
            probability += contribution
            contributions.append(
                {
                    "signal": kind,
                    "contribution": round(contribution, 4),
                    "evidence_ids": signal["evidence_ids"],
                }
            )
        predictions.append(
            {
                "event": event,
                "probability": round(min(0.95, probability), 3),
                "horizon_days": horizon,
                "evidence": contributions,
                "calibration": "heuristic_explainable",
            }
        )
    return sorted(predictions, key=lambda row: row["probability"], reverse=True)


def company_similarity(
    company_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    target = {
        signal.kind: signal.strength * signal.confidence
        for signal in list_signals(company_id)
    }
    companies = list_companies(10000)
    target_company = next(
        (company for company in companies if company.id == company_id),
        None,
    )
    results = []

    for company in companies:
        if company.id == company_id:
            continue
        peer = {
            signal.kind: signal.strength * signal.confidence
            for signal in list_signals(company.id)
        }
        keys = set(target) | set(peer)
        dot = sum(target.get(key, 0) * peer.get(key, 0) for key in keys)
        target_size = math.sqrt(sum(target.get(key, 0) ** 2 for key in keys))
        peer_size = math.sqrt(sum(peer.get(key, 0) ** 2 for key in keys))
        signal_similarity = dot / (target_size * peer_size) if target_size and peer_size else 0

        sic_similarity = 0.0
        if target_company:
            target_sics = set(target_company.sic_codes or [])
            peer_sics = set(company.sic_codes or [])
            union = target_sics | peer_sics
            if union:
                sic_similarity = len(target_sics & peer_sics) / len(union)

        results.append(
            {
                "company_id": company.id,
                "name": company.name,
                "similarity": round(
                    0.8 * signal_similarity + 0.2 * sic_similarity,
                    4,
                ),
            }
        )
    return sorted(results, key=lambda row: row["similarity"], reverse=True)[:limit]


def buyer_intent_graph(company_id: str) -> dict[str, Any]:
    edges = []
    relevant = {"contract_award", "procurement", "tender", "planning_notice"}
    for evidence in list_evidence(company_id):
        if evidence.fact_type not in relevant:
            continue
        value = evidence.value or {}
        buyer = value.get("buyer") or {}
        tender = value.get("tender") or {}
        tender_period = tender.get("tenderPeriod") or {}
        contract_period = tender.get("contractPeriod") or {}
        edges.append(
            {
                "buyer": buyer,
                "title": value.get("title") or tender.get("title"),
                "value": value.get("tender_value") or value.get("award_value"),
                "deadline": value.get("deadline") or tender_period.get("endDate"),
                "contract_end": value.get("contract_end")
                or contract_period.get("endDate"),
                "evidence_id": evidence.id,
            }
        )
    return {"company_id": company_id, "intent_edges": edges}


def decision_makers(
    company_id: str,
    opportunity_kind: str,
) -> list[dict[str, Any]]:
    wanted = DECISION_ROLE_MAP.get(opportunity_kind, {"executive"})
    active_people = [person for person in list_people(company_id) if not person.resigned_on]
    ranked = sorted(
        active_people,
        key=lambda person: (person.role_family in wanted, person.confidence),
        reverse=True,
    )
    return [
        {
            "person_id": person.id,
            "name": person.name,
            "role": person.role,
            "role_family": person.role_family,
            "fit": "high" if person.role_family in wanted else "secondary",
            "confidence": person.confidence,
            "evidence_ids": person.evidence_ids,
        }
        for person in ranked[:12]
    ]


def technology_changes(company_id: str) -> dict[str, Any]:
    snapshots = list_snapshots(company_id)
    if len(snapshots) < 2:
        return {
            "company_id": company_id,
            "changes": [],
            "snapshots": len(snapshots),
        }

    def technologies(snapshot) -> list[Any]:
        evidence = (snapshot.data or {}).get("evidence", [])
        values = []
        for item in evidence:
            if item.get("fact_type") in {
                "technology_profile",
                "domain",
                "certificate",
                "website",
            }:
                values.append(item.get("value"))
        return values

    before = technologies(snapshots[1])
    after = technologies(snapshots[0])
    return {
        "company_id": company_id,
        "changed": before != after,
        "before": before,
        "after": after,
        "snapshots": [snapshots[1].id, snapshots[0].id],
    }


def incumbent_intelligence(company_id: str) -> dict[str, Any]:
    contracts = buyer_intent_graph(company_id)["intent_edges"]
    expiring = [contract for contract in contracts if contract.get("contract_end")]
    return {
        "company_id": company_id,
        "contracts": contracts,
        "contracts_with_expiry": expiring,
        "research_priority": "high" if expiring else "normal",
    }


def opportunity_lifecycle(company_id: str) -> dict[str, Any]:
    outcomes = [outcome for outcome in list_outcomes() if outcome.company_id == company_id]
    stage = "detected"
    if outcomes:
        latest = outcomes[0]
        mapping = {
            "meeting": "meeting",
            "proposal": "proposal",
            "won": "won",
            "lost": "lost",
            "reply": "outreach",
        }
        stage = mapping.get(latest.outcome.lower(), "qualified")
    return {
        "company_id": company_id,
        "stage": stage,
        "allowed_stages": [
            "detected",
            "qualified",
            "researched",
            "contact_identified",
            "outreach",
            "meeting",
            "proposal",
            "won",
            "lost",
        ],
        "outcome_count": len(outcomes),
    }


def outcome_calibration() -> dict[str, Any]:
    outcomes = list_outcomes()
    stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"total": 0, "won": 0, "revenue": 0.0}
    )
    for outcome in outcomes:
        row = stats[outcome.opportunity_kind]
        row["total"] += 1
        if outcome.outcome.lower() == "won":
            row["won"] += 1
        row["revenue"] += float(outcome.revenue_gbp or 0)

    by_kind = {}
    for kind, values in stats.items():
        total = values["total"]
        by_kind[kind] = {
            **values,
            "win_rate": round(values["won"] / total, 4) if total else None,
        }
    return {
        "samples": len(outcomes),
        "by_kind": by_kind,
        "policy": "retain_deterministic_score_alongside_learned_calibration",
    }


def negative_intelligence(company_id: str) -> list[dict[str, Any]]:
    negatives = []
    for evidence in list_evidence(company_id):
        text = f"{evidence.fact_type} {evidence.value}".lower()
        hits = [term for term in NEGATIVE_FACTS if term in text]
        if hits:
            negatives.append(
                {
                    "reason": hits[0],
                    "confidence": evidence.confidence,
                    "evidence_id": evidence.id,
                }
            )
    return negatives


def corroboration(company_id: str) -> dict[str, Any]:
    sources: dict[str, set[str]] = defaultdict(set)
    evidence_ids: dict[str, list[str]] = defaultdict(list)
    for evidence in list_evidence(company_id):
        sources[evidence.fact_type].add(evidence.source_id)
        evidence_ids[evidence.fact_type].append(evidence.id)

    facts = []
    for fact_type, source_ids in sources.items():
        facts.append(
            {
                "fact_type": fact_type,
                "independent_sources": len(source_ids),
                "confidence_multiplier": round(
                    min(1.25, 1 + 0.08 * max(0, len(source_ids) - 1)),
                    2,
                ),
                "sources": sorted(source_ids),
                "evidence_ids": evidence_ids[fact_type],
            }
        )
    return {
        "company_id": company_id,
        "facts": sorted(
            facts,
            key=lambda row: row["independent_sources"],
            reverse=True,
        ),
    }


def provenance_ledger(company_id: str) -> list[dict[str, Any]]:
    signals = list_signals(company_id)
    rows = []
    for evidence in list_evidence(company_id):
        consumers = [
            signal.id
            for signal in signals
            if evidence.id in (signal.evidence_ids or [])
        ]
        rows.append(
            {
                "evidence_id": evidence.id,
                "source_id": evidence.source_id,
                "fact_type": evidence.fact_type,
                "retrieved_or_observed_at": evidence.observed_at,
                "source_url": evidence.source_url,
                "raw_reference": evidence.raw_reference,
                "confidence": evidence.confidence,
                "transformation": "stored_evidence",
                "consumers": consumers,
            }
        )
    return rows


def counterfactuals(company_id: str) -> list[dict[str, Any]]:
    present = {signal.kind for signal in list_signals(company_id)}
    candidates = [
        ("hiring_growth", 12),
        ("tech_hiring", 10),
        ("digital_transformation", 14),
        ("revenue_growth", 9),
        ("headcount_growth", 8),
        ("new_location", 8),
        ("procurement_activity", 10),
    ]
    return [
        {
            "missing_signal": kind,
            "indicative_score_uplift": uplift,
            "research_question": (
                "Can independent public evidence confirm "
                f"{kind.replace('_', ' ')}?"
            ),
        }
        for kind, uplift in candidates
        if kind not in present
    ]


def research_plan(
    company_id: str,
    budget: int = 5,
) -> list[dict[str, Any]]:
    """Prioritise missing evidence by expected information value."""
    mapping = {
        "hiring_growth": ("public careers/jobs", 0.75),
        "tech_hiring": ("careers + professional profiles", 0.72),
        "digital_transformation": (
            "website/Common Crawl/certificate transparency",
            0.80,
        ),
        "revenue_growth": ("accounts/SEC filings", 0.90),
        "headcount_growth": ("accounts/Nomis/jobs", 0.82),
        "new_location": ("planning/Land Registry/OpenStreetMap", 0.74),
        "procurement_activity": ("Find a Tender/Contracts Finder", 0.92),
    }
    plan = []
    for item in counterfactuals(company_id):
        source, reliability = mapping[item["missing_signal"]]
        value = item["indicative_score_uplift"] * reliability
        plan.append(
            {
                **item,
                "source_strategy": source,
                "expected_information_value": round(value, 2),
            }
        )
    limit = max(1, min(budget, 20))
    return sorted(
        plan,
        key=lambda row: row["expected_information_value"],
        reverse=True,
    )[:limit]


def opportunity_clusters(company_id: str) -> list[dict[str, Any]]:
    """Group semantically related evidence into candidate programmes."""
    clusters: list[dict[str, Any]] = []
    for evidence in list_evidence(company_id):
        value = evidence.value or {}
        title = str(value.get("title") or value.get("name") or evidence.fact_type)
        placed = False
        for cluster in clusters:
            similarity = SequenceMatcher(
                None,
                _norm(title),
                _norm(cluster["label"]),
            ).ratio()
            if similarity >= 0.55:
                cluster["evidence_ids"].append(evidence.id)
                cluster["fact_types"].add(evidence.fact_type)
                placed = True
                break
        if not placed:
            clusters.append(
                {
                    "label": title[:160],
                    "evidence_ids": [evidence.id],
                    "fact_types": {evidence.fact_type},
                }
            )

    result = []
    for cluster in clusters:
        if len(cluster["evidence_ids"]) < 2:
            continue
        fact_types = sorted(cluster["fact_types"])
        result.append(
            {
                **cluster,
                "fact_types": fact_types,
                "multi_signal_programme": len(fact_types) >= 2,
            }
        )
    return result


def group_intelligence(company_id: str) -> dict[str, Any]:
    relations = list_relations("company", company_id)
    group_relations = [
        relation
        for relation in relations
        if relation.relation
        in {"parent_of", "subsidiary_of", "controls", "psc", "same_group"}
    ]
    members = {company_id}
    for relation in group_relations:
        if relation.target_type == "company":
            members.add(relation.target_id)

    known_ids = {company.id for company in list_companies(10000)}
    member_predictions = {
        member: leading_indicators(member)[:2]
        for member in members
        if member in known_ids
    }
    return {
        "root_company_id": company_id,
        "member_ids": sorted(members),
        "relationships": [relation.model_dump() for relation in group_relations],
        "member_predictions": member_predictions,
    }


def backtest(company_id: str, cutoff: datetime) -> dict[str, Any]:
    """Evaluate only evidence available at a historical cutoff."""
    cutoff = _aware(cutoff)
    evidence = [
        row
        for row in list_evidence(company_id)
        if _aware(row.observed_at) <= cutoff
    ]
    later_outcomes = [
        outcome
        for outcome in list_outcomes()
        if outcome.company_id == company_id and _aware(outcome.created_at) > cutoff
    ]
    later_snapshots = [
        snapshot
        for snapshot in list_snapshots(company_id)
        if _aware(snapshot.captured_at) > cutoff
    ]
    return {
        "company_id": company_id,
        "cutoff": cutoff,
        "evidence_available": len(evidence),
        "evidence_ids": [row.id for row in evidence],
        "future_outcomes": [outcome.model_dump() for outcome in later_outcomes],
        "future_snapshot_count": len(later_snapshots),
        "leakage_policy": "exclude evidence observed after cutoff",
    }


def intelligence_pack(company_id: str) -> dict[str, Any]:
    """Return one payload covering the twenty advanced intelligence capabilities."""
    return {
        "identity": canonical_entity(company_id),
        "temporal_graph": temporal_graph(company_id),
        "signal_fusion": fused_signal(company_id),
        "predictions": leading_indicators(company_id),
        "similar_companies": company_similarity(company_id),
        "buyer_intent": buyer_intent_graph(company_id),
        "decision_makers": decision_makers(company_id, "consulting"),
        "technology_change": technology_changes(company_id),
        "incumbents": incumbent_intelligence(company_id),
        "lifecycle": opportunity_lifecycle(company_id),
        "calibration": outcome_calibration(),
        "negative_intelligence": negative_intelligence(company_id),
        "corroboration": corroboration(company_id),
        "provenance": provenance_ledger(company_id),
        "decayed_signals": decayed_signals(company_id),
        "counterfactuals": counterfactuals(company_id),
        "research_plan": research_plan(company_id),
        "clusters": opportunity_clusters(company_id),
        "group_intelligence": group_intelligence(company_id),
    }
