from datetime import datetime

from intelligence_os.db import EvidenceRow
from intelligence_os.signals import derive_signals


def test_derive_distress_signal():
    evidence = [
        EvidenceRow(
            id="e1",
            company_id="c1",
            source_id="companies-house",
            fact_type="company_profile",
            observed_at=datetime.now(),
            value={"company_status": "liquidation", "sic_codes": []},
        )
    ]
    signals = derive_signals("c1", evidence)
    assert any(signal.kind == "distress" for signal in signals)


def test_derive_digital_signal():
    evidence = [
        EvidenceRow(
            id="e2",
            company_id="c1",
            source_id="companies-house",
            fact_type="company_profile",
            observed_at=datetime.now(),
            value={"company_status": "active", "sic_codes": ["62020"]},
        )
    ]
    signals = derive_signals("c1", evidence)
    assert any(signal.kind == "digital_transformation" for signal in signals)


def test_derive_procurement_signal():
    evidence = [
        EvidenceRow(
            id="p1",
            company_id="c1",
            source_id="contracts-finder",
            fact_type="procurement_notice",
            observed_at=datetime.now(),
            value={"title": "Digital transformation programme"},
        )
    ]
    signals = derive_signals("c1", evidence)
    assert any(signal.kind == "procurement_activity" for signal in signals)
