from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from . import __version__
from .db import init_db
from .models import Opportunity, OpportunityScoreRequest, SourceRecord
from .scoring import score_all, score_opportunity
from .service import digital_twin, opportunity_feed, refresh_company, resolve_company_number
from .sources import get_source, get_sources
from .uk import ExternalServiceError

app = FastAPI(
    title="Raeburn Intelligence OS",
    version=__version__,
    description="Evidence-backed public intelligence, company digital twins and opportunity scoring.",
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/v1/sources", response_model=list[SourceRecord])
def list_sources() -> list[SourceRecord]:
    return get_sources()


@app.get("/v1/sources/{source_id}", response_model=SourceRecord)
def read_source(source_id: str) -> SourceRecord:
    source = get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


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
