from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from statistics import mean, pstdev
from typing import Any
from uuid import uuid4

from .db import (
    ActionRow,
    AlertRow,
    OutcomeRow,
    PersonRow,
    RelationRow,
    SnapshotRow,
    WatchlistRow,
    get_action,
    get_company,
    list_actions,
    list_alerts,
    list_companies,
    list_evidence,
    list_outcomes,
    list_people,
    list_relations,
    list_signals,
    list_snapshots,
    list_watchlists,
    replace_people,
    replace_relations,
    save_action,
    save_alerts,
    save_outcome,
    save_snapshot,
    save_watchlist,
)
from .service import digital_twin

ROLE_FAMILIES = {
    "chief executive": "executive",
    "ceo": "executive",
    "managing director": "executive",
    "director": "executive",
    "chief technology": "technology",
    "cto": "technology",
    "technology": "technology",
    "engineering": "technology",
    "chief operating": "operations",
    "coo": "operations",
    "operations": "operations",
    "transformation": "transformation",
    "digital": "transformation",
    "talent": "people",
    "people": "people",
    "hr": "people",
    "recruit": "people",
    "finance": "finance",
    "cfo": "finance",
}


def _now() -> datetime:
    return datetime.now(UTC)


def capture_snapshot(company_id: str, snapshot_type: str = "digital_twin") -> dict:
    twin = digital_twin(company_id)
    evidence_ids = [row["id"] for row in twin["evidence"]]
    row = SnapshotRow(
        id=str(uuid4()),
        company_id=company_id,
        snapshot_type=snapshot_type,
        captured_at=_now(),
        data=twin,
        evidence_ids=evidence_ids,
    )
    save_snapshot(row)
    return row.model_dump()


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(item, path))
    elif isinstance(value, list):
        result[prefix] = value
    else:
        result[prefix] = value
    return result


def snapshot_changes(company_id: str, snapshot_type: str = "digital_twin") -> dict:
    snapshots = list_snapshots(company_id, snapshot_type)
    if len(snapshots) < 2:
        return {"company_id": company_id, "changes": [], "snapshots": len(snapshots)}
    latest, previous = snapshots[0], snapshots[1]
    before = _flatten(previous.data)
    after = _flatten(latest.data)
    changes = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changes.append({"field": key, "before": before.get(key), "after": after.get(key)})
    return {
        "company_id": company_id,
        "previous_snapshot": previous.id,
        "latest_snapshot": latest.id,
        "changes": changes,
    }


def infer_people(company_id: str) -> list[dict]:
    evidence = list_evidence(company_id)
    officers = next((row for row in evidence if row.fact_type == "officers"), None)
    items = (officers.value or {}).get("items", []) if officers else []
    people: list[PersonRow] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        occupation = str(item.get("occupation") or item.get("officer_role") or "director")
        lowered = occupation.lower()
        family = next((family for phrase, family in ROLE_FAMILIES.items() if phrase in lowered), "executive")
        confidence = 0.95 if item.get("officer_role") else 0.75
        people.append(
            PersonRow(
                id=f"{company_id}:{name.lower()}:{occupation.lower()}",
                company_id=company_id,
                name=name,
                role=occupation,
                role_family=family,
                appointed_on=item.get("appointed_on"),
                resigned_on=item.get("resigned_on"),
                confidence=confidence,
                source_url=officers.source_url if officers else None,
                evidence_ids=[officers.id] if officers else [],
                updated_at=_now(),
            )
        )
    replace_people(company_id, people)
    return [row.model_dump() for row in people]


def rebuild_graph(company_id: str) -> dict:
    company = get_company(company_id)
    if company is None:
        raise KeyError(company_id)
    people = list_people(company_id) or [PersonRow(**row) for row in infer_people(company_id)]
    evidence = list_evidence(company_id)
    relations: list[RelationRow] = []
    now = _now()
    for person in people:
        relations.append(
            RelationRow(
                id=str(uuid4()),
                source_type="company",
                source_id=company_id,
                relation="has_person",
                target_type="person",
                target_id=person.id,
                confidence=person.confidence,
                evidence_ids=person.evidence_ids,
                observed_at=now,
            )
        )
    for row in evidence:
        if row.fact_type != "contract_award":
            continue
        buyer = (row.value or {}).get("buyer") or {}
        buyer_id = str(buyer.get("id") or buyer.get("name") or "").strip()
        if buyer_id:
            relations.append(
                RelationRow(
                    id=str(uuid4()),
                    source_type="company",
                    source_id=company_id,
                    relation="won_contract_from",
                    target_type="buyer",
                    target_id=buyer_id,
                    confidence=row.confidence,
                    evidence_ids=[row.id],
                    observed_at=row.observed_at,
                )
            )
    replace_relations("company", company_id, relations)
    return {
        "company": company.model_dump(),
        "people": [row.model_dump() for row in people],
        "relations": [row.model_dump() for row in relations],
    }


def financial_trends(company_id: str) -> dict:
    rows = [row for row in list_evidence(company_id) if row.fact_type in {"accounts", "financial_metrics"}]
    metrics: dict[str, list[tuple[datetime, float, str]]] = defaultdict(list)
    aliases = {
        "turnover": ["turnover", "revenue"],
        "cash": ["cash", "cash_at_bank"],
        "net_assets": ["net_assets", "netAssets"],
        "liabilities": ["liabilities", "total_liabilities"],
        "employees": ["employees", "employee_count", "average_employees"],
    }
    for row in rows:
        value = row.value or {}
        for metric, keys in aliases.items():
            for key in keys:
                raw = value.get(key)
                if isinstance(raw, (int, float)):
                    metrics[metric].append((row.observed_at, float(raw), row.id))
                    break
    result = {}
    for metric, values in metrics.items():
        values.sort(key=lambda item: item[0])
        latest = values[-1]
        previous = values[-2] if len(values) > 1 else None
        growth = None
        if previous and previous[1] != 0:
            growth = (latest[1] - previous[1]) / abs(previous[1])
        result[metric] = {
            "latest": latest[1],
            "previous": previous[1] if previous else None,
            "growth": growth,
            "evidence_ids": [item[2] for item in values[-2:]],
        }
    return {"company_id": company_id, "metrics": result, "source_records": len(rows)}


def tender_score(record: dict, profile: dict | None = None) -> dict:
    profile = profile or {}
    score = 0.0
    reasons: list[str] = []
    title = str(record.get("title") or "").lower()
    description = str(record.get("description") or "").lower()
    text = f"{title} {description}"
    keywords = profile.get(
        "keywords",
        ["automation", "digital", "technology", "software", "consulting", "recruitment", "ai", "data"],
    )
    hits = [word for word in keywords if str(word).lower() in text]
    if hits:
        score += min(45, 12 + 8 * len(hits))
        reasons.append(f"Service-fit keywords: {', '.join(hits[:6])}.")
    value = record.get("tender_value") or record.get("award_value") or {}
    amount = value.get("amount") if isinstance(value, dict) else None
    if isinstance(amount, (int, float)):
        if 25_000 <= amount <= 5_000_000:
            score += 20
            reasons.append("Contract value falls within a practical SME/mid-market delivery range.")
        elif amount > 5_000_000:
            score += 10
            reasons.append("Large contract may favour consortium or partner participation.")
    if record.get("buyer"):
        score += 10
        reasons.append("Identifiable public buyer available for qualification.")
    tags = {str(tag).lower() for tag in record.get("tags") or []}
    if "tender" in tags or "planning" in tags:
        score += 15
        reasons.append("Opportunity is at a pre-award stage.")
    elif "award" in tags:
        score -= 20
        reasons.append("Record is already at award stage.")
    score = max(0.0, min(100.0, score))
    return {"score": round(score, 1), "reasons": reasons, "record": record}


def peer_anomalies(company_id: str) -> dict:
    company = get_company(company_id)
    if company is None:
        raise KeyError(company_id)
    peers = [row for row in list_companies(limit=10000) if row.id != company_id]
    if company.sic_codes:
        peers = [row for row in peers if set(row.sic_codes).intersection(company.sic_codes)] or peers
    target = {row.kind: row.strength for row in list_signals(company_id)}
    peer_values: dict[str, list[float]] = defaultdict(list)
    for peer in peers:
        for signal in list_signals(peer.id):
            peer_values[signal.kind].append(signal.strength)
    anomalies = []
    for kind, value in target.items():
        values = peer_values.get(kind, [])
        if len(values) < 2:
            continue
        avg = mean(values)
        deviation = pstdev(values)
        z = (value - avg) / deviation if deviation else 0.0
        if abs(z) >= 1.0:
            anomalies.append({"signal": kind, "value": value, "peer_mean": avg, "z_score": round(z, 2)})
    return {"company_id": company_id, "peer_count": len(peers), "anomalies": anomalies}


def create_watchlist(name: str, company_ids: list[str], signal_kinds: list[str], minimum_strength: float = 0.5) -> dict:
    now = _now()
    row = WatchlistRow(
        id=str(uuid4()),
        name=name,
        company_ids=company_ids,
        signal_kinds=signal_kinds,
        minimum_strength=minimum_strength,
        active=True,
        created_at=now,
        updated_at=now,
    )
    return save_watchlist(row).model_dump()


def evaluate_watchlists() -> list[dict]:
    alerts: list[AlertRow] = []
    for watchlist in list_watchlists():
        if not watchlist.active:
            continue
        for company_id in watchlist.company_ids:
            for signal in list_signals(company_id):
                if signal.strength < watchlist.minimum_strength:
                    continue
                if watchlist.signal_kinds and signal.kind not in watchlist.signal_kinds:
                    continue
                alert_id = f"{watchlist.id}:{company_id}:{signal.kind}:{signal.id}"
                alerts.append(
                    AlertRow(
                        id=alert_id,
                        watchlist_id=watchlist.id,
                        company_id=company_id,
                        signal_kind=signal.kind,
                        strength=signal.strength,
                        summary=signal.explanation or signal.kind,
                        evidence_ids=signal.evidence_ids,
                        created_at=_now(),
                    )
                )
    save_alerts(alerts)
    return [row.model_dump() for row in alerts]


def analyst(company_id: str, question: str) -> dict:
    twin = digital_twin(company_id)
    question_lower = question.lower()
    evidence = twin["evidence"]
    signals = twin["signals"]
    opportunities = twin["opportunities"]
    cited: list[str] = []
    points: list[str] = []
    if any(word in question_lower for word in ("sell", "offer", "need", "opportun")):
        top = sorted(opportunities, key=lambda item: item["score"], reverse=True)[:3]
        for item in top:
            points.append(f"{item['kind']}: {item['score']}/100 — {item['rationale']}")
            cited.extend(item.get("evidence_ids") or [])
    elif any(word in question_lower for word in ("change", "changed", "month", "recent")):
        changes = snapshot_changes(company_id)
        for item in changes["changes"][:10]:
            points.append(f"{item['field']} changed from {item['before']} to {item['after']}.")
    elif any(word in question_lower for word in ("risk", "distress")):
        for item in signals:
            if item["kind"] == "distress":
                points.append(item.get("explanation") or "Distress signal detected.")
                cited.extend(item.get("evidence_ids") or [])
    else:
        for item in sorted(signals, key=lambda row: row["strength"], reverse=True)[:5]:
            points.append(item.get("explanation") or item["kind"])
            cited.extend(item.get("evidence_ids") or [])
    if not points:
        points.append("No stored evidence currently supports a confident answer to that question.")
    available_ids = {row["id"] for row in evidence}
    cited = list(dict.fromkeys(item for item in cited if item in available_ids))
    return {
        "company_id": company_id,
        "question": question,
        "answer": " ".join(points),
        "evidence_ids": cited,
        "grounding": "stored_evidence_only",
    }


def propose_actions(company_id: str, minimum_score: float = 60.0) -> list[dict]:
    twin = digital_twin(company_id)
    proposed: list[ActionRow] = []
    mapping = {
        "automation": "prepare_automation_assessment",
        "consulting": "prepare_consulting_brief",
        "recruitment": "prepare_recruitment_outreach",
        "software": "prepare_solution_brief",
        "procurement": "prepare_bid_review",
        "ma": "prepare_ma_screen",
        "market_entry": "prepare_market_entry_brief",
    }
    for opportunity in twin["opportunities"]:
        if opportunity["score"] < minimum_score:
            continue
        action = ActionRow(
            id=str(uuid4()),
            company_id=company_id,
            opportunity_kind=opportunity["kind"],
            action_type=mapping[opportunity["kind"]],
            status="proposed",
            payload={
                "score": opportunity["score"],
                "confidence": opportunity["confidence"],
                "recommended_action": opportunity["recommended_action"],
                "external_execution": False,
                "approval_required": True,
            },
            evidence_ids=opportunity.get("evidence_ids") or [],
            created_at=_now(),
        )
        proposed.append(save_action(action))
    return [row.model_dump() for row in proposed]


def approve_action(action_id: str) -> dict:
    row = get_action(action_id)
    if row is None:
        raise KeyError(action_id)
    row.status = "approved"
    row.approved_at = _now()
    return save_action(row).model_dump()


def record_outcome(
    company_id: str,
    opportunity_kind: str,
    outcome: str,
    action_id: str | None = None,
    revenue_gbp: float | None = None,
    notes: str | None = None,
) -> dict:
    row = OutcomeRow(
        id=str(uuid4()),
        company_id=company_id,
        action_id=action_id,
        opportunity_kind=opportunity_kind,
        outcome=outcome,
        revenue_gbp=revenue_gbp,
        notes=notes,
        created_at=_now(),
    )
    return save_outcome(row).model_dump()


def feedback_summary() -> dict:
    outcomes = list_outcomes()
    by_kind: dict[str, Counter] = defaultdict(Counter)
    revenue: dict[str, float] = defaultdict(float)
    for row in outcomes:
        by_kind[row.opportunity_kind][row.outcome] += 1
        revenue[row.opportunity_kind] += row.revenue_gbp or 0.0
    return {
        "total_outcomes": len(outcomes),
        "by_kind": {kind: dict(counter) for kind, counter in by_kind.items()},
        "revenue_gbp": dict(revenue),
        "actions": len(list_actions()),
        "alerts": len(list_alerts(limit=10000)),
    }


def graph(entity_type: str, entity_id: str) -> dict:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "relations": [row.model_dump() for row in list_relations(entity_type, entity_id)],
    }
