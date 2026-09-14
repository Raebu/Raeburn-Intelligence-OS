from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from .uk import ExternalServiceError

USER_AGENT = "Raeburn-Intelligence-OS/0.6 (+https://github.com/Raebu/Raeburn-Intelligence-OS)"


def _get_json(url: str, *, params: dict[str, Any] | None = None, timeout: float = 20.0) -> Any:
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ExternalServiceError(str(exc)) from exc


class GDELTClient:
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"

    def search(self, query: str, *, max_records: int = 20) -> dict[str, Any]:
        max_records = max(1, min(max_records, 250))
        payload = _get_json(
            self.base_url,
            params={
                "query": query,
                "mode": "ArtList",
                "format": "json",
                "maxrecords": max_records,
                "sort": "HybridRel",
            },
        )
        return payload if isinstance(payload, dict) else {"articles": []}


class WorldBankClient:
    base_url = "https://api.worldbank.org/v2"

    def indicator(self, country: str, indicator: str, *, per_page: int = 20) -> dict[str, Any]:
        payload = _get_json(
            f"{self.base_url}/country/{quote(country)}/indicator/{quote(indicator)}",
            params={"format": "json", "per_page": max(1, min(per_page, 100))},
        )
        if not isinstance(payload, list) or len(payload) < 2:
            return {"metadata": {}, "observations": []}
        return {
            "metadata": payload[0] if isinstance(payload[0], dict) else {},
            "observations": payload[1] if isinstance(payload[1], list) else [],
        }


class WikidataClient:
    base_url = "https://www.wikidata.org/w/api.php"

    def search(self, query: str, *, limit: int = 10, language: str = "en") -> list[dict[str, Any]]:
        payload = _get_json(
            self.base_url,
            params={
                "action": "wbsearchentities",
                "search": query,
                "language": language,
                "uselang": language,
                "format": "json",
                "limit": max(1, min(limit, 50)),
            },
        )
        rows = payload.get("search", []) if isinstance(payload, dict) else []
        return [row for row in rows if isinstance(row, dict)]


class CommonCrawlClient:
    index_url = "https://index.commoncrawl.org/collinfo.json"

    def latest_index(self) -> dict[str, Any] | None:
        payload = _get_json(self.index_url)
        if not isinstance(payload, list):
            return None
        rows = [row for row in payload if isinstance(row, dict) and row.get("cdx-api")]
        return rows[0] if rows else None

    def domain_records(self, domain: str, *, limit: int = 25) -> list[dict[str, Any]]:
        index = self.latest_index()
        if not index:
            return []
        api_url = str(index["cdx-api"])
        payload = _get_json(
            api_url,
            params={
                "url": f"{domain}/*",
                "output": "json",
                "filter": "status:200",
                "collapse": "urlkey",
                "pageSize": max(1, min(limit, 100)),
            },
        )
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)][:limit]
        return []


class OpenStreetMapClient:
    nominatim_url = "https://nominatim.openstreetmap.org/search"

    def geocode(self, query: str, *, limit: int = 5, country_codes: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": max(1, min(limit, 10)),
        }
        if country_codes:
            params["countrycodes"] = country_codes
        payload = _get_json(self.nominatim_url, params=params)
        return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


PUBLIC_CONTEXT_CAPABILITIES = [
    {
        "source_id": "gdelt",
        "purpose": "organisation news/event discovery and external change signals",
        "automation": "on_demand",
    },
    {
        "source_id": "world-bank",
        "purpose": "country-level macroeconomic and market-entry context",
        "automation": "on_demand",
    },
    {
        "source_id": "wikidata",
        "purpose": "entity aliases, organisations, people and relationship hints",
        "automation": "on_demand",
    },
    {
        "source_id": "common-crawl",
        "purpose": "domain history and public web-presence evidence",
        "automation": "on_demand",
    },
    {
        "source_id": "openstreetmap",
        "purpose": "address and location intelligence",
        "automation": "on_demand_rate_limited",
    },
    {
        "source_id": "eurostat",
        "purpose": "EU sector, labour and regional market benchmarking",
        "automation": "registered_for_dataset_specific_ingestion",
    },
    {
        "source_id": "oecd",
        "purpose": "international productivity, trade and market benchmarking",
        "automation": "registered_for_dataset_specific_ingestion",
    },
    {
        "source_id": "openaddresses",
        "purpose": "address normalisation and geographic entity resolution",
        "automation": "registered_for_source_specific_ingestion",
    },
]
