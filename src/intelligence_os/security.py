from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException

from .config import get_settings


def validate_operator_key(value: str | None) -> None:
    settings = get_settings()
    configured = settings.api_key
    if not configured:
        if settings.environment.lower() == "production":
            raise HTTPException(
                status_code=503,
                detail="Production write actions require RIOS_API_KEY to be configured",
            )
        return
    if value is None or not secrets.compare_digest(value, configured):
        raise HTTPException(status_code=401, detail="Invalid or missing operator API key")


def require_operator_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    validate_operator_key(x_api_key)
