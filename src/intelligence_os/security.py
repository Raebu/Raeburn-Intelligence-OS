from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from .config import get_settings


def require_operator_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    configured = settings.api_key
    if not configured:
        if settings.environment.lower() == "production":
            raise HTTPException(
                status_code=503,
                detail="Production write actions require RIOS_API_KEY to be configured",
            )
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, configured):
        raise HTTPException(status_code=401, detail="Invalid or missing operator API key")
