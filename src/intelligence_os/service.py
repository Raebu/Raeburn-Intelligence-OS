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
from .models import OpportunityKind, OpportunityScoreRequest, SignalInput, SignalKind
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

ROLE_SCORE_FACTORS: dict[str, dict[OpportunityKind, float]] = {
    "technology_supplier_or_partner": {
        OpportunityKind.AUTOMATION: 0.5,
        OpportunityKind.CONSULTING: 0.55,
        OpportunityKind.RECRUITMENT: 0.8,
        OpportunityKind.SOFTWARE: 0.45,
        OpportunityKind.PROCUREMENT: 1.0,
        OpportunityKind.MA: 0.9,
        OpportunityKind.MARKET_ENTRY: 0.9,
    },
    "recruitment_supplier_or_partner": {
        OpportunityKind.AUTOMATION: 0.75,
        OpportunityKind.CONSULTING: 0.65,
        OpportunityKind.RECRUITMENT: 0.25,
        OpportunityKind.SOFTWARE: 0.75,
        OpportunityKind.PROCUREMENT: 1.0,
        OpportunityKind.MA: 0.9,
        OpportunityKind.MARKET_ENTRY: 0.9,
    },
    "consulting_supplier_or_partner": {
        OpportunityKind.AUTOMATION: 0.75,
        OpportunityKind.CONSULTING: 0.35,
        OpportunityKind.RECRUITMENT: 0.8,
        OpportunityKind.SOFTWARE: 0.75,
        OpportunityKind.PROCUREMENT: 1.0,
        OpportunityKind.MA: 0.9,
        OpportunityKind.MARKET_ENTRY: 0.9,
    },
    "professional_services": {
        OpportunityKind.AUTOMATION: 0.9,
        OpportunityKind.CONSULTING: 0.85,
        OpportunityKind.RECRUITMENT: 0.9,
        OpportunityKind.SOFTWARE: 0.9,
        OpportunityKind.PROCUREMENT: 1.0,
        OpportunityKind.MA: 0.95,
        OpportunityKind.MARKET_ENTRY: 0.95,
    },
}


def classify_commercial_role(company: CompanyRow) -> dict[str, object]:
    sics = {str(code) for code in company.sic_codes or []}
    name = company.name.upper()
    if any(code.startswith(("62", "63", "582")) for code in sics):
        return {
            "role": "technology_supplier_or_partner",
            "confidence": 0.8,
            "reason": "Technology/software SIC classification suggests a supplier, partner or competitor rather than a default end-customer.",
        }
    if sics.intersection({"78109", "78101", "78200", "78300"}) or any(
        term in name for term in ("RECRUITMENT", "STAFFING", "TALENT SOLUTIONS")
    ):
        return {
            "role": "recruitment_supplier_or_partner",
            "confidence": 0.85,
            "reason": "Recruitment/employment-services activity suggests a sector supplier or partner.",
        }
    if sics.intersection({"70210", "70221", "70229"}) and any(
        term in name for term in ("CONSULT", "ADVISORY", "MANAGEMENT")
    ):
        return {
            "role": "consulting_supplier_or_partner",
            "confidence": 0.7,
            "reason": "Management-consulting activity suggests potential partner or competitor overlap.",
        }
    if any(code.startswith(("691", "692")) for code in sics):
        return {
            "role": "professional_services",
            "confidence": 0.75,
            "reason": "Legal/accounting professional-services classification warrants a modest fit adjustment rather than exclusion.",
        }
    return {
        "role": "prospect",
        "confidence": 0.7,
        "reason": "No strong supplier/competitor SIC pattern detected; treat as a normal prospect pending deeper qualification.",
    }


def _apply_role_adjustment(company: CompanyRow, opportunities: list) -> tuple[dict[str, object], list]:
    role = classify_commercial_role(company)
    role_name = str(role["role"])
    factors = ROLE_SCORE_FACTORS.get(role_name, {})
    adjusted = []
    for opportunity in opportunities:
        factor = factors.get(opportunity.kind, 1.0)
        if factor == 1.0:
            adjusted.append(opportunity)
            continue
        score = round(opportunity.score * factor)
        rationale = (
            f"{opportunity.rationale} Commercial-role adjustment ×{factor:.2f}: "
            f"{role['reason']}"
        )
        adjusted.append(opportunity.model_copy(update={"score": score, "rationale": rationale}))
    return role, adjusted


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
    role, opportunities = _apply_role_adjustment(company, score_all(request))
    return {
        "company": company.model_dump(),
        "commercial_role": role,
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
                        "commercial_role": twin["commercial_role"],
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
            "contracts_finder": {"configured": True, "mode": "public_ocds"},
            "find_a_tender": {"configured": True, "mode": "public_ocds"},
            "nomis": {
                "configured": True,
                "mode": "authenticated" if settings.nomis_uid else "anonymous_25000_cell_limit",
            },
            "website_technology": {"configured": True, "mode": "public_web"},
            "public_careers": {"configured": True, "mode": "public_web"},
        },
    }
