from __future__ import annotations

from typing import Any

import httpx

from .config import get_settings
from .uk import ExternalServiceError


class NomisClient:
    """Small wrapper around the official Nomis REST API.

    Nomis permits anonymous use with a 25,000-cell limit. A uid can be supplied
    through RIOS_NOMIS_UID for larger server-side requests.
    """

    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self.base_url = settings.nomis_base_url.rstrip("/")
        self.uid = settings.nomis_uid
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        request_params = dict(params or {})
        if self.uid:
            request_params["uid"] = self.uid
        response = self.client.get(f"{self.base_url}/{path.lstrip('/')}", params=request_params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"Nomis returned {response.status_code}") from exc
        return response.json()

    def datasets(self) -> Any:
        return self._get("dataset/def.sdmx.json")

    def dataset_definition(self, dataset: str) -> Any:
        return self._get(f"dataset/{dataset}.def.sdmx.json")

    def query(self, dataset: str, params: dict[str, Any]) -> Any:
        return self._get(f"dataset/{dataset}.data.json", params=params)
