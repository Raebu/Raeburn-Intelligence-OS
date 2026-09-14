from __future__ import annotations

import csv
import io

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from . import __version__
from .advanced_api import router as advanced_router
from .db import init_db
from .enrichment import enrich_companies_house, enrich_jobs, enrich_technology
from .extended_context_api import router as extended_context_router
from .market import NomisClient
from .models import Opportunity, OpportunityScoreRequest, SourceRecord
from .procurement_api import router as procurement_router
from .public_context_api import router as public_context_router
from .scoring import score_all, score_opportunity
from .security import validate_operator_key
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
from .uk import ContractsFinderClient, ExternalServiceError, FindATenderClient

app = FastAPI(title="Raeburn Intelligence OS", version=__version__, description="Evidence-backed public intelligence, company digital twins and opportunity scoring.")
app.include_router(procurement_router)
app.include_router(advanced_router)
app.include_router(public_context_router)
app.include_router(extended_context_router)


@app.middleware("http")
async def protect_operator_actions(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        try:
            validate_operator_key(request.headers.get("X-API-Key"))
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


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
def discovery_search(q: str = Query(min_length=2, max_length=200), limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    try:
        return discover_companies(q, limit=limit)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/discovery/refresh")
def discovery_refresh(q: str = Query(min_length=2, max_length=200), limit: int = Query(default=10, ge=1, le=50)) -> dict:
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
        return refresh_company(company_number).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/companies/{company_id}/enrich/companies-house")
def companies_house_enrichment(company_id: str) -> dict:
    try:
        return enrich_companies_house(company_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/companies/{company_id}/enrich/technology")
def technology_enrichment(company_id: str, url: str = Query(min_length=8, max_length=2048)) -> dict:
    try:
        return enrich_technology(company_id, url)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc
    except (ExternalServiceError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/companies/{company_id}/enrich/jobs")
def jobs_enrichment(company_id: str, careers_url: str = Query(min_length=8, max_length=2048)) -> dict:
    try:
        return enrich_jobs(company_id, careers_url)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Company not found") from exc
    except (ExternalServiceError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/market/nomis/datasets")
def nomis_datasets() -> object:
    try:
        return NomisClient().datasets()
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/market/nomis/{dataset}/definition")
def nomis_dataset_definition(dataset: str) -> object:
    try:
        return NomisClient().dataset_definition(dataset)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/procurement/find-a-tender")
def find_a_tender(updated_from: str | None = None, updated_to: str | None = None, stages: str | None = None, limit: int = Query(default=100, ge=1, le=100), cursor: str | None = None) -> dict:
    try:
        return FindATenderClient().releases(updated_from=updated_from, updated_to=updated_to, stages=stages, limit=limit, cursor=cursor)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/procurement/contracts-finder")
def contracts_finder(published_from: str | None = None, published_to: str | None = None, stage: list[str] | None = None, size: int = Query(default=100, ge=1, le=100), page: int = Query(default=1, ge=1)) -> dict:
    try:
        return ContractsFinderClient().search(published_from=published_from, published_to=published_to, stages=stage, size=size, page=page)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/companies/by-number/{company_number}")
def company_by_number(company_number: str) -> dict:
    company = resolve_company_number(company_number.upper())
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found in local intelligence store")
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
    writer.writerow(["score", "confidence", "type", "company", "company_number", "recommended_action"])
    for row in opportunity_feed(limit=limit):
        company = row["company"]
        opportunity = row["opportunity"]
        writer.writerow([opportunity["score"], opportunity["confidence"], opportunity["kind"], company["name"], company["company_number"], opportunity["recommended_action"]])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=raeburn-opportunities.csv"})
