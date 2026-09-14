from datetime import UTC, datetime

from intelligence_os.db import EvidenceRow
from intelligence_os.signals import derive_signals


def _evidence(
    identifier: str,
    fact_type: str,
    value: dict,
    observed_at: datetime | None = None,
) -> EvidenceRow:
    return EvidenceRow(
        id=identifier,
        company_id="c1",
        source_id="test",
        fact_type=fact_type,
        observed_at=observed_at or datetime.now(UTC),
        value=value,
    )


def test_derive_distress_signal():
    signals = derive_signals(
        "c1",
        [_evidence("e1", "company_profile", {"company_status": "liquidation", "sic_codes": []})],
    )
    assert any(signal.kind == "distress" for signal in signals)


def test_derive_digital_signal():
    signals = derive_signals(
        "c1",
        [_evidence("e2", "company_profile", {"company_status": "active", "sic_codes": ["62020"]})],
    )
    assert any(signal.kind == "digital_transformation" for signal in signals)


def test_derive_procurement_signal():
    signals = derive_signals(
        "c1",
        [_evidence("p1", "procurement_notice", {"title": "Digital transformation programme"})],
    )
    assert any(signal.kind == "procurement_activity" for signal in signals)


def test_derive_director_change_signal():
    signals = derive_signals(
        "c1",
        [_evidence("o1", "officers", {"items": [{"name": "A Director", "resigned_on": "2026-01-01"}]})],
    )
    assert any(signal.kind == "director_change" for signal in signals)


def test_old_director_change_is_not_current_signal():
    signals = derive_signals(
        "c1",
        [_evidence("o1", "officers", {"items": [{"name": "A Director", "resigned_on": "2018-01-01"}]})],
    )
    assert not any(signal.kind == "director_change" for signal in signals)


def test_derive_technology_signal():
    signals = derive_signals(
        "c1",
        [_evidence("t1", "technology_profile", {"technologies": ["nextjs", "hubspot"]})],
    )
    assert any(signal.kind == "digital_transformation" for signal in signals)


def test_derive_tech_hiring_and_growth_signals():
    evidence = [
        _evidence(
            "j2",
            "job_scan",
            {"job_count": 12, "technology_job_count": 4},
            datetime(2026, 9, 14, tzinfo=UTC),
        ),
        _evidence(
            "j1",
            "job_scan",
            {"job_count": 5, "technology_job_count": 1},
            datetime(2026, 8, 14, tzinfo=UTC),
        ),
    ]
    signals = derive_signals("c1", evidence)
    kinds = {signal.kind for signal in signals}
    assert "tech_hiring" in kinds
    assert "hiring_growth" in kinds


def test_derive_filing_distress_signal():
    signals = derive_signals(
        "c1",
        [
            _evidence(
                "f1",
                "filing_history",
                {
                    "items": [
                        {
                            "date": "2026-08-01",
                            "category": "insolvency",
                            "description": "administration",
                        }
                    ]
                },
            )
        ],
    )
    assert any(signal.kind == "distress" for signal in signals)


def test_old_solvency_statement_is_not_distress():
    signals = derive_signals(
        "c1",
        [
            _evidence(
                "f1",
                "filing_history",
                {
                    "items": [
                        {
                            "date": "2022-05-27",
                            "category": "insolvency",
                            "description": "legacy",
                            "type": "CAP-SS",
                            "description_values": {
                                "description": "Solvency Statement dated 26/05/22"
                            },
                        }
                    ]
                },
            )
        ],
    )
    assert not any(signal.kind == "distress" for signal in signals)


def test_financial_history_creates_revenue_and_headcount_growth():
    signals = derive_signals(
        "c1",
        [
            _evidence(
                "a2",
                "financial_metrics",
                {"filing_date": "2026-06-01", "turnover": 1500000, "employees": 30},
            ),
            _evidence(
                "a1",
                "financial_metrics",
                {"filing_date": "2025-06-01", "turnover": 1000000, "employees": 20},
            ),
        ],
    )
    kinds = {signal.kind for signal in signals}
    assert "revenue_growth" in kinds
    assert "headcount_growth" in kinds


def test_duplicate_contract_awards_are_counted_once():
    signals = derive_signals(
        "c1",
        [
            _evidence(
                "c1",
                "contract_award",
                {
                    "date": "2026-09-01",
                    "title": "2026-049 Telephony Solutions for D&S",
                    "buyer": {"name": "Ofgem"},
                    "award_value": {"amount": 940000, "currency": "GBP"},
                },
            ),
            _evidence(
                "c2",
                "contract_award",
                {
                    "date": "2026-09-01",
                    "title": "Telephony Solutions",
                    "buyer": {"name": "Ofgem"},
                    "award_value": {"amount": 940000, "currency": "GBP"},
                },
            ),
        ],
    )
    contract_signal = next(signal for signal in signals if signal.kind == "public_contract_win")
    assert "1 deduplicated" in (contract_signal.explanation or "")
    assert contract_signal.strength >= 0.7
