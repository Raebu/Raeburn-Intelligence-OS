from __future__ import annotations

import re
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from .config import get_settings
from .db import EvidenceRow, get_company, list_evidence, replace_signals, save_evidence
from .signals import derive_signals
from .uk import CompaniesHouseClient, ExternalServiceError


def _now() -> datetime:
    return datetime.now(UTC)


def _evidence_id(prefix: str, company_id: str, payload: Any) -> str:
    digest = sha256(repr(payload).encode()).hexdigest()[:20]
    return f"{prefix}:{company_id}:{digest}"


def _save_and_rescore(company_id: str, rows: list[EvidenceRow]) -> None:
    save_evidence(rows)
    replace_signals(company_id, derive_signals(company_id, list_evidence(company_id)))


def enrich_companies_house(
    company_id: str,
    *,
    officers_limit: int = 100,
    filings_limit: int = 100,
) -> dict:
    company = get_company(company_id)
    if company is None or not company.company_number:
        raise KeyError(company_id)
    client = CompaniesHouseClient()
    number = company.company_number
    officers = client.officers(number, items_per_page=officers_limit)
    filings = client.filing_history(number, items_per_page=filings_limit)
    try:
        charges = client.charges(number)
    except KeyError:
        charges = {"items": []}
    try:
        insolvency = client.insolvency(number)
    except KeyError:
        insolvency = {}
    observed = _now()
    rows = [
        EvidenceRow(
            id=_evidence_id("ch-officers", company_id, officers),
            company_id=company_id,
            source_id="companies-house",
            fact_type="officers",
            observed_at=observed,
            source_url=f"{client.base_url}/company/{number}/officers",
            value=officers,
            confidence=1.0,
            raw_reference=number,
        ),
        EvidenceRow(
            id=_evidence_id("ch-filings", company_id, filings),
            company_id=company_id,
            source_id="companies-house",
            fact_type="filing_history",
            observed_at=observed,
            source_url=f"{client.base_url}/company/{number}/filing-history",
            value=filings,
            confidence=1.0,
            raw_reference=number,
        ),
        EvidenceRow(
            id=_evidence_id("ch-charges", company_id, charges),
            company_id=company_id,
            source_id="companies-house",
            fact_type="charges",
            observed_at=observed,
            source_url=f"{client.base_url}/company/{number}/charges",
            value=charges,
            confidence=1.0,
            raw_reference=number,
        ),
    ]
    if insolvency:
        rows.append(
            EvidenceRow(
                id=_evidence_id("ch-insolvency", company_id, insolvency),
                company_id=company_id,
                source_id="companies-house",
                fact_type="insolvency",
                observed_at=observed,
                source_url=f"{client.base_url}/company/{number}/insolvency",
                value=insolvency,
                confidence=1.0,
                raw_reference=number,
            )
        )
    _save_and_rescore(company_id, rows)
    return {
        "company_id": company_id,
        "officers": len(officers.get("items", [])),
        "filings": len(filings.get("items", [])),
        "charges": len(charges.get("items", [])),
        "insolvency": bool(insolvency),
    }


class TechnologyProfiler:
    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )

    def _fetch(self, url: str) -> httpx.Response:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("A valid http(s) URL is required")
        response = self.client.get(url)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"Website returned {response.status_code}") from exc
        return response

    def profile(self, url: str) -> dict[str, Any]:
        response = self._fetch(url)
        text = response.text[:1_000_000].lower()
        headers = {key.lower(): value for key, value in response.headers.items()}
        technologies: set[str] = set()
        signatures = {
            "wordpress": ["wp-content", "wp-includes"],
            "shopify": ["cdn.shopify.com", "shopify.theme"],
            "wix": ["wixstatic.com", "wix.com"],
            "squarespace": ["static1.squarespace.com", "squarespace"],
            "react": ["reactroot", "__next_data__", "data-reactroot"],
            "nextjs": ["/_next/", "__next_data__"],
            "cloudflare": ["cloudflare"],
            "google-analytics": ["googletagmanager.com", "google-analytics.com"],
            "hubspot": ["js.hs-scripts.com", "hubspot"],
            "stripe": ["js.stripe.com"],
            "intercom": ["intercomcdn.com", "intercomsettings"],
        }
        for technology, needles in signatures.items():
            if any(needle in text for needle in needles):
                technologies.add(technology)
        server = headers.get("server", "").lower()
        for technology in ("nginx", "apache", "cloudflare"):
            if technology in server:
                technologies.add(technology)
        return {
            "requested_url": url,
            "final_url": str(response.url),
            "status_code": response.status_code,
            "technologies": sorted(technologies),
            "server": headers.get("server"),
            "powered_by": headers.get("x-powered-by"),
        }

    def careers(self, url: str) -> dict[str, Any]:
        response = self._fetch(url)
        html = response.text[:2_000_000]
        text = re.sub(r"<[^>]+>", " ", html).lower()
        role_terms = (
            "engineer",
            "developer",
            "software",
            "data scientist",
            "data analyst",
            "product manager",
            "cyber",
            "cloud",
            "devops",
            "machine learning",
            "artificial intelligence",
            "automation",
        )
        generic_terms = ("vacancy", "vacancies", "job", "jobs", "role", "roles", "position")
        technology_job_count = sum(text.count(term) for term in role_terms)
        generic_mentions = sum(text.count(term) for term in generic_terms)
        estimated_jobs = min(250, max(technology_job_count, generic_mentions // 3))
        return {
            "requested_url": url,
            "final_url": str(response.url),
            "job_count": estimated_jobs,
            "technology_job_count": technology_job_count,
            "method": "public-careers-page-text-signals",
        }


def enrich_technology(company_id: str, url: str) -> dict:
    if get_company(company_id) is None:
        raise KeyError(company_id)
    profile = TechnologyProfiler().profile(url)
    row = EvidenceRow(
        id=_evidence_id("tech", company_id, profile),
        company_id=company_id,
        source_id="website-technology",
        fact_type="technology_profile",
        observed_at=_now(),
        source_url=profile["final_url"],
        value=profile,
        confidence=0.8,
        raw_reference=str(uuid4()),
    )
    _save_and_rescore(company_id, [row])
    return profile


def enrich_jobs(company_id: str, careers_url: str) -> dict:
    if get_company(company_id) is None:
        raise KeyError(company_id)
    profile = TechnologyProfiler().careers(careers_url)
    row = EvidenceRow(
        id=f"job:{company_id}:{_now().isoformat()}",
        company_id=company_id,
        source_id="public-careers-page",
        fact_type="job_scan",
        observed_at=_now(),
        source_url=profile["final_url"],
        value=profile,
        confidence=0.65,
        raw_reference=str(uuid4()),
    )
    _save_and_rescore(company_id, [row])
    return profile
