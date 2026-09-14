from __future__ import annotations

import math
import re
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from .db import EvidenceRow, SignalRow
from .models import SignalKind


def _signal(
    company_id: str,
    kind: SignalKind,
    strength: float,
    confidence: float,
    explanation: str,
    evidence_ids: list[str],
    detected_at: datetime,
) -> SignalRow:
    return SignalRow(
        id=str(uuid4()),
        company_id=company_id,
        kind=kind.value,
        strength=max(0.0, min(1.0, strength)),
        confidence=max(0.0, min(1.0, confidence)),
        detected_at=detected_at,
        explanation=explanation,
        evidence_ids=evidence_ids,
    )


def _items(row: EvidenceRow | None) -> list[dict]:
    if row is None:
        return []
    value = row.value or {}
    items = value.get("items", []) if isinstance(value, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _recent(value: object, now: datetime, days: int = 365) -> bool:
    parsed = _parse_date(value)
    if parsed is None:
        return False
    return now.date() - timedelta(days=days) <= parsed <= now.date()


def _recent_distress_filings(items: list[dict], now: datetime) -> list[dict]:
    distress_terms = (
        "administration",
        "administrator",
        "liquidation",
        "liquidator",
        "winding-up",
        "winding up",
        "compulsory strike-off",
        "gazette-notice-compulsary",
        "gazette-notice-compulsory",
        "receiver",
        "receivership",
        "creditors voluntary",
        "cv01",
    )
    false_positive_terms = (
        "solvency statement",
        "capital reduction",
        "reduction capital",
        "filings brought up to date",
        "gazette-filings-brought-up-to-date",
    )
    matches: list[dict] = []
    for item in items:
        if not _recent(item.get("date") or item.get("action_date"), now):
            continue
        description_values = item.get("description_values") or {}
        extra = description_values.get("description", "") if isinstance(description_values, dict) else ""
        text = " ".join(
            str(part or "")
            for part in (
                item.get("category"),
                item.get("description"),
                item.get("type"),
                item.get("subcategory"),
                extra,
            )
        ).lower()
        if any(term in text for term in false_positive_terms):
            continue
        if any(term in text for term in distress_terms):
            matches.append(item)
    return matches


def _tokens(value: object) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(value or "").lower())
    stop = {"the", "and", "for", "of", "to", "a", "an", "uk", "limited", "ltd", "plc", "llp"}
    return {word for word in words if len(word) > 1 and word not in stop and not word.isdigit()}


def _amount(value: dict) -> float:
    try:
        return max(0.0, float((value.get("award_value") or {}).get("amount") or 0))
    except (TypeError, ValueError):
        return 0.0


def _award_date(row: EvidenceRow) -> date | None:
    value = row.value or {}
    return _parse_date(value.get("date") or value.get("award_date") or value.get("published_date"))


def _award_duplicate(left: EvidenceRow, right: EvidenceRow) -> bool:
    a = left.value or {}
    b = right.value or {}
    buyer_a = _tokens((a.get("buyer") or {}).get("name"))
    buyer_b = _tokens((b.get("buyer") or {}).get("name"))
    if buyer_a and buyer_b and buyer_a != buyer_b:
        return False
    amount_a = _amount(a)
    amount_b = _amount(b)
    if amount_a and amount_b and abs(amount_a - amount_b) > max(1.0, 0.005 * max(amount_a, amount_b)):
        return False
    title_a = _tokens(a.get("title"))
    title_b = _tokens(b.get("title"))
    if not title_a or not title_b:
        return amount_a > 0 and amount_b > 0 and buyer_a == buyer_b
    overlap = len(title_a & title_b) / max(1, min(len(title_a), len(title_b)))
    return overlap >= 0.6


def _dedupe_awards(rows: list[EvidenceRow]) -> list[EvidenceRow]:
    unique: list[EvidenceRow] = []
    for row in sorted(rows, key=lambda item: item.observed_at, reverse=True):
        if any(_award_duplicate(row, existing) for existing in unique):
            continue
        unique.append(row)
    return unique


def _award_strength(rows: list[EvidenceRow], now: datetime) -> tuple[float, float, str]:
    unique = _dedupe_awards(rows)
    total_value = sum(_amount(row.value or {}) for row in unique)
    largest = max((_amount(row.value or {}) for row in unique), default=0.0)
    if largest >= 10_000_000:
        base = 0.95
    elif largest >= 1_000_000:
        base = 0.85
    elif largest >= 250_000:
        base = 0.75
    elif largest >= 50_000:
        base = 0.65
    elif largest >= 10_000:
        base = 0.55
    elif largest > 0:
        base = 0.4
    else:
        base = 0.5

    dates = [parsed for row in unique if (parsed := _award_date(row)) is not None]
    if dates:
        age_days = max(0, (now.date() - max(dates)).days)
        recency = 1.0 if age_days <= 90 else 0.9 if age_days <= 180 else 0.75 if age_days <= 365 else 0.55
    else:
        recency = 0.8
    strength = min(1.0, base * recency + min(0.12, 0.04 * max(0, len(unique) - 1)))
    confidence = 0.9 if largest > 0 else 0.8
    value_text = f"£{total_value:,.0f}" if total_value > 0 else "undisclosed value"
    explanation = f"{len(unique)} deduplicated public contract award(s), total {value_text}."
    return strength, confidence, explanation


def _financial_rows(evidence: list[EvidenceRow]) -> list[EvidenceRow]:
    rows = [row for row in evidence if row.fact_type == "financial_metrics"]
    return sorted(
        rows,
        key=lambda row: _parse_date((row.value or {}).get("filing_date")) or date.min,
        reverse=True,
    )


def _growth_signal(
    company_id: str,
    rows: list[EvidenceRow],
    metric: str,
    kind: SignalKind,
    label: str,
    now: datetime,
) -> SignalRow | None:
    with_metric = [row for row in rows if isinstance((row.value or {}).get(metric), (int, float))]
    if len(with_metric) < 2:
        return None
    latest, previous = with_metric[0], with_metric[1]
    current = float(latest.value[metric])
    prior = float(previous.value[metric])
    if prior <= 0 or current <= prior:
        return None
    growth = (current - prior) / prior
    strength = min(1.0, 0.4 + math.log1p(growth * 10) / 3)
    return _signal(
        company_id,
        kind,
        strength,
        0.85,
        f"Filed {label} increased from {prior:,.0f} to {current:,.0f} ({growth:.1%}).",
        [latest.id, previous.id],
        now,
    )


def derive_signals(company_id: str, evidence: list[EvidenceRow]) -> list[SignalRow]:
    now = datetime.now(UTC)
    rows: list[SignalRow] = []
    latest_profile = next((item for item in evidence if item.fact_type == "company_profile"), None)
    if latest_profile:
        value = latest_profile.value
        status = str(value.get("company_status", "")).lower()
        if status and status != "active":
            rows.append(
                _signal(
                    company_id,
                    SignalKind.DISTRESS,
                    0.75,
                    0.95,
                    f"Companies House status is {status}.",
                    [latest_profile.id],
                    now,
                )
            )

        sic_codes = set(value.get("sic_codes") or [])
        digital_sics = {"62012", "62020", "62090", "63110", "63120"}
        if digital_sics.intersection(sic_codes):
            rows.append(
                _signal(
                    company_id,
                    SignalKind.DIGITAL_TRANSFORMATION,
                    0.35,
                    0.6,
                    "Company SIC classification indicates digital or technology activity.",
                    [latest_profile.id],
                    now,
                )
            )

    latest_officers = next((item for item in evidence if item.fact_type == "officers"), None)
    officer_items = _items(latest_officers)
    recent_resigned = [item for item in officer_items if _recent(item.get("resigned_on"), now)]
    recent_appointed = [
        item for item in officer_items if not item.get("resigned_on") and _recent(item.get("appointed_on"), now)
    ]
    recent_changes = len(recent_resigned) + len(recent_appointed)
    if recent_changes and latest_officers:
        rows.append(
            _signal(
                company_id,
                SignalKind.DIRECTOR_CHANGE,
                min(0.9, 0.35 + 0.08 * recent_changes),
                0.95,
                (
                    "Companies House records "
                    f"{len(recent_appointed)} recent officer appointment(s) and "
                    f"{len(recent_resigned)} recent resignation(s) in the last 12 months."
                ),
                [latest_officers.id],
                now,
            )
        )

    latest_filings = next((item for item in evidence if item.fact_type == "filing_history"), None)
    filing_items = _items(latest_filings)
    distress_filings = _recent_distress_filings(filing_items, now)
    if latest_filings and distress_filings:
        newest = distress_filings[0]
        detail = str(
            newest.get("description")
            or (newest.get("description_values") or {}).get("description")
            or newest.get("type")
            or "distress-related filing"
        )
        rows.append(
            _signal(
                company_id,
                SignalKind.DISTRESS,
                min(0.95, 0.75 + 0.05 * len(distress_filings)),
                0.9,
                f"Recent Companies House filing indicates potential distress: {detail}.",
                [latest_filings.id],
                now,
            )
        )

    insolvency = next((item for item in evidence if item.fact_type == "insolvency"), None)
    if insolvency and insolvency.value:
        rows.append(
            _signal(
                company_id,
                SignalKind.DISTRESS,
                1.0,
                0.99,
                "Companies House reports insolvency information for this company.",
                [insolvency.id],
                now,
            )
        )

    technology = next((item for item in evidence if item.fact_type == "technology_profile"), None)
    if technology:
        technologies = set(technology.value.get("technologies") or [])
        modern = technologies.intersection({"react", "nextjs", "stripe", "hubspot", "intercom"})
        automation_stack = technologies.intersection({"hubspot", "stripe", "intercom"})
        if modern:
            rows.append(
                _signal(
                    company_id,
                    SignalKind.DIGITAL_TRANSFORMATION,
                    min(0.85, 0.4 + 0.09 * len(modern)),
                    0.8,
                    f"Public website exposes modern technology: {', '.join(sorted(modern))}.",
                    [technology.id],
                    now,
                )
            )
        if technologies and not automation_stack:
            rows.append(
                _signal(
                    company_id,
                    SignalKind.AUTOMATION_GAP,
                    min(0.7, 0.4 + 0.04 * len(technologies)),
                    0.6,
                    "Public technology footprint has no detected CRM/payment/customer-automation tooling.",
                    [technology.id],
                    now,
                )
            )

    job_scans = sorted(
        [item for item in evidence if item.fact_type == "job_scan"],
        key=lambda item: item.observed_at,
        reverse=True,
    )
    if job_scans:
        latest_jobs = job_scans[0]
        job_count = int(latest_jobs.value.get("job_count", 0))
        tech_jobs = int(latest_jobs.value.get("technology_job_count", 0))
        if tech_jobs:
            rows.append(
                _signal(
                    company_id,
                    SignalKind.TECH_HIRING,
                    min(1.0, 0.4 + 0.08 * tech_jobs),
                    0.75,
                    f"Public careers page exposes {tech_jobs} technology-related role(s).",
                    [latest_jobs.id],
                    now,
                )
            )
        if len(job_scans) > 1:
            previous_count = int(job_scans[1].value.get("job_count", 0))
            if job_count > previous_count:
                growth = (job_count - previous_count) / max(previous_count, 1)
                rows.append(
                    _signal(
                        company_id,
                        SignalKind.HIRING_GROWTH,
                        min(1.0, 0.45 + growth / 2),
                        0.75,
                        f"Observed careers-page vacancies increased from {previous_count} to {job_count}.",
                        [latest_jobs.id, job_scans[1].id],
                        now,
                    )
                )

    financials = _financial_rows(evidence)
    revenue_growth = _growth_signal(
        company_id, financials, "turnover", SignalKind.REVENUE_GROWTH, "turnover", now
    )
    if revenue_growth:
        rows.append(revenue_growth)
    headcount_growth = _growth_signal(
        company_id, financials, "employees", SignalKind.HEADCOUNT_GROWTH, "employee count", now
    )
    if headcount_growth:
        rows.append(headcount_growth)

    market_rows = [item for item in evidence if item.fact_type == "market_indicator"]
    if market_rows:
        positive = [item for item in market_rows if float(item.value.get("growth", 0)) > 0]
        if positive:
            avg_growth = sum(float(item.value.get("growth", 0)) for item in positive) / len(positive)
            rows.append(
                _signal(
                    company_id,
                    SignalKind.MARKET_GROWTH,
                    min(1.0, 0.35 + avg_growth),
                    0.75,
                    "Linked official market indicators show positive sector or labour-market movement.",
                    [item.id for item in positive[:10]],
                    now,
                )
            )

    procurement = [item for item in evidence if item.fact_type == "procurement_notice"]
    if procurement:
        recent_notices = [
            item
            for item in procurement
            if _recent((item.value or {}).get("date") or item.observed_at.date(), now, days=180)
        ]
        considered = recent_notices or procurement
        values = []
        for item in considered:
            try:
                values.append(float(((item.value or {}).get("tender_value") or {}).get("amount") or 0))
            except (TypeError, ValueError):
                pass
        max_value = max(values, default=0.0)
        value_boost = min(0.25, math.log10(max_value + 1) / 30) if max_value else 0.0
        strength = min(1.0, 0.45 + value_boost + 0.07 * min(len(considered), 5))
        confidence = min(0.95, 0.7 + 0.04 * min(len(considered), 5))
        rows.append(
            _signal(
                company_id,
                SignalKind.PROCUREMENT_ACTIVITY,
                strength,
                confidence,
                f"{len(considered)} recent public procurement notice(s) are linked to this organisation.",
                [item.id for item in considered[:10]],
                now,
            )
        )

    contract_wins = [item for item in evidence if item.fact_type == "contract_award"]
    if contract_wins:
        unique = _dedupe_awards(contract_wins)
        strength, confidence, explanation = _award_strength(unique, now)
        rows.append(
            _signal(
                company_id,
                SignalKind.PUBLIC_CONTRACT_WIN,
                strength,
                confidence,
                explanation,
                [item.id for item in unique[:10]],
                now,
            )
        )

    return rows
