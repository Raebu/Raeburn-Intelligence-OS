from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from .db import list_companies, list_evidence, list_signals

LABEL_WEIGHTS = {
    "gold_terminal": 1.0,
    "gold_intermediate": 0.7,
    "gold_engagement": 0.5,
    "gold_delivery": 0.2,
    "observed": 0.7,
    "proxy": 0.3,
}

EVENT_SIGNAL_MAP = {
    "automation_procurement": {"procurement_activity", "digital_transformation", "public_contract_win"},
    "hiring_expansion": {"hiring_growth", "tech_hiring", "headcount_growth"},
    "international_expansion": {"new_location", "market_growth"},
    "m_and_a_activity": {"director_change", "distress", "revenue_growth"},
    "technology_replacement": {"digital_transformation", "automation_gap", "tech_hiring"},
    "financial_deterioration": {"distress"},
}

POSITIVE_TERMINAL = ("won", "awarded", "accepted", "signed", "contracted")
NEGATIVE_TERMINAL = ("lost", "rejected", "declined", "unsuccessful", "closed")
POSITIVE_INTERMEDIATE = ("meeting", "proposal", "shortlist", "submitted", "demo")
ENGAGEMENT = ("reply", "replied", "responded", "response")
DELIVERY = ("delivered", "sent", "contacted")


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _date(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(parsed)


def _effective_signal_date(signal: Any, evidence_by_id: dict[str, Any]) -> datetime:
    """Prefer the source event date to ingestion/detection time for historical backtests."""
    candidates: list[datetime] = []
    for evidence_id in signal.evidence_ids or []:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            continue
        value = evidence.value or {}
        if signal.kind in {"revenue_growth", "headcount_growth"}:
            parsed = _date(value.get("filing_date") or value.get("date"))
            if parsed:
                candidates.append(parsed)
        elif signal.kind == "director_change":
            for item in value.get("items", []):
                if not isinstance(item, dict):
                    continue
                for key in ("appointed_on", "resigned_on"):
                    parsed = _date(item.get(key))
                    if parsed:
                        candidates.append(parsed)
        elif signal.kind == "distress":
            for item in value.get("items", []):
                if not isinstance(item, dict):
                    continue
                if item.get("description") == "gazette-notice-compulsory":
                    parsed = _date(item.get("date"))
                    if parsed:
                        candidates.append(parsed)
        elif signal.kind in {"public_contract_win", "procurement_activity"}:
            parsed = _date(value.get("date") or value.get("award_date") or value.get("published_date"))
            if parsed:
                candidates.append(parsed)
        else:
            parsed = _date(value.get("date") or value.get("observed_date"))
            if parsed:
                candidates.append(parsed)
    return max(candidates) if candidates else _aware(signal.detected_at)


def classify_commercial_outcome(text: str) -> dict[str, Any]:
    value = text.lower().strip()
    if any(term in value for term in POSITIVE_TERMINAL):
        return {"label_class": "gold_terminal", "outcome": 1, "weight": 1.0, "terminal": True}
    if any(term in value for term in NEGATIVE_TERMINAL):
        return {"label_class": "gold_terminal", "outcome": 0, "weight": 1.0, "terminal": True}
    if any(term in value for term in POSITIVE_INTERMEDIATE):
        return {"label_class": "gold_intermediate", "outcome": 1, "weight": 0.7, "terminal": False}
    if any(term in value for term in ENGAGEMENT):
        return {"label_class": "gold_engagement", "outcome": 1, "weight": 0.5, "terminal": False}
    if any(term in value for term in DELIVERY):
        return {"label_class": "gold_delivery", "outcome": None, "weight": 0.2, "terminal": False}
    return {"label_class": "unlabelled", "outcome": None, "weight": 0.0, "terminal": False}


def calibration_readiness(labels: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    gold_positive = gold_negative = observed_positive = observed_negative = 0
    for label in labels:
        tier = str(label.get("label_class") or label.get("tier") or "unlabelled")
        counts[tier] += 1
        outcome = label.get("outcome")
        if tier == "gold_terminal":
            gold_positive += outcome == 1
            gold_negative += outcome == 0
        elif tier == "observed":
            observed_positive += outcome == 1
            observed_negative += outcome == 0
    gold_terminal = gold_positive + gold_negative
    observed_total = observed_positive + observed_negative
    commercial_ready = gold_terminal >= 100 and gold_positive >= 30 and gold_negative >= 30
    event_ready = observed_total >= 500 and observed_positive >= 50 and observed_negative >= 50
    if commercial_ready and event_ready:
        mode = "empirically_calibrated"
    elif event_ready:
        mode = "event_calibrated_commercial_heuristic"
    elif gold_terminal >= 30:
        mode = "early_commercial_calibration"
    else:
        mode = "heuristic_explainable"
    return {
        "mode": mode,
        "commercial_conversion_ready": commercial_ready,
        "public_event_prediction_ready": event_ready,
        "counts": dict(counts),
        "gold_terminal": {"total": gold_terminal, "positive": gold_positive, "negative": gold_negative, "target": "100 total with at least 30 positive and 30 negative"},
        "observed": {"total": observed_total, "positive": observed_positive, "negative": observed_negative, "target": "500 total with at least 50 positive and 50 negative"},
        "proxy_policy": "proxy labels never make a model calibrated on their own",
    }


def empirical_calibration(rows: list[dict[str, Any]], bins: int = 10) -> dict[str, Any]:
    clean = []
    for row in rows:
        probability, outcome = row.get("probability"), row.get("outcome")
        if not isinstance(probability, (int, float)) or outcome not in {0, 1}:
            continue
        probability = max(0.0, min(1.0, float(probability)))
        tier = str(row.get("label_class") or row.get("tier") or "observed")
        weight = float(row.get("weight") or LABEL_WEIGHTS.get(tier, 0.3))
        clean.append((probability, int(bool(outcome)), max(0.0, weight)))
    if not clean:
        return {"samples": 0, "weighted_brier_score": None, "bins": []}
    total_weight = sum(weight for _, _, weight in clean)
    if total_weight <= 0:
        total_weight = float(len(clean)); clean = [(p, o, 1.0) for p, o, _ in clean]
    brier = sum(weight * (probability - outcome) ** 2 for probability, outcome, weight in clean) / total_weight
    grouped: dict[int, list[tuple[float, int, float]]] = defaultdict(list)
    bin_count = max(2, min(int(bins), 20))
    for probability, outcome, weight in clean:
        grouped[min(bin_count - 1, int(probability * bin_count))].append((probability, outcome, weight))
    reliability = []
    for index in sorted(grouped):
        items = grouped[index]; weight_sum = sum(item[2] for item in items) or float(len(items))
        reliability.append({"bin": index, "samples": len(items), "mean_prediction": round(sum(item[0] * item[2] for item in items) / weight_sum, 4), "observed_rate": round(sum(item[1] * item[2] for item in items) / weight_sum, 4)})
    return {"samples": len(clean), "weighted_brier_score": round(brier, 6), "bins": reliability}


def select_active_learning(candidates: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    ranked = []
    for candidate in candidates:
        probabilities = candidate.get("probabilities") or []
        if not probabilities and isinstance(candidate.get("probability"), (int, float)):
            probabilities = [float(candidate["probability"])]
        numeric = [float(value) for value in probabilities if isinstance(value, (int, float))]
        if not numeric:
            continue
        mean_probability = sum(numeric) / len(numeric)
        uncertainty = 1.0 - min(1.0, abs(mean_probability - 0.5) * 2)
        disagreement = max(numeric) - min(numeric) if len(numeric) > 1 else 0.0
        value = float(candidate.get("commercial_value") or candidate.get("score") or 0.0)
        priority = 0.55 * uncertainty + 0.30 * disagreement + 0.15 * min(1.0, max(0.0, value / 100.0))
        ranked.append({**candidate, "active_learning_priority": round(priority, 4), "uncertainty": round(uncertainty, 4), "model_disagreement": round(disagreement, 4)})
    return sorted(ranked, key=lambda row: row["active_learning_priority"], reverse=True)[: max(1, min(limit, 500))]


def observed_event_labels(company_id: str, cutoff: datetime, horizon_days: int = 365) -> list[dict[str, Any]]:
    """Generate positive and negative labels using effective source dates, not ingestion time."""
    cutoff = _aware(cutoff)
    horizon = cutoff + timedelta(days=max(1, min(horizon_days, 3650)))
    signals = list_signals(company_id)
    evidence_by_id = {row.id: row for row in list_evidence(company_id)}
    labels = []
    for event, signal_kinds in EVENT_SIGNAL_MAP.items():
        future = []
        effective_dates: dict[str, datetime] = {}
        for signal in signals:
            if signal.kind not in signal_kinds:
                continue
            effective = _effective_signal_date(signal, evidence_by_id)
            effective_dates[signal.id] = effective
            if cutoff < effective <= horizon:
                future.append(signal)
        labels.append({
            "company_id": company_id,
            "event": event,
            "cutoff": cutoff,
            "horizon_days": horizon_days,
            "outcome": 1 if future else 0,
            "label_class": "observed",
            "weight": LABEL_WEIGHTS["observed"],
            "evidence_ids": [evidence_id for signal in future for evidence_id in (signal.evidence_ids or [])],
            "observed_signal_ids": [signal.id for signal in future],
            "observed_event_dates": {signal.id: effective_dates[signal.id] for signal in future},
            "leakage_policy": "effective source-event date must be after cutoff and within horizon; ingestion time is fallback only when source date is unavailable",
        })
    return labels


def batch_observed_labels(cutoff: datetime, horizon_days: int = 365, limit: int = 10000) -> list[dict[str, Any]]:
    labels = []
    for company in list_companies(limit=max(1, min(limit, 10000))):
        labels.extend(observed_event_labels(company.id, cutoff, horizon_days))
    return labels


def multi_cutoff_observed_labels(cutoffs: list[datetime], horizon_days: int = 180, limit: int = 10000) -> list[dict[str, Any]]:
    """Quickly create a large, balanced backtest corpus from several historical cutoffs."""
    labels = []
    for cutoff in cutoffs:
        labels.extend(batch_observed_labels(cutoff, horizon_days=horizon_days, limit=limit))
    return labels
