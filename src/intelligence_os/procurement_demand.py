from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

KEYWORD_WEIGHTS = {
    "artificial intelligence": 1.0,
    "machine learning": 0.95,
    "automation": 0.95,
    "digital transformation": 0.9,
    "software": 0.8,
    "data": 0.75,
    "cloud": 0.75,
    "cyber": 0.75,
    "integration": 0.7,
    "workflow": 0.7,
    "consulting": 0.65,
    "professional services": 0.6,
    "recruitment": 0.6,
    "staffing": 0.6,
    "managed service": 0.55,
}


def _parse_date(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _value_amount(record: dict[str, Any]) -> float:
    value = record.get("tender_value") or record.get("award_value") or {}
    try:
        return max(0.0, float(value.get("amount") or 0))
    except (AttributeError, TypeError, ValueError):
        return 0.0


def score_procurement_demand(record: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    text = " ".join(
        str(part or "")
        for part in (
            record.get("title"),
            record.get("description"),
            " ".join(str(tag) for tag in record.get("tags", [])),
        )
    ).lower()
    matches = [keyword for keyword in KEYWORD_WEIGHTS if keyword in text]
    keyword_score = min(0.65, sum(KEYWORD_WEIGHTS[keyword] for keyword in matches) / 4)

    amount = _value_amount(record)
    value_score = min(0.2, math.log10(amount + 1) / 35) if amount else 0.0

    parsed = _parse_date(record.get("date"))
    if parsed:
        age_days = max(0, (now - parsed).days)
        recency_score = 0.15 if age_days <= 30 else 0.1 if age_days <= 90 else 0.05 if age_days <= 180 else 0.0
    else:
        recency_score = 0.03

    score = round(min(1.0, keyword_score + value_score + recency_score) * 100)
    return {
        "score": score,
        "matched_keywords": matches,
        "estimated_value": amount or None,
        "source": record.get("source"),
        "ocid": record.get("ocid"),
        "release_id": record.get("release_id"),
        "date": record.get("date"),
        "title": record.get("title"),
        "description": record.get("description"),
        "buyer": record.get("buyer"),
        "tender_value": record.get("tender_value"),
    }


def rank_procurement_demand(records: list[dict[str, Any]], limit: int = 25) -> list[dict[str, Any]]:
    ranked = [score_procurement_demand(record) for record in records]
    ranked = [item for item in ranked if item["score"] > 0]
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]
