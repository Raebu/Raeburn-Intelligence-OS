from datetime import datetime

from intelligence_os.db import EvidenceRow
from intelligence_os.signals import derive_signals


def _evidence(identifier: str, fact_type: str, value: dict) -> EvidenceRow:
    return EvidenceRow(
        id=identifier,
        company_id="c1",
        source_id="test",
        fact_type=fact_type,
        observed_at=datetime.now(),
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
        _evidence("j2", "job_scan", {"job_count": 12, "technology_job_count": 4}),
        _evidence("j1", "job_scan", {"job_count": 5, "technology_job_count": 1}),
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
