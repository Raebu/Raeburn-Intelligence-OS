from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .procurement import (
    attach_awards_to_indexed_companies,
    contracts_finder_feed,
    find_a_tender_feed,
)
from .uk import ExternalServiceError

router = APIRouter(prefix="/v1/procurement", tags=["procurement"])


@router.get("/find-a-tender/normalized")
def normalized_find_a_tender(
    updated_from: str | None = None,
    updated_to: str | None = None,
    stages: str | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    cursor: str | None = None,
) -> list[dict]:
    try:
        return find_a_tender_feed(
            updated_from=updated_from,
            updated_to=updated_to,
            stages=stages,
            limit=limit,
            cursor=cursor,
        )
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/contracts-finder/normalized")
def normalized_contracts_finder(
    published_from: str | None = None,
    published_to: str | None = None,
    stage: list[str] | None = None,
    size: int = Query(default=100, ge=1, le=100),
    page: int = Query(default=1, ge=1),
) -> list[dict]:
    try:
        return contracts_finder_feed(
            published_from=published_from,
            published_to=published_to,
            stages=stage,
            size=size,
            page=page,
        )
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/find-a-tender/link-awards")
def link_find_a_tender_awards(
    updated_from: str | None = None,
    updated_to: str | None = None,
    limit: int = Query(default=100, ge=1, le=100),
) -> dict[str, int]:
    try:
        records = find_a_tender_feed(
            updated_from=updated_from,
            updated_to=updated_to,
            stages="award",
            limit=limit,
        )
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return attach_awards_to_indexed_companies(records)


@router.post("/contracts-finder/link-awards")
def link_contracts_finder_awards(
    published_from: str | None = None,
    published_to: str | None = None,
    size: int = Query(default=100, ge=1, le=100),
    page: int = Query(default=1, ge=1),
) -> dict[str, int]:
    try:
        records = contracts_finder_feed(
            published_from=published_from,
            published_to=published_to,
            stages=["award"],
            size=size,
            page=page,
        )
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return attach_awards_to_indexed_companies(records)
