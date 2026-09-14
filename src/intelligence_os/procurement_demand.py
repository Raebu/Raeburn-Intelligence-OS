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
    "data platform": 0.8,
    "data management": 0.8,
    "cloud": 0.75,
    "cyber": 0.75,
    "integration": 0.7,
    "workflow": 0.7,
    "consulting": 0.65,
    "professional services": 0.6,
    "recruitment": 0.6,
    "managed service": 0.55,
    "resource management": 0.8,
    "capacity management": 0.8,
}

WEAK_KEYWORDS = {"data", "staffing"}
AWARD_MARKERS = {
    "contract award",
    "award of a contract",
    "awarded to",
    "contract has been awarded",
    "this contract was awarded",
}
LIVE_MARKERS = {
    "invitation to tender",
    "invite bids",
    "invites bids",
    "seeking submissions",
    "seeking tenders",
    "market engagement",
    "request for information",
    "rfi",
    "procure",
    "procurement",
    "tender",
    "framework agreement",
    "dynamic purchasing system",
    "dps",
    "challenge",
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


def _text(record: dict[str, Any]) -> str:
    return " ".join(
        str(part or "")
        for part in (
            record.get("title"),
            record.get("description"),
            " ".join(str(tag) for tag in record.get("tags", [])),
        )
    ).lower()


def _is_live_tender(record: dict[str, Any], now: datetime) -> bool:
    tags = {str(tag).lower() for tag in record.get("tags", [])}
    text = _text(record)

    if tags & {"award", "contract"}:
        return False
    if any(marker in text for marker in AWARD_MARKERS):
        return False

    parsed = _parse_date(record.get("date"))
    if parsed and (now - parsed).days > 45:
        return False

    if "tender" in tags or "planning" in tags:
        return True
    return any(marker in text for marker in LIVE_MARKERS)


def score_procurement_demand(record: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if not _is_live_tender(record, now):
        return {"score": 0, "excluded": "not_live_tender"}

    text = _text(record)
    strong_matches = [keyword for keyword in KEYWORD_WEIGHTS if keyword in text]
    weak_matches = [keyword for keyword in WEAK_KEYWORDS if keyword in text]

    # Weak generic terms alone should never create a demand opportunity.
    if not strong_matches:
        return {"score": 0, "excluded": "no_strong_commercial_match"}

    keyword_score = min(0.65, sum(KEYWORD_WEIGHTS[keyword] for keyword in strong_matches) / 4)
    if weak_matches:
        keyword_score = min(0.65, keyword_score + 0.03 * len(weak_matches))

    amount = _value_amount(record)
    value_score = min(0.2, math.log10(amount + 1) / 35) if amount else 0.0

    parsed = _parse_date(record.get("date"))
    if parsed:
        age_days = max(0, (now - parsed).days)
        recency_score = 0.15 if age_days <= 7 else 0.12 if age_days <= 30 else 0.05
    else:
        recency_score = 0.02

    score = round(min(1.0, keyword_score + value_score + recency_score) * 100)
    return {
        "score": score,
        "matched_keywords": strong_matches + weak_matches,
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
    ranked = [item for item in ranked if item.get("score", 0) > 0]
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]
