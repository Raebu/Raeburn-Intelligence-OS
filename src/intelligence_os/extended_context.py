from __future__ import annotations

from typing import Any

from .public_context import USER_AGENT, _get_json


class SECClient:
    """SEC EDGAR public submissions adapter. Caller should use CIK padded to ten digits."""

    def submissions(self, cik: str) -> dict[str, Any]:
        cik = "".join(ch for ch in cik if ch.isdigit()).zfill(10)
        payload = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        return payload if isinstance(payload, dict) else {}


class UNComtradeClient:
    """UN Comtrade public API adapter; parameters intentionally explicit and bounded."""

    base_url = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"

    def trade(self, *, period: str, reporter: str, partner: str = "0", commodity: str = "TOTAL", max_records: int = 500) -> dict[str, Any]:
        payload = _get_json(self.base_url, params={"period": period, "reporterCode": reporter, "partnerCode": partner, "cmdCode": commodity, "maxRecords": max(1, min(max_records, 500))})
        return payload if isinstance(payload, dict) else {"data": []}


class UKRIClient:
    base_url = "https://gtr.ukri.org/gtr/api"

    def search_projects(self, term: str, *, page: int = 1, size: int = 20) -> dict[str, Any]:
        # Gateway to Research may negotiate XML on some routes; this method is isolated so
        # production ingestion can add the source-specific parser without contaminating facts.
        payload = _get_json(f"{self.base_url}/projects", params={"q": term, "p": max(1, page), "s": max(1, min(size, 100))})
        return payload if isinstance(payload, dict) else {"projects": []}


class PlanningDataClient:
    base_url = "https://www.planning.data.gov.uk"

    def entities(self, dataset: str, *, limit: int = 50) -> Any:
        return _get_json(f"{self.base_url}/entity.json", params={"dataset": dataset, "limit": max(1, min(limit, 100))})


class RDAPClient:
    def domain(self, domain: str) -> dict[str, Any]:
        payload = _get_json(f"https://rdap.org/domain/{domain.strip().lower()}")
        return payload if isinstance(payload, dict) else {}


class CharityCommissionClient:
    """Registry capability descriptor: production API access may require source credentials."""

    api_url = "https://api.charitycommission.gov.uk/"

    def capability(self) -> dict[str, Any]:
        return {"source": "charity-commission", "api_url": self.api_url, "credential_required": True}


class OpenCorporatesClient:
    """Global entity capability descriptor; API use is gated by current licence/API terms."""

    api_url = "https://api.opencorporates.com/"

    def capability(self) -> dict[str, Any]:
        return {"source": "opencorporates", "api_url": self.api_url, "terms_review_required": True}


EXTENDED_CONTEXT_CAPABILITIES = {
    "un-comtrade": "trade flows and supply-chain/market-entry context",
    "wto-data": "trade and market-access benchmarking",
    "sec-edgar": "US issuer filing and strategic-change intelligence",
    "epo-ops": "European patent activity",
    "wipo-patentscope": "international patent activity",
    "uspto-open-data": "US patent activity",
    "ukri-gtr": "research and innovation grants",
    "innovate-uk": "innovation funding",
    "horizon-europe": "European research and innovation funding",
    "planning-data": "physical development and expansion",
    "national-grid-eso": "energy demand/capacity and infrastructure",
    "fca-enforcement": "financial regulatory enforcement",
    "ico-enforcement": "privacy/data enforcement",
    "cma-cases": "competition and merger intervention",
    "hse-enforcement": "health and safety enforcement",
    "environment-agency": "environmental compliance",
    "gazette": "insolvency/restructuring/court notices",
    "charity-commission": "charity entity universe",
    "uk-public-bodies": "public-sector organisation universe",
    "certificate-transparency": "domain/subdomain change",
    "rdap": "domain registration context",
    "find-a-tender-pipeline": "future procurement intent",
    "contracts-finder-pipeline": "early procurement intent",
    "govuk-news": "official news and announcements",
    "london-stock-exchange-rns": "listed-company announcements",
    "maritime-and-coastguard": "shipping/logistics context",
    "uk-port-freight": "port freight flows",
    "land-registry-ppd": "property transactions",
    "land-registry-uk-companies": "company property ownership",
    "opencorporates": "global entity relationships",
    "firstdata-catalogue": "authoritative-source discovery only",
}

# Keep a stable UA exported for future source-specific clients.
EXTENDED_USER_AGENT = USER_AGENT
