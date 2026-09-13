from __future__ import annotations

from .db import (
    CompanyRow,
    get_company,
    get_company_by_number,
    list_companies,
    list_evidence,
    list_signals,
    replace_signals,
    save_evidence,
    upsert_company,
)
from .models import OpportunityScoreRequest, SignalInput, SignalKind
from .scoring import score_all
from .signals import derive_signals
from .uk import CompaniesHouseClient


def refresh_company(company_number: str) -> CompanyRow:
    client = CompaniesHouseClient()
    payload = client.company_profile(company_number)
    company, evidence = client.normalize(payload)
    company = upsert_company(company)
    save_evidence(evidence)
    derived = derive_signals(company.id, list_evidence(company.id))
    replace_signals(company.id, derived)
    return company


def digital_twin(company_id: str) -> dict:
    company = get_company(company_id)
    if company is None:
        raise KeyError(company_id)
    evidence = list_evidence(company_id)
    signals = list_signals(company_id)
    request = OpportunityScoreRequest(
        company_id=company_id,
        signals=[
            SignalInput(
                kind=SignalKind(item.kind),
                strength=item.strength,
                confidence=item.confidence,
                evidence_ids=item.evidence_ids,
            )
            for item in signals
        ],
    )
    opportunities = score_all(request)
    return {
        "company": company.model_dump(),
        "evidence": [item.model_dump() for item in evidence],
        "signals": [item.model_dump() for item in signals],
        "opportunities": [item.model_dump() for item in opportunities],
    }


def opportunity_feed(limit: int = 100) -> list[dict]:
    results: list[dict] = []
    for company in list_companies(limit=limit):
        twin = digital_twin(company.id)
        for opportunity in twin["opportunities"]:
            if opportunity["score"] > 0:
                results.append(
                    {
                        "company": company.model_dump(),
                        "opportunity": opportunity,
                    }
                )
    return sorted(
        results,
        key=lambda item: (
            item["opportunity"]["score"],
            item["opportunity"]["confidence"],
        ),
        reverse=True,
    )


def resolve_company_number(company_number: str) -> CompanyRow | None:
    return get_company_by_number(company_number)
