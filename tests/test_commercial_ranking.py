from datetime import UTC, datetime

from intelligence_os.db import CompanyRow
from intelligence_os.procurement_demand import score_procurement_demand
from intelligence_os.service import classify_commercial_role


def _company(name: str, sic_codes: list[str]) -> CompanyRow:
    return CompanyRow(
        id="gb:companies-house:01234567",
        name=name,
        company_number="01234567",
        sic_codes=sic_codes,
        updated_at=datetime.now(UTC),
    )


def test_technology_supplier_is_not_treated_as_default_customer():
    role = classify_commercial_role(_company("Example Software Limited", ["62020"]))
    assert role["role"] == "technology_supplier_or_partner"


def test_recruitment_supplier_is_identified():
    role = classify_commercial_role(_company("Example Recruitment Limited", ["78109"]))
    assert role["role"] == "recruitment_supplier_or_partner"


def test_live_ai_tender_scores_higher_than_irrelevant_tender():
    now = datetime(2026, 9, 14, tzinfo=UTC)
    relevant = score_procurement_demand(
        {
            "date": "2026-09-13T12:00:00Z",
            "title": "Artificial intelligence and workflow automation platform",
            "description": "Cloud software and data integration services",
            "tender_value": {"amount": 1500000, "currency": "GBP"},
        },
        now=now,
    )
    irrelevant = score_procurement_demand(
        {
            "date": "2026-09-13T12:00:00Z",
            "title": "Grounds maintenance",
            "description": "Grass cutting services",
            "tender_value": {"amount": 1500000, "currency": "GBP"},
        },
        now=now,
    )
    assert relevant["score"] > irrelevant["score"]
    assert relevant["score"] >= 70
