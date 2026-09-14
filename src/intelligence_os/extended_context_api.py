from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from .extended_context import EXTENDED_CONTEXT_CAPABILITIES, RDAPClient, SECClient, UNComtradeClient
from .extended_sources import extended_source, extended_sources
from .uk import ExternalServiceError

router = APIRouter(prefix="/v1/extended", tags=["extended-intelligence"])


@router.get("/sources")
def sources() -> list[dict]:
    return [asdict(source) for source in extended_sources()]


@router.get("/sources/{source_id}")
def source(source_id: str) -> dict:
    item = extended_source(source_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Extended source not found")
    result = asdict(item)
    result["capability"] = EXTENDED_CONTEXT_CAPABILITIES.get(source_id)
    return result


@router.get("/sec/{cik}")
def sec_submissions(cik: str) -> dict:
    try:
        return SECClient().submissions(cik)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/trade/un-comtrade")
def un_comtrade(period: str, reporter: str, partner: str = "0", commodity: str = "TOTAL", max_records: int = Query(default=100, ge=1, le=500)) -> dict:
    try:
        return UNComtradeClient().trade(period=period, reporter=reporter, partner=partner, commodity=commodity, max_records=max_records)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/domain/rdap/{domain}")
def rdap_domain(domain: str) -> dict:
    try:
        return RDAPClient().domain(domain)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
