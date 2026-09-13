from __future__ import annotations

from .config import get_settings
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
from .sources import get_sources
from .uk import CompaniesHouseClient, ExternalServiceError

ACTION_BY_KIND = {
    "automation": "Offer an automation and process-efficiency assessment.",
    "consulting": "Open a transformation consulting conversation.",
    "recruitment": "Review hiring needs and identify relevant recruitment support.",
    "software": "Identify a software product or workflow that can remove friction.",
    "procurement": "Review the procurement event and decide whether Raeburn should bid or partner.",
    "ma": "Run a deeper strategic and acquisition-screening review.",
    "market_entry": "Assess the market, competitors and a practical entry route.",
}


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
        "opportunities": [
            {
                **item.model_dump(),
                "recommended_action": ACTION_BY_KIND[item.kind.value],
            }
            for item in opportunities
        ],
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


def company_index(limit: int = 100) -> list[dict]:
    return [row.model_dump() for row in list_companies(limit=limit)]


def discover_companies(query: str, limit: int = 20) -> list[dict]:
    client = CompaniesHouseClient()
    return client.search(query, items_per_page=limit)


def discover_and_refresh(query: str, limit: int = 10) -> dict:
    matches = discover_companies(query, limit=limit)
    refreshed: list[dict] = []
    failures: list[dict] = []
    for item in matches:
        company_number = item.get("company_number")
        if not company_number:
            continue
        try:
            refreshed.append(refresh_company(str(company_number)).model_dump())
        except (ExternalServiceError, KeyError) as exc:
            failures.append({"company_number": company_number, "error": str(exc)})
    return {"matches": len(matches), "refreshed": refreshed, "failures": failures}


def system_status() -> dict:
    settings = get_settings()
    companies = list_companies(limit=10000)
    opportunities = opportunity_feed(limit=10000)
    return {
        "environment": settings.environment,
        "companies_indexed": len(companies),
        "opportunities_ranked": len(opportunities),
        "sources_registered": len(get_sources()),
        "integrations": {
            "companies_house": {
                "configured": bool(settings.companies_house_api_key),
                "mode": "live" if settings.companies_house_api_key else "credential_required",
            },
            "contracts_finder": {"configured": True, "mode": "public_endpoint"},
        },
    }
