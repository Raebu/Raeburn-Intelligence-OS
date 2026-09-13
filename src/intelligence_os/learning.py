from __future__ import annotations

from collections import defaultdict

from .db import list_outcomes
from .service import digital_twin

POSITIVE = {"won", "converted", "proposal", "meeting", "qualified"}
NEGATIVE = {"lost", "rejected", "no_response", "disqualified"}


def calibration() -> dict:
    grouped: dict[str, dict[str, float]] = defaultdict(
        lambda: {"positive": 0.0, "negative": 0.0, "revenue": 0.0, "count": 0.0}
    )
    for row in list_outcomes():
        bucket = grouped[row.opportunity_kind]
        bucket["count"] += 1
        bucket["revenue"] += row.revenue_gbp or 0.0
        if row.outcome.lower() in POSITIVE:
            bucket["positive"] += 1
        elif row.outcome.lower() in NEGATIVE:
            bucket["negative"] += 1
    result = {}
    for kind, bucket in grouped.items():
        total = bucket["positive"] + bucket["negative"]
        conversion = bucket["positive"] / total if total else None
        if total < 3:
            multiplier = 1.0
            confidence = 0.2
        else:
            multiplier = 0.75 + min(0.5, (conversion or 0.0) * 0.5)
            confidence = min(1.0, total / 20)
        result[kind] = {
            **bucket,
            "conversion_rate": conversion,
            "score_multiplier": round(multiplier, 3),
            "confidence": round(confidence, 3),
        }
    return {"kinds": result, "method": "outcome-calibrated-multiplier-v1"}


def calibrated_opportunities(company_id: str) -> list[dict]:
    twin = digital_twin(company_id)
    learned = calibration()["kinds"]
    rows = []
    for opportunity in twin["opportunities"]:
        kind = opportunity["kind"]
        learned_row = learned.get(kind, {})
        multiplier = float(learned_row.get("score_multiplier", 1.0))
        score = min(100.0, max(0.0, opportunity["score"] * multiplier))
        rows.append(
            {
                **opportunity,
                "base_score": opportunity["score"],
                "score": round(score, 1),
                "learning_multiplier": multiplier,
                "learning_confidence": learned_row.get("confidence", 0.0),
            }
        )
    return sorted(rows, key=lambda row: (row["score"], row["confidence"]), reverse=True)
