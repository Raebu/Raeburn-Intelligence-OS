from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .accounts import enrich_latest_accounts
from .advanced import capture_snapshot, evaluate_watchlists, infer_people, propose_actions
from .config import get_settings
from .db import init_db, list_companies
from .enrichment import enrich_companies_house
from .graph_engine import rebuild_enriched_graph
from .ownership import enrich_ownership
from .procurement import (
    attach_awards_to_indexed_companies,
    contracts_finder_feed,
    find_a_tender_feed,
)
from .service import opportunity_feed, refresh_company
from .uk import ExternalServiceError


def _window(hours: int) -> tuple[str, str]:
    end = datetime.now(UTC).replace(microsecond=0)
    start = end - timedelta(hours=hours)
    return start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S")


def run_radar(hours: int = 24, company_limit: int = 500) -> dict:
    init_db()
    settings = get_settings()
    refreshed = 0
    enriched = 0
    ownership_enriched = 0
    accounts_enriched = 0
    snapshots = 0
    graphs = 0
    proposed_actions = 0
    failures: list[dict[str, str]] = []

    companies = list_companies(limit=company_limit)
    if settings.companies_house_api_key:
        for company in companies:
            if not company.company_number:
                continue
            try:
                fresh = refresh_company(company.company_number)
                refreshed += 1
                enrich_companies_house(fresh.id)
                enriched += 1
                try:
                    enrich_ownership(fresh.id)
                    ownership_enriched += 1
                except (ExternalServiceError, KeyError):
                    pass
                try:
                    enrich_latest_accounts(fresh.id)
                    accounts_enriched += 1
                except (ExternalServiceError, KeyError):
                    pass
                infer_people(fresh.id)
                rebuild_enriched_graph(fresh.id)
                graphs += 1
            except (ExternalServiceError, KeyError, ValueError) as exc:
                failures.append({"company": company.id, "error": str(exc)})

    start, end = _window(hours)
    procurement: dict[str, object] = {}
    try:
        fts = find_a_tender_feed(
            updated_from=start,
            updated_to=end,
            stages="award",
            limit=100,
        )
        procurement["find_a_tender"] = attach_awards_to_indexed_companies(fts)
    except ExternalServiceError as exc:
        procurement["find_a_tender"] = {"error": str(exc)}

    try:
        cf = contracts_finder_feed(
            published_from=start,
            published_to=end,
            stages=["award"],
            size=100,
            page=1,
        )
        procurement["contracts_finder"] = attach_awards_to_indexed_companies(cf)
    except ExternalServiceError as exc:
        procurement["contracts_finder"] = {"error": str(exc)}

    for company in list_companies(limit=company_limit):
        try:
            capture_snapshot(company.id)
            snapshots += 1
            proposed_actions += len(propose_actions(company.id, minimum_score=70))
        except (KeyError, TypeError, ValueError) as exc:
            failures.append({"company": company.id, "error": str(exc)})

    alerts = evaluate_watchlists()
    ranked = opportunity_feed(limit=company_limit)
    return {
        "window_hours": hours,
        "companies_seen": len(companies),
        "companies_refreshed": refreshed,
        "companies_enriched": enriched,
        "ownership_enriched": ownership_enriched,
        "accounts_enriched": accounts_enriched,
        "snapshots_captured": snapshots,
        "graphs_rebuilt": graphs,
        "alerts_generated": len(alerts),
        "actions_proposed": proposed_actions,
        "procurement": procurement,
        "opportunities_ranked": len(ranked),
        "top_opportunities": ranked[:25],
        "failures": failures,
    }


def main() -> None:
    import json

    print(json.dumps(run_radar(), default=str, indent=2))


if __name__ == "__main__":
    main()
