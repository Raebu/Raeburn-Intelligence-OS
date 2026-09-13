from __future__ import annotations

from .models import SignalKind, SourceRecord

SOURCES: list[SourceRecord] = [
    SourceRecord(
        id="companies-house",
        name="Companies House",
        canonical_url="https://www.gov.uk/government/organisations/companies-house",
        category="companies",
        jurisdiction="GB",
        licence="Open Government Licence where applicable; verify dataset-specific terms",
        commercial_reuse=None,
        refresh_cadence="source-dependent",
        collection_method="api",
        entity_types=["company", "officer", "filing", "charge", "insolvency"],
        supported_signals=[
            SignalKind.DIRECTOR_CHANGE,
            SignalKind.HEADCOUNT_GROWTH,
            SignalKind.DISTRESS,
        ],
        notes="Treat filing-derived inference separately from statutory facts.",
    ),
    SourceRecord(
        id="contracts-finder",
        name="Contracts Finder",
        canonical_url="https://www.gov.uk/contracts-finder",
        category="procurement",
        jurisdiction="GB",
        licence="Verify record/feed terms before redistribution",
        commercial_reuse=None,
        refresh_cadence="daily",
        collection_method="api_or_feed",
        entity_types=["buyer", "supplier", "contract", "notice"],
        supported_signals=[
            SignalKind.PUBLIC_CONTRACT_WIN,
            SignalKind.PROCUREMENT_ACTIVITY,
        ],
    ),
    SourceRecord(
        id="find-a-tender",
        name="Find a Tender",
        canonical_url="https://www.gov.uk/find-tender",
        category="procurement",
        jurisdiction="GB",
        licence="Verify notice/feed terms before redistribution",
        commercial_reuse=None,
        refresh_cadence="daily",
        collection_method="api_or_feed",
        entity_types=["buyer", "supplier", "contract", "notice"],
        supported_signals=[
            SignalKind.PUBLIC_CONTRACT_WIN,
            SignalKind.PROCUREMENT_ACTIVITY,
        ],
    ),
    SourceRecord(
        id="ons",
        name="Office for National Statistics",
        canonical_url="https://www.ons.gov.uk/",
        category="economics",
        jurisdiction="GB",
        licence="Open Government Licence for many datasets; verify dataset-specific terms",
        commercial_reuse=None,
        refresh_cadence="dataset-dependent",
        collection_method="api_or_download",
        entity_types=["industry", "geography", "labour_market", "economic_series"],
        supported_signals=[SignalKind.HIRING_GROWTH, SignalKind.MARKET_GROWTH],
    ),
    SourceRecord(
        id="nomis",
        name="Nomis",
        canonical_url="https://www.nomisweb.co.uk/",
        category="labour_market",
        jurisdiction="GB",
        licence="Verify dataset-specific terms",
        commercial_reuse=None,
        refresh_cadence="dataset-dependent",
        collection_method="api",
        entity_types=["geography", "occupation", "industry", "labour_market"],
        supported_signals=[SignalKind.HIRING_GROWTH, SignalKind.MARKET_GROWTH],
    ),
    SourceRecord(
        id="website-technology",
        name="Public company website technology profile",
        canonical_url="https://github.com/Raebu/Raeburn-Intelligence-OS",
        category="technology",
        jurisdiction=None,
        licence="Observed public metadata only; respect target-site terms and access controls",
        commercial_reuse=None,
        refresh_cadence="on-demand",
        collection_method="public_web_observation",
        entity_types=["website", "technology"],
        supported_signals=[SignalKind.DIGITAL_TRANSFORMATION, SignalKind.AUTOMATION_GAP],
        notes="Uses visible HTML and response headers; does not bypass authentication or controls.",
    ),
    SourceRecord(
        id="public-careers-page",
        name="Public company careers page",
        canonical_url="https://github.com/Raebu/Raeburn-Intelligence-OS",
        category="jobs",
        jurisdiction=None,
        licence="Observed public page signals only; respect target-site terms and access controls",
        commercial_reuse=None,
        refresh_cadence="on-demand",
        collection_method="public_web_observation",
        entity_types=["job", "career_page"],
        supported_signals=[SignalKind.TECH_HIRING, SignalKind.HIRING_GROWTH],
        notes="Hiring growth is derived only when historical scans show an increase.",
    ),
    SourceRecord(
        id="data-gov-uk",
        name="data.gov.uk",
        canonical_url="https://www.data.gov.uk/",
        category="dataset_catalogue",
        jurisdiction="GB",
        licence="Per-dataset",
        commercial_reuse=None,
        refresh_cadence="catalogue-dependent",
        collection_method="catalogue",
        entity_types=["dataset"],
        supported_signals=[],
        notes="Discovery catalogue only. Licence and source quality must be assessed per dataset.",
    ),
    SourceRecord(
        id="awesome-public-datasets",
        name="Awesome Public Datasets",
        canonical_url="https://github.com/awesomedata/awesome-public-datasets",
        category="dataset_catalogue",
        jurisdiction=None,
        licence="Repository and linked datasets have separate licensing considerations",
        commercial_reuse=None,
        refresh_cadence="community-maintained",
        collection_method="catalogue",
        entity_types=["dataset"],
        supported_signals=[],
        notes=(
            "Use for source discovery, never as blanket permission to ingest or redistribute "
            "linked data."
        ),
    ),
]


def get_sources() -> list[SourceRecord]:
    return SOURCES


def get_source(source_id: str) -> SourceRecord | None:
    return next((source for source in SOURCES if source.id == source_id), None)
