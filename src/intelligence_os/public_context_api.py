from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .public_context import (
    PUBLIC_CONTEXT_CAPABILITIES,
    CommonCrawlClient,
    GDELTClient,
    OpenStreetMapClient,
    WikidataClient,
    WorldBankClient,
)
from .uk import ExternalServiceError

router = APIRouter(prefix="/v1/context", tags=["public-context"])


@router.get("/capabilities")
def capabilities() -> list[dict]:
    return PUBLIC_CONTEXT_CAPABILITIES


@router.get("/gdelt")
def gdelt_search(
    q: str = Query(min_length=2, max_length=300),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    try:
        return GDELTClient().search(q, max_records=limit)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/world-bank/{country}/{indicator}")
def world_bank_indicator(
    country: str,
    indicator: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    try:
        return WorldBankClient().indicator(country, indicator, per_page=limit)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/wikidata")
def wikidata_search(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict]:
    try:
        return WikidataClient().search(q, limit=limit)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/common-crawl")
def common_crawl_domain(
    domain: str = Query(min_length=3, max_length=253),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[dict]:
    try:
        return CommonCrawlClient().domain_records(domain, limit=limit)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/openstreetmap")
def osm_geocode(
    q: str = Query(min_length=3, max_length=300),
    limit: int = Query(default=5, ge=1, le=10),
    country_codes: str | None = Query(default=None, max_length=50),
) -> list[dict]:
    try:
        return OpenStreetMapClient().geocode(q, limit=limit, country_codes=country_codes)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
