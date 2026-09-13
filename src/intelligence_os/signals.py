from __future__ import annotations

from datetime import UTC, datetime
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
        strength=strength,
        confidence=confidence,
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


def derive_signals(company_id: str, evidence: list[EvidenceRow]) -> list[SignalRow]:
    now = datetime.now(UTC)
    rows: list[SignalRow] = []
    latest_profile = next(
        (item for item in evidence if item.fact_type == "company_profile"),
        None,
    )
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
    resigned = [item for item in officer_items if item.get("resigned_on")]
    if resigned and latest_officers:
        rows.append(
            _signal(
                company_id,
                SignalKind.DIRECTOR_CHANGE,
                min(0.9, 0.35 + 0.08 * len(resigned)),
                0.95,
                f"Companies House records {len(resigned)} resigned officer appointment(s).",
                [latest_officers.id],
                now,
            )
        )

    latest_filings = next(
        (item for item in evidence if item.fact_type == "filing_history"),
        None,
    )
    filing_items = _items(latest_filings)
    filing_text = " ".join(
        f"{item.get('category', '')} {item.get('description', '')} {item.get('type', '')}".lower()
        for item in filing_items[:100]
    )
    if latest_filings and any(
        phrase in filing_text
        for phrase in ("insolvency", "liquidation", "administration", "strike-off", "compulsory")
    ):
        rows.append(
            _signal(
                company_id,
                SignalKind.DISTRESS,
                0.85,
                0.9,
                "Recent filing history contains a potential distress or insolvency indicator.",
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

    technology = next(
        (item for item in evidence if item.fact_type == "technology_profile"),
        None,
    )
    if technology:
        technologies = set(technology.value.get("technologies") or [])
        modern = technologies.intersection({"react", "nextjs", "stripe", "hubspot", "intercom"})
        if modern:
            rows.append(
                _signal(
                    company_id,
                    SignalKind.DIGITAL_TRANSFORMATION,
                    min(0.8, 0.35 + 0.08 * len(modern)),
                    0.75,
                    "Public website technology indicates active digital capability or transformation.",
                    [technology.id],
                    now,
                )
            )
        if technologies and not modern:
            rows.append(
                _signal(
                    company_id,
                    SignalKind.AUTOMATION_GAP,
                    0.35,
                    0.55,
                    "Public technology footprint shows limited modern application-layer tooling.",
                    [technology.id],
                    now,
                )
            )

    job_scans = [item for item in evidence if item.fact_type == "job_scan"]
    if job_scans:
        latest_jobs = job_scans[0]
        job_count = int(latest_jobs.value.get("job_count", 0))
        tech_jobs = int(latest_jobs.value.get("technology_job_count", 0))
        if tech_jobs:
            rows.append(
                _signal(
                    company_id,
                    SignalKind.TECH_HIRING,
                    min(1.0, 0.35 + 0.08 * tech_jobs),
                    0.7,
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
                        min(1.0, 0.4 + growth / 2),
                        0.7,
                        f"Observed careers-page vacancies increased from {previous_count} to {job_count}.",
                        [latest_jobs.id, job_scans[1].id],
                        now,
                    )
                )

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
        confidence = min(0.95, 0.65 + (0.05 * min(len(procurement), 6)))
        strength = min(1.0, 0.35 + (0.1 * min(len(procurement), 6)))
        rows.append(
            _signal(
                company_id,
                SignalKind.PROCUREMENT_ACTIVITY,
                strength,
                confidence,
                f"{len(procurement)} public procurement notice(s) are linked to this company.",
                [item.id for item in procurement[:10]],
                now,
            )
        )

    contract_wins = [item for item in evidence if item.fact_type == "contract_award"]
    if contract_wins:
        rows.append(
            _signal(
                company_id,
                SignalKind.PUBLIC_CONTRACT_WIN,
                min(1.0, 0.55 + (0.1 * min(len(contract_wins), 4))),
                0.85,
                f"{len(contract_wins)} public contract award(s) are linked to this company.",
                [item.id for item in contract_wins[:10]],
                now,
            )
        )

    return rows
