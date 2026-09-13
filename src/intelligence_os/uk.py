from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import get_settings
from .db import CompanyRow, EvidenceRow


class ExternalServiceError(RuntimeError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CompaniesHouseClient:
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.companies_house_api_key
        self.base_url = settings.companies_house_base_url.rstrip("/")
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
        )

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ExternalServiceError(
                "Companies House access requires RIOS_COMPANIES_HOUSE_API_KEY"
            )
        token = base64.b64encode(f"{self.api_key}:".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.client.get(
            f"{self.base_url}{path}",
            params=params,
            headers=self._headers(),
        )
        if response.status_code == 404:
            raise KeyError(path)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"Companies House returned {response.status_code}") from exc
        data = response.json()
        return data if isinstance(data, dict) else {"items": data}

    def company_profile(self, company_number: str) -> dict[str, Any]:
        number = company_number.strip().upper()
        return self._get(f"/company/{number}")

    def officers(self, company_number: str, items_per_page: int = 100) -> dict[str, Any]:
        number = company_number.strip().upper()
        return self._get(
            f"/company/{number}/officers",
            params={"items_per_page": min(max(items_per_page, 1), 100)},
        )

    def filing_history(self, company_number: str, items_per_page: int = 100) -> dict[str, Any]:
        number = company_number.strip().upper()
        return self._get(
            f"/company/{number}/filing-history",
            params={"items_per_page": min(max(items_per_page, 1), 100)},
        )

    def insolvency(self, company_number: str) -> dict[str, Any]:
        number = company_number.strip().upper()
        return self._get(f"/company/{number}/insolvency")

    def charges(self, company_number: str, items_per_page: int = 100) -> dict[str, Any]:
        number = company_number.strip().upper()
        return self._get(
            f"/company/{number}/charges",
            params={"items_per_page": min(max(items_per_page, 1), 100)},
        )

    def search(self, query: str, items_per_page: int = 20) -> list[dict[str, Any]]:
        response = self._get(
            "/search/companies",
            params={"q": query, "items_per_page": min(max(items_per_page, 1), 100)},
        )
        return list(response.get("items", []))

    def normalize(self, payload: dict[str, Any]) -> tuple[CompanyRow, list[EvidenceRow]]:
        number = str(payload["company_number"]).upper()
        observed = _utcnow()
        incorporated = payload.get("date_of_creation")
        company = CompanyRow(
            id=f"gb:companies-house:{number}",
            name=payload.get("company_name", number),
            company_number=number,
            status=payload.get("company_status"),
            company_type=payload.get("type"),
            sic_codes=payload.get("sic_codes") or [],
            registered_address=payload.get("registered_office_address") or {},
            incorporated_at=(
                datetime.fromisoformat(incorporated).replace(tzinfo=UTC)
                if incorporated
                else None
            ),
            updated_at=observed,
        )
        evidence = [
            EvidenceRow(
                id=f"ch:{number}:profile:{observed.isoformat()}",
                company_id=company.id,
                source_id="companies-house",
                fact_type="company_profile",
                observed_at=observed,
                source_url=f"{self.base_url}/company/{number}",
                value=payload,
                confidence=1.0,
                raw_reference=number,
            )
        ]
        return company, evidence


class ContractsFinderClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self.base_url = settings.contracts_finder_base_url
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
        )

    def search(
        self,
        *,
        published_from: str | None = None,
        published_to: str | None = None,
        stages: list[str] | None = None,
        size: int = 100,
        page: int = 1,
    ) -> dict[str, Any]:
        criteria: dict[str, Any] = {}
        if published_from:
            criteria["publishedFrom"] = published_from
        if published_to:
            criteria["publishedTo"] = published_to
        if stages:
            criteria["stages"] = stages
        payload = {
            "searchCriteria": criteria,
            "orderBy": "publishedDate",
            "order": "DESC",
            "size": min(max(size, 1), 100),
            "page": max(page, 1),
        }
        response = self.client.post(self.base_url, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"Contracts Finder returned {response.status_code}") from exc
        data = response.json()
        return data if isinstance(data, dict) else {"releases": data}


class FindATenderClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self.base_url = settings.find_a_tender_base_url.rstrip("/")
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
        )

    def releases(
        self,
        *,
        updated_from: str | None = None,
        updated_to: str | None = None,
        stages: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": min(max(limit, 1), 100)}
        if updated_from:
            params["updatedFrom"] = updated_from
        if updated_to:
            params["updatedTo"] = updated_to
        if stages:
            params["stages"] = stages
        if cursor:
            params["cursor"] = cursor
        response = self.client.get(self.base_url, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"Find a Tender returned {response.status_code}") from exc
        data = response.json()
        return data if isinstance(data, dict) else {"releases": data}
