from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .db import EvidenceRow, SignalRow
from .models import SignalKind


def derive_signals(company_id: str, evidence: list[EvidenceRow]) -> list[SignalRow]:
    now = datetime.now(timezone.utc)
    rows: list[SignalRow] = []
    latest_profile = next((item for item in evidence if item.fact_type == "company_profile"), None)
    if latest_profile:
        value = latest_profile.value
        status = str(value.get("company_status", "")).lower()
        if status and status != "active":
            rows.append(
                SignalRow(
                    id=str(uuid4()), company_id=company_id, kind=SignalKind.DISTRESS.value,
                    strength=0.75, confidence=0.95, detected_at=now,
                    explanation=f"Companies House status is {status}.",
                    evidence_ids=[latest_profile.id],
                )
            )
        sic_codes = value.get("sic_codes") or []
        digital_sics = {"62012", "62020", "62090", "63110", "63120"}
        if digital_sics.intersection(set(sic_codes)):
            rows.append(
                SignalRow(
                    id=str(uuid4()), company_id=company_id, kind=SignalKind.DIGITAL_TRANSFORMATION.value,
                    strength=0.35, confidence=0.6, detected_at=now,
                    explanation="Company SIC classification indicates material digital/technology activity.",
                    evidence_ids=[latest_profile.id],
                )
            )
    return rows
