# Raeburn Intelligence OS

**Evidence-backed public intelligence for companies, markets and commercial opportunities.**

Raeburn Intelligence OS converts fragmented public information into normalized entities, source evidence, explainable signals, ranked opportunities, relationship graphs and approval-gated commercial actions. Its first production vertical is **UK Company Opportunity Intelligence** for consulting, automation, recruitment, software, procurement, M&A and market-entry workflows.

## Version 0.6.0

Version 0.6 turns the v0.5 radar into a compounding intelligence layer:

- historical Company Digital Twin snapshots and field-level change detection;
- persistent company/person/buyer/technology/SIC/ownership relationship graph;
- Companies House officers and role-family decision-maker inference;
- Companies House Persons with Significant Control enrichment;
- Companies House Document API/iXBRL account-fact extraction for turnover, cash, net assets, liabilities and employee counts when those facts are present;
- financial trend calculation from repeated public account observations;
- tender fit scoring with service, value, buyer, lifecycle and deadline evidence;
- sector-peer anomaly detection over observed signals;
- persistent company watchlists and evidence-linked alerts;
- evidence-grounded analyst answers that refuse unsupported conclusions;
- approval-gated commercial action proposals rather than autonomous external side effects;
- recorded commercial outcomes and outcome-based score calibration;
- scheduled radar cycles that refresh, enrich, rebuild graphs, capture snapshots, evaluate watchlists and prepare high-confidence actions;
- production operator-key protection for mutating API actions.

The v0.5 capabilities remain: Companies House profile/officer/filing/charge/insolvency intelligence, website technology profiling, public careers-page hiring observations, Nomis labour-market access, Contracts Finder and Find a Tender OCDS feeds, procurement award matching, opportunity scoring, dashboard, CSV export, PostgreSQL support, Docker and CI.

## Architecture

```text
Companies House + Document API / Find a Tender / Contracts Finder / Nomis / public web
        ↓
Source registry + licence/provenance controls
        ↓
Discovery / enrichment / scheduled radar
        ↓
Companies + people + owners + buyers + technology + procurement entities
        ↓
Immutable timestamped evidence + historical snapshots
        ↓
Knowledge graph + change detection + peer comparison
        ↓
Evidence-derived signals
        ↓
Base opportunity scoring + outcome calibration
        ↓
Company Digital Twin + Opportunity Radar + grounded analyst
        ↓
Watchlists / alerts / approval-gated action proposals
        ↓
Downstream Raeburn systems
```

Facts, interpretations and commercial actions remain deliberately separate. Every derived signal retains evidence IDs, analyst answers are restricted to stored evidence, and outcome learning adjusts ranking without overwriting the original deterministic score.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn intelligence_os.main:app --reload
```

Open `http://127.0.0.1:8000/` for the operator dashboard or `/docs` for the interactive API.

## Configuration

### Companies House

```text
RIOS_COMPANIES_HOUSE_API_KEY=your-key
RIOS_COMPANIES_HOUSE_BASE_URL=https://api.company-information.service.gov.uk
RIOS_COMPANIES_HOUSE_DOCUMENT_BASE_URL=https://document-api.company-information.service.gov.uk
```

Without the API key the service still starts and stored intelligence remains accessible. Live Companies House and document endpoints fail explicitly rather than fabricating values.

### Production operator authentication

Read-only endpoints can remain public. Mutating HTTP actions are protected when an operator key is configured:

```text
RIOS_API_KEY=generate-a-long-random-secret
```

Send it as `X-API-Key`. Development remains open when no key is set. In `production`, write actions fail closed when the key is missing.

### Persistent scheduled radar

The scheduled GitHub Action runs every six hours. Persistent operation requires a PostgreSQL-compatible database configured as a repository/runtime secret:

```text
RIOS_DATABASE_URL=postgresql+psycopg://...
```

The scheduled workflow exits cleanly when no persistent database URL exists instead of creating disposable intelligence in a temporary SQLite database.

## Core API surface

### Company intelligence

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/companies` | Indexed companies |
| `GET /v1/discovery/companies?q=...` | Companies House discovery |
| `POST /v1/discovery/refresh?q=...` | Bulk discovery/indexing |
| `POST /v1/companies/{number}/refresh` | Refresh company profile |
| `POST /v1/companies/{id}/enrich/companies-house` | Officers, filings, charges, insolvency |
| `POST /v1/companies/{id}/ownership/enrich` | Persons with Significant Control |
| `POST /v1/companies/{id}/accounts/enrich` | Extract public iXBRL account facts |
| `POST /v1/companies/{id}/enrich/technology?url=...` | Public website technology profile |
| `POST /v1/companies/{id}/enrich/jobs?careers_url=...` | Public hiring observation |
| `GET /v1/companies/{id}/twin` | Company Digital Twin |
| `POST /v1/companies/{id}/snapshots` | Capture historical Twin snapshot |
| `GET /v1/companies/{id}/changes` | Compare two most recent snapshots |
| `GET /v1/companies/{id}/financial-trends` | Public financial trend calculations |
| `GET /v1/companies/{id}/anomalies` | Peer-relative signal anomalies |

### People and knowledge graph

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/companies/{id}/people/rebuild` | Infer evidence-backed people/role records |
| `GET /v1/companies/{id}/people` | Company people index |
| `POST /v1/companies/{id}/graph/rebuild` | Rebuild company graph including PSC/buyers/technology |
| `GET /v1/graph/{entity_type}/{entity_id}` | Inspect graph relationships |

### Procurement

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/procurement/find-a-tender` | Raw Find a Tender OCDS |
| `GET /v1/procurement/find-a-tender/normalized` | Normalized Find a Tender records |
| `POST /v1/procurement/find-a-tender/link-awards` | Match awards to indexed suppliers |
| `GET /v1/procurement/contracts-finder` | Raw Contracts Finder OCDS |
| `GET /v1/procurement/contracts-finder/normalized` | Normalized Contracts Finder records |
| `POST /v1/procurement/contracts-finder/link-awards` | Match awards to indexed suppliers |
| `POST /v1/procurement/score` | Evidence-based tender fit score |

### Analyst, alerts and actions

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/companies/{id}/analyst` | Ask evidence-grounded company questions |
| `POST /v1/watchlists` | Create signal watchlist |
| `POST /v1/watchlists/evaluate` | Generate alerts from current signals |
| `GET /v1/alerts` | Alert feed |
| `POST /v1/companies/{id}/actions/propose` | Prepare approval-gated commercial actions |
| `POST /v1/actions/{action_id}/approve` | Approve prepared action |
| `GET /v1/actions` | Action queue |
| `POST /v1/outcomes` | Record conversation/proposal/win/loss outcome |
| `GET /v1/feedback` | Commercial feedback summary |
| `GET /v1/feedback/calibration` | Learned opportunity multipliers |
| `GET /v1/companies/{id}/opportunities/calibrated` | Base scores plus outcome calibration |

The action engine deliberately stops at preparation/approval. Sending outreach, writing to CRM systems or submitting bids remains a separately authorized downstream action.

## Opportunity families

`automation`, `consulting`, `recruitment`, `software`, `procurement`, `ma`, and `market_entry`.

## Evidence and source governance

Raw source observations are stored separately from interpretations. Public financial intelligence only uses defensible public records and extracted facts actually present in Companies House documents; missing revenue or profit is never invented.

Website and careers-page intelligence uses public responses only and does not bypass authentication or private systems. The Awesome Public Datasets repository remains a discovery catalogue rather than blanket commercial permission: every downstream dataset requires its own licence and terms assessment.

Engineering rules: evidence before inference, no unsupported claims, raw facts separate from signals, traceable evidence IDs, retained historical snapshots, explicit credentials, and approval before external actions.

## Persistence

Development defaults to `sqlite:///./raeburn_intelligence.db`. Production can use PostgreSQL through `RIOS_DATABASE_URL`. Historical evidence, snapshots, graph records, watchlists, alerts, action proposals and outcomes are persistent tables.

## Development checks

```bash
ruff check .
pytest -q
```

GitHub Actions runs the same checks on every push to `main` and on pull requests.
