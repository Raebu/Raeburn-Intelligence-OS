from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from .db import EvidenceRow, get_company, list_evidence, replace_signals, save_evidence
from .signals import derive_signals
from .uk import CompaniesHouseClient


def enrich_ownership(company_id: str) -> dict:
    company = get_company(company_id)
    if company is None or not company.company_number:
        raise KeyError(company_id)
    client = CompaniesHouseClient()
    number = company.company_number
    payload = client._get(  # noqa: SLF001 - shared authenticated CH transport
        f"/company/{number}/persons-with-significant-control",
        params={"items_per_page": 100},
    )
    observed = datetime.now(UTC)
    digest = sha256(repr(payload).encode()).hexdigest()[:20]
    evidence_id = f"ch-psc:{company_id}:{digest}"
    row = EvidenceRow(
        id=evidence_id,
        company_id=company_id,
        source_id="companies-house",
        fact_type="persons_with_significant_control",
        observed_at=observed,
        source_url=(
            f"{client.base_url}/company/{number}/persons-with-significant-control"
        ),
        value=payload,
        confidence=1.0,
        raw_reference=number,
    )
    save_evidence([row])
    replace_signals(company_id, derive_signals(company_id, list_evidence(company_id)))
    items = payload.get("items", [])
    return {
        "company_id": company_id,
        "persons_with_significant_control": len(items),
        "evidence_id": evidence_id,
    }
