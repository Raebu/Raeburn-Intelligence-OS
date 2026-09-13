# Raeburn Intelligence OS

**Evidence-backed public intelligence for companies, markets and opportunities.**

Raeburn Intelligence OS converts fragmented public datasets into normalized entities, explainable signals, opportunity scores and actionable recommendations. The first vertical is **UK Company Opportunity Intelligence**, designed to feed Raeburn Consulting, automation, recruitment, outreach and future DiscoveryOS workflows.

## What it does

```text
Public datasets / APIs
        ↓
Source registry + licensing/provenance
        ↓
Ingestion connectors
        ↓
Normalized observations
        ↓
Company / entity resolution
        ↓
Signal detection
        ↓
Explainable opportunity scoring
        ↓
API + downstream Raeburn products
```

The product is intentionally not a generic “search public datasets” tool. Users should see answers such as:

> **Automation opportunity — 87/100**
> Hiring activity, contract growth and operational signals suggest near-term process-automation demand. Evidence: source A, source B, source C.

## Initial capabilities

- Source registry with jurisdiction, licence, refresh cadence and commercial-use metadata
- Connector interface for APIs, CSV/JSON downloads and future streaming sources
- Normalized company, observation, signal and opportunity models
- Deterministic, inspectable opportunity scoring
- Evidence/provenance attached to every signal and opportunity
- FastAPI endpoints for sources, companies, signals and opportunity ranking
- UK-company-first taxonomy
- Seed public-source catalogue
- Tests and CI

## API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn intelligence_os.main:app --reload
```

Then open `http://127.0.0.1:8000/docs`.

### Example

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/sources
curl -X POST http://127.0.0.1:8000/v1/opportunities/score \
  -H 'content-type: application/json' \
  -d '{
    "company_id":"demo-001",
    "signals":[
      {"kind":"hiring_growth","strength":0.8,"confidence":0.9},
      {"kind":"public_contract_win","strength":0.7,"confidence":0.95},
      {"kind":"automation_gap","strength":0.9,"confidence":0.7}
    ]
  }'
```

## Opportunity taxonomy

Current opportunity families:

- `automation`
- `consulting`
- `recruitment`
- `software`
- `procurement`
- `ma`
- `market_entry`

The scoring engine is deliberately transparent. LLM reasoning can enrich an opportunity explanation later, but it must not replace source evidence or deterministic scoring.

## Source principles

Every source must record:

1. provenance and canonical URL;
2. licence / terms status;
3. whether commercial reuse is known to be allowed;
4. jurisdiction and refresh cadence;
5. collection method;
6. entity types and signal types it can support.

The [Awesome Public Datasets](https://github.com/awesomedata/awesome-public-datasets) project is treated as a **discovery catalogue**, not as blanket permission to redistribute each linked dataset.

## Roadmap

### Phase 1 — UK Company Opportunity Intelligence
Companies House, contracts/procurement, labour/hiring, economic/geographic and technology signals.

### Phase 2 — Company Digital Twin
Historical company timeline, people, locations, technologies, contracts, jobs, financial indicators and competitors.

### Phase 3 — Autonomous Opportunity Radar
Scheduled change detection and ranked daily opportunities with actions such as research, CRM hand-off and outreach preparation.

### Phase 4 — Shared Raeburn intelligence layer
Expose stable APIs/events to DiscoveryOS, RaeburnEmailer, ViraLink, RaeburnAI Executive and other group products.

## Engineering rules

- Evidence before inference.
- No unsupported claims.
- Keep raw source facts separate from derived signals.
- Every derived output must be traceable to evidence.
- Do not ingest or redistribute data whose licence/terms have not been assessed.
- Store timestamps so historical change can become proprietary intelligence.

## Status

Foundation build in progress. The repository starts with a runnable API and scoring engine, then adds real connectors incrementally.
