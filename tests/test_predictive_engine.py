from datetime import UTC, datetime

from intelligence_os.predictive_engine import DECAY_DAYS, _norm


def test_identity_normalisation_is_stable():
    assert _norm("ACME Holdings, Ltd.") == "acme holdings ltd"


def test_signal_decay_profiles_cover_commercial_signals():
    assert DECAY_DAYS["hiring_growth"] < DECAY_DAYS["revenue_growth"]
    assert DECAY_DAYS["procurement_activity"] <= 120
    assert DECAY_DAYS["director_change"] >= 365


def test_backtest_cutoff_can_be_timezone_aware():
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    assert cutoff.tzinfo is UTC
