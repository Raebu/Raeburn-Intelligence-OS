from __future__ import annotations

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


def enrich_companies_house(company_id: str, *, officers_limit: int = 100, filings_limit: int = 100) -> dict:
    company = get_company(company_id)
    if company is None or not company.company_number:
        raise KeyError(company_id)
    client = CompaniesHouseClient()
    officers = client.officers(company.company_number, items_per_page=officers_limit)
    filings = client.filing_history(company.company_number, items_per_page=filings_limit)
    observed = _now()
    rows = [
        EvidenceRow(
            id=_evidence_id("ch-officers", company_id, officers),
            company_id=company_id,
            source_id="companies-house",
            fact_type="officers",
            observed_at=observed,
            source_url=f"{client.base_url}/company/{company.company_number}/officers",
            value=officers,
            confidence=1.0,
            raw_reference=company.company_number,
        ),
        EvidenceRow(
            id=_evidence_id("ch-filings", company_id, filings),
            company_id=company_id,
            source_id="companies-house",
            fact_type="filing_history",
            observed_at=observed,
            source_url=f"{client.base_url}/company/{company.company_number}/filing-history",
            value=filings,
            confidence=1.0,
            raw_reference=company.company_number,
        ),
    ]
    save_evidence(rows)
    replace_signals(company_id, derive_signals(company_id, list_evidence(company_id)))
    return {
        "company_id": company_id,
        "officers": len(officers.get("items", [])),
        "filings": len(filings.get("items", [])),
    }


class TechnologyProfiler:
    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )

    def profile(self, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("A valid http(s) URL is required")
        response = self.client.get(url)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"Website returned {response.status_code}") from exc
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
    save_evidence([row])
    replace_signals(company_id, derive_signals(company_id, list_evidence(company_id)))
    return profile
