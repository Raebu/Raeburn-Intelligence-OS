from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from .db import list_companies, list_signals

LABEL_WEIGHTS = {
    "gold_terminal": 1.0,
    "gold_intermediate": 0.7,
    "gold_engagement": 0.5,
    "gold_delivery": 0.2,
    "observed": 0.7,
    "proxy": 0.3,
}

EVENT_SIGNAL_MAP = {
    "automation_procurement": {
        "procurement_activity",
        "digital_transformation",
        "public_contract_win",
    },
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
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def classify_commercial_outcome(text: str) -> dict[str, Any]:
    """Classify known lifecycle evidence without inventing a win/loss label."""
    value = text.lower().strip()
    if any(term in value for term in POSITIVE_TERMINAL):
        return {
            "label_class": "gold_terminal",
            "outcome": 1,
            "weight": LABEL_WEIGHTS["gold_terminal"],
            "terminal": True,
        }
    if any(term in value for term in NEGATIVE_TERMINAL):
        return {
            "label_class": "gold_terminal",
            "outcome": 0,
            "weight": LABEL_WEIGHTS["gold_terminal"],
            "terminal": True,
        }
    if any(term in value for term in POSITIVE_INTERMEDIATE):
        return {
            "label_class": "gold_intermediate",
            "outcome": 1,
            "weight": LABEL_WEIGHTS["gold_intermediate"],
            "terminal": False,
        }
    if any(term in value for term in ENGAGEMENT):
        return {
            "label_class": "gold_engagement",
            "outcome": 1,
            "weight": LABEL_WEIGHTS["gold_engagement"],
            "terminal": False,
        }
    if any(term in value for term in DELIVERY):
        return {
            "label_class": "gold_delivery",
            "outcome": None,
            "weight": LABEL_WEIGHTS["gold_delivery"],
            "terminal": False,
        }
    return {
        "label_class": "unlabelled",
        "outcome": None,
        "weight": 0.0,
        "terminal": False,
    }


def calibration_readiness(labels: list[dict[str, Any]]) -> dict[str, Any]:
    """Decide whether labels justify replacing heuristic probabilities."""
    counts: dict[str, int] = defaultdict(int)
    gold_positive = 0
    gold_negative = 0
    observed_positive = 0
    observed_negative = 0

    for label in labels:
        tier = str(label.get("label_class") or label.get("tier") or "unlabelled")
        counts[tier] += 1
        outcome = label.get("outcome")
        if tier == "gold_terminal":
            if outcome in {1, True}:
                gold_positive += 1
            elif outcome in {0, False}:
                gold_negative += 1
        elif tier == "observed":
            if outcome in {1, True}:
                observed_positive += 1
            elif outcome in {0, False}:
                observed_negative += 1

    gold_terminal = gold_positive + gold_negative
    observed_total = observed_positive + observed_negative
    commercial_ready = (
        gold_terminal >= 100
        and gold_positive >= 30
        and gold_negative >= 30
    )
    event_ready = (
        observed_total >= 500
        and observed_positive >= 50
        and observed_negative >= 50
    )

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
        "gold_terminal": {
            "total": gold_terminal,
            "positive": gold_positive,
            "negative": gold_negative,
            "target": "100 total with at least 30 positive and 30 negative",
        },
        "observed": {
            "total": observed_total,
            "positive": observed_positive,
            "negative": observed_negative,
            "target": "500 total with at least 50 positive and 50 negative",
        },
        "proxy_policy": "proxy labels never make a model calibrated on their own",
    }


def empirical_calibration(rows: list[dict[str, Any]], bins: int = 10) -> dict[str, Any]:
    """Compute weighted Brier score and reliability bins without external ML dependencies."""
    clean = []
    for row in rows:
        probability = row.get("probability")
        outcome = row.get("outcome")
        if not isinstance(probability, (int, float)) or outcome not in {0, 1, False, True}:
            continue
        probability = max(0.0, min(1.0, float(probability)))
        tier = str(row.get("label_class") or row.get("tier") or "observed")
        weight = float(row.get("weight") or LABEL_WEIGHTS.get(tier, 0.3))
        clean.append((probability, int(bool(outcome)), max(0.0, weight)))

    if not clean:
        return {"samples": 0, "weighted_brier_score": None, "bins": []}

    total_weight = sum(weight for _, _, weight in clean)
    if total_weight <= 0:
        total_weight = float(len(clean))
        clean = [(p, o, 1.0) for p, o, _ in clean]

    brier = sum(weight * (probability - outcome) ** 2 for probability, outcome, weight in clean)
    brier /= total_weight

    grouped: dict[int, list[tuple[float, int, float]]] = defaultdict(list)
    bin_count = max(2, min(int(bins), 20))
    for probability, outcome, weight in clean:
        index = min(bin_count - 1, int(probability * bin_count))
        grouped[index].append((probability, outcome, weight))

    reliability = []
    for index in sorted(grouped):
        items = grouped[index]
        weight_sum = sum(item[2] for item in items) or float(len(items))
        mean_prediction = sum(item[0] * item[2] for item in items) / weight_sum
        observed_rate = sum(item[1] * item[2] for item in items) / weight_sum
        reliability.append(
            {
                "bin": index,
                "samples": len(items),
                "mean_prediction": round(mean_prediction, 4),
                "observed_rate": round(observed_rate, 4),
            }
        )

    return {
        "samples": len(clean),
        "weighted_brier_score": round(brier, 6),
        "bins": reliability,
    }


def select_active_learning(
    candidates: list[dict[str, Any]],
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Prioritise uncertain, high-value or model-disagreement cases for review."""
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
        value_factor = min(1.0, max(0.0, value / 100.0))
        priority = 0.55 * uncertainty + 0.30 * disagreement + 0.15 * value_factor
        ranked.append(
            {
                **candidate,
                "active_learning_priority": round(priority, 4),
                "uncertainty": round(uncertainty, 4),
                "model_disagreement": round(disagreement, 4),
            }
        )
    return sorted(
        ranked,
        key=lambda row: row["active_learning_priority"],
        reverse=True,
    )[: max(1, min(limit, 500))]


def observed_event_labels(
    company_id: str,
    cutoff: datetime,
    horizon_days: int = 365,
) -> list[dict[str, Any]]:
    """Create leakage-safe public-event labels from signals observed after a cutoff."""
    cutoff = _aware(cutoff)
    horizon = cutoff + timedelta(days=max(1, min(horizon_days, 3650)))
    signals = list_signals(company_id)
    labels = []

    for event, signal_kinds in EVENT_SIGNAL_MAP.items():
        future = [
            signal
            for signal in signals
            if signal.kind in signal_kinds
            and cutoff < _aware(signal.detected_at) <= horizon
        ]
        labels.append(
            {
                "company_id": company_id,
                "event": event,
                "cutoff": cutoff,
                "horizon_days": horizon_days,
                "outcome": 1 if future else 0,
                "label_class": "observed",
                "weight": LABEL_WEIGHTS["observed"],
                "evidence_ids": [
                    evidence_id
                    for signal in future
                    for evidence_id in (signal.evidence_ids or [])
                ],
                "observed_signal_ids": [signal.id for signal in future],
                "leakage_policy": "only signals detected after cutoff and within horizon",
            }
        )
    return labels


def batch_observed_labels(
    cutoff: datetime,
    horizon_days: int = 365,
    limit: int = 10000,
) -> list[dict[str, Any]]:
    """Generate observed labels for the indexed company universe."""
    labels = []
    for company in list_companies(limit=max(1, min(limit, 10000))):
        labels.extend(observed_event_labels(company.id, cutoff, horizon_days))
    return labels
