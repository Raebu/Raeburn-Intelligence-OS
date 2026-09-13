from __future__ import annotations

from fastapi import FastAPI, HTTPException

from . import __version__
from .models import Opportunity, OpportunityScoreRequest, SourceRecord
from .scoring import score_all, score_opportunity
from .sources import get_source, get_sources

app = FastAPI(
    title="Raeburn Intelligence OS",
    version=__version__,
    description="Evidence-backed public intelligence and opportunity scoring.",
)


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
