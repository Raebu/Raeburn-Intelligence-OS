# Raeburn Intelligence OS

**Evidence-backed public intelligence for companies, markets and commercial opportunities.**

Raeburn Intelligence OS converts fragmented public information into normalized entities, source evidence, explainable signals, ranked opportunities and recommended actions. Its first production vertical is **UK Company Opportunity Intelligence** for consulting, automation, recruitment, software, procurement, M&A and market-entry workflows.

## Version 0.3.0

The repository now contains a complete runnable vertical, not only a scoring prototype:

- responsive operator dashboard at `/`;
- FastAPI service and OpenAPI documentation at `/docs`;
- SQLite persistence by default and PostgreSQL support for production;
- Companies House company search, profile refresh and normalization;
- Contracts Finder public endpoint client;
- source registry with provenance and licensing metadata;
- immutable timestamped evidence records;
- derived distress, digital-transformation and procurement signals;
- deterministic multi-product opportunity scoring;
- Company Digital Twin endpoint;
- ranked Opportunity Radar feed;
- recommended next action for every scored opportunity;
- company discovery and bulk refresh endpoints;
- CSV opportunity export;
- Docker support;
- automated Ruff and pytest CI.

## Architecture

```text
Public sources / APIs
        ↓
Source registry + licence/provenance controls
        ↓
Connectors / discovery
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

Open:

- `http://127.0.0.1:8000/` — operator dashboard
- `http://127.0.0.1:8000/docs` — interactive API
- `http://127.0.0.1:8000/health` — health check

### Companies House live data

Create a Companies House API key and set:

```text
RIOS_COMPANIES_HOUSE_API_KEY=your-key
```

Without the key, the service still starts, the dashboard works, local intelligence remains accessible and integration status explicitly reports `credential_required`. It does not fabricate live Companies House data.

## Core endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/status` | Store and integration readiness |
| `GET /v1/sources` | Registered intelligence sources |
| `GET /v1/companies` | Indexed company entities |
| `GET /v1/discovery/companies?q=...` | Search Companies House |
| `POST /v1/discovery/refresh?q=...` | Search and bulk-index matching companies |
| `POST /v1/companies/{number}/refresh` | Refresh one company from Companies House |
| `GET /v1/companies/{id}/twin` | Full Company Digital Twin |
| `GET /v1/opportunities` | Ranked Opportunity Radar |
| `GET /v1/opportunities.csv` | Download opportunity feed |
| `POST /v1/opportunities/score` | Score a supplied signal set |
| `POST /v1/opportunities/score-all` | Score all opportunity families |

## Opportunity families

- `automation`
- `consulting`
- `recruitment`
- `software`
- `procurement`
- `ma`
- `market_entry`

The scoring engine is deterministic and inspectable. AI reasoning can later enrich explanations, but it must not replace source evidence or make unsupported factual claims.

## Data model

### Company
Canonical organization identity, Companies House number, status, type, SIC codes, registered address and incorporation date.

### Evidence
A timestamped observation from a named source. Evidence contains the original fact payload or normalized source record plus confidence and source reference.

### Signal
A derived interpretation supported by one or more evidence IDs, such as distress, digital transformation, public contract activity or a contract award.

### Opportunity
A product-specific score from 0–100 with confidence, score components, rationale, evidence IDs and a recommended Raeburn action.

## Persistence

Development defaults to:

```text
sqlite:///./raeburn_intelligence.db
```

Production can use PostgreSQL:

```text
RIOS_DATABASE_URL=postgresql+psycopg://user:password@host/database
```

Historical evidence is intentionally retained so repeated observations can become change signals and proprietary time-series intelligence.

## Docker

```bash
docker build -t raeburn-intelligence-os .
docker run --rm -p 8000:8000 --env-file .env raeburn-intelligence-os
```

## Source governance

Every registered source records its canonical URL, jurisdiction, licence status, refresh cadence, collection method, supported entity types and supported signals.

The [Awesome Public Datasets](https://github.com/awesomedata/awesome-public-datasets) repository is treated only as a **discovery catalogue**. Each linked dataset must receive its own licence/terms review before commercial ingestion or redistribution.

Engineering rules:

1. Evidence before inference.
2. No unsupported factual claims.
3. Raw facts stay separate from derived signals.
4. Derived outputs retain evidence IDs.
5. Unknown licensing is not assumed to permit commercial reuse.
6. Historical observations are retained rather than overwritten.
7. Missing credentials fail explicitly rather than silently degrading data quality.

## Development checks

```bash
ruff check .
pytest -q
```

GitHub Actions runs the same checks on every push to `main` and on pull requests.

## Product direction

Version 0.3 establishes the reusable intelligence core and the first UK-company vertical. Additional connectors can now be added without changing the evidence → signal → opportunity contract. Natural next data families include public procurement awards, officers/directors, filings, labour-market demand, jobs, financial indicators, geographic economics, technology signals and market datasets.

The intended long-term role is to provide a shared intelligence layer to DiscoveryOS, RaeburnEmailer, ViraLink, RaeburnAI Executive and other Raeburn Group systems through stable APIs and evidence-backed opportunity events.
