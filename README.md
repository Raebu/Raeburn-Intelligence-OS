# Raeburn Intelligence OS

**Evidence-backed public intelligence for companies, markets and commercial opportunities.**

Raeburn Intelligence OS converts fragmented public information into normalized entities, source evidence, explainable signals, ranked opportunities and recommended actions. Its first production vertical is **UK Company Opportunity Intelligence** for consulting, automation, recruitment, software, procurement, M&A and market-entry workflows.

## Version 0.4.0

Version 0.4 expands the Company Digital Twin beyond the original company-profile layer:

- Companies House company search, profile refresh and normalization;
- Companies House officers and director-change intelligence;
- filing-history monitoring and distress indicators;
- charges and insolvency evidence for public financial-risk intelligence;
- Contracts Finder OCDS connector;
- Nomis labour-market API client, anonymous by default;
- public website technology profiling;
- public careers-page scanning and historical hiring-change detection;
- technology-hiring, hiring-growth, director-change, market-growth, distress, digital-transformation and automation-gap signals;
- responsive operator dashboard at `/`;
- FastAPI service and OpenAPI documentation at `/docs`;
- SQLite persistence by default and PostgreSQL support for production;
- immutable timestamped evidence records;
- deterministic multi-product opportunity scoring;
- Company Digital Twin endpoint;
- ranked Opportunity Radar feed and CSV export;
- Docker support and automated Ruff/pytest CI.

## Architecture

```text
Companies House / Contracts Finder / Nomis / public company web pages
        ↓
Source registry + licence/provenance controls
        ↓
Connectors / discovery / enrichment
        ↓
Normalized company entities
        ↓
Timestamped source evidence
        ↓
Evidence-derived signals
        ↓
Explainable opportunity scoring
        ↓
Company Digital Twin + Opportunity Radar
        ↓
Dashboard / API / CSV / downstream Raeburn systems
```

The system deliberately separates **facts**, **signals** and **commercial recommendations**. A score is never treated as a source fact, and every derived signal retains evidence IDs.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn intelligence_os.main:app --reload
```

Open the dashboard at `http://127.0.0.1:8000/` or the interactive API at `http://127.0.0.1:8000/docs`.

### Companies House live data

Set a Companies House API key:

```text
RIOS_COMPANIES_HOUSE_API_KEY=your-key
```

Without the key, the service still starts and local intelligence remains accessible. Live Companies House endpoints explicitly report the missing credential rather than fabricating data.

### Nomis

Nomis supports anonymous API use with its guest limits. For larger server-side requests you can optionally set:

```text
RIOS_NOMIS_UID=your-uid
```

## Core endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/status` | Store and integration readiness |
| `GET /v1/sources` | Registered intelligence sources |
| `GET /v1/companies` | Indexed company entities |
| `GET /v1/discovery/companies?q=...` | Search Companies House |
| `POST /v1/discovery/refresh?q=...` | Search and bulk-index matching companies |
| `POST /v1/companies/{number}/refresh` | Refresh one company profile |
| `POST /v1/companies/{id}/enrich/companies-house` | Add officers, filings, charges and insolvency evidence |
| `POST /v1/companies/{id}/enrich/technology?url=...` | Profile public website technology |
| `POST /v1/companies/{id}/enrich/jobs?careers_url=...` | Observe public hiring activity |
| `GET /v1/market/nomis/datasets` | Browse Nomis datasets |
| `GET /v1/market/nomis/{dataset}/definition` | Inspect a Nomis dataset definition |
| `GET /v1/companies/{id}/twin` | Full Company Digital Twin |
| `GET /v1/opportunities` | Ranked Opportunity Radar |
| `GET /v1/opportunities.csv` | Export opportunity feed |

## Opportunity families

`automation`, `consulting`, `recruitment`, `software`, `procurement`, `ma`, and `market_entry`.

## Evidence and signals

Raw source observations are stored separately from interpretations. Current derived signals include public-contract activity, public-contract wins, distress, director change, digital transformation, automation gap, technology hiring, hiring growth and market growth.

Hiring growth is only emitted when repeated careers-page observations show an increase. Website technology observations use only public HTML and response headers and do not bypass authentication, robots/access controls or private systems.

Public financial intelligence is intentionally limited to defensible public records such as charges, insolvency information and filing-derived distress indicators. The system does not invent revenue, profit or private financial data.

## Persistence

Development defaults to `sqlite:///./raeburn_intelligence.db`. Production can use PostgreSQL through `RIOS_DATABASE_URL`.

Historical evidence is retained so repeated observations become change signals and proprietary time-series intelligence.

## Source governance

Every registered source records its canonical URL, jurisdiction, licence status, refresh cadence, collection method, supported entity types and signals. The Awesome Public Datasets repository remains a discovery catalogue only; each linked dataset requires its own terms/licensing assessment before commercial ingestion or redistribution.

Engineering rules remain: evidence before inference, no unsupported claims, raw facts separate from derived signals, traceable evidence IDs, no assumed commercial rights, retained history, and explicit credential failures.

## Development checks

```bash
ruff check .
pytest -q
```

GitHub Actions runs the same checks on every push to `main` and on pull requests.
