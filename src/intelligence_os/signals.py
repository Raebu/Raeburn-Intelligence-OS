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
