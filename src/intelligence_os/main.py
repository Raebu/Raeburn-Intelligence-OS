from __future__ import annotations

import csv
import io

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from . import __version__
from .db import init_db
from .models import Opportunity, OpportunityScoreRequest, SourceRecord
from .scoring import score_all, score_opportunity
from .service import (
    company_index,
    digital_twin,
    discover_and_refresh,
    discover_companies,
    opportunity_feed,
    refresh_company,
    resolve_company_number,
    system_status,
)
from .sources import get_source, get_sources
from .ui import DASHBOARD_HTML
from .uk import ExternalServiceError

app = FastAPI(
    title="Raeburn Intelligence OS",
    version=__version__,
    description=(
        "Evidence-backed public intelligence, company digital twins and opportunity scoring."
    ),
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/v1/status")
def status() -> dict:
    return system_status()


@app.get("/v1/sources", response_model=list[SourceRecord])
def list_sources() -> list[SourceRecord]:
    return get_sources()


@app.get("/v1/sources/{source_id}", response_model=SourceRecord)
def read_source(source_id: str) -> SourceRecord:
    source = get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@app.get("/v1/companies")
def companies(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict]:
    return company_index(limit=limit)


@app.get("/v1/discovery/companies")
def discovery_search(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    try:
        return discover_companies(q, limit=limit)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/discovery/refresh")
def discovery_refresh(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    try:
        return discover_and_refresh(q, limit=limit)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/opportunities/score", response_model=Opportunity)
def score(request: OpportunityScoreRequest) -> Opportunity:
    return score_opportunity(request)


@app.post("/v1/opportunities/score-all", response_model=list[Opportunity])
def score_every_kind(request: OpportunityScoreRequest) -> list[Opportunity]:
    return score_all(request)


@app.post("/v1/companies/{company_number}/refresh")
def refresh(company_number: str) -> dict:
    try:
        company = refresh_company(company_number)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return company.model_dump()


@app.get("/v1/companies/by-number/{company_number}")
def company_by_number(company_number: str) -> dict:
    company = resolve_company_number(company_number.upper())
    if company is None:
        detail = "Company not found in local intelligence store"
        raise HTTPException(status_code=404, detail=detail)
    return company.model_dump()


@app.get("/v1/companies/{company_id}/twin")
def read_digital_twin(company_id: str) -> dict:
    try:
        return digital_twin(company_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc


@app.get("/v1/opportunities")
def read_opportunity_feed(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict]:
    return opportunity_feed(limit=limit)


@app.get("/v1/opportunities.csv")
def export_opportunities(limit: int = Query(default=1000, ge=1, le=10000)) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["score", "confidence", "type", "company", "company_number", "recommended_action"]
    )
    for row in opportunity_feed(limit=limit):
        company = row["company"]
        opportunity = row["opportunity"]
        writer.writerow(
            [
                opportunity["score"],
                opportunity["confidence"],
                opportunity["kind"],
                company["name"],
                company["company_number"],
                opportunity["recommended_action"],
            ]
        )
    body = output.getvalue()
    headers = {"Content-Disposition": "attachment; filename=raeburn-opportunities.csv"}
    return StreamingResponse(iter([body]), media_type="text/csv", headers=headers)
