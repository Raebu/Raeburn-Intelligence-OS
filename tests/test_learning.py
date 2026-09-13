from types import SimpleNamespace

from intelligence_os import learning


def test_calibration_learns_multiplier_after_enough_outcomes(monkeypatch):
    rows = [
        SimpleNamespace(opportunity_kind="automation", outcome="won", revenue_gbp=10000),
        SimpleNamespace(opportunity_kind="automation", outcome="meeting", revenue_gbp=None),
        SimpleNamespace(opportunity_kind="automation", outcome="lost", revenue_gbp=None),
        SimpleNamespace(opportunity_kind="automation", outcome="won", revenue_gbp=5000),
    ]
    monkeypatch.setattr(learning, "list_outcomes", lambda: rows)
    result = learning.calibration()["kinds"]["automation"]
    assert result["count"] == 4
    assert result["positive"] == 3
    assert result["negative"] == 1
    assert result["revenue"] == 15000
    assert result["score_multiplier"] > 1.0
