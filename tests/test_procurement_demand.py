from datetime import UTC, datetime, timedelta

from intelligence_os.procurement_demand import rank_procurement_demand, score_procurement_demand


def _record(**overrides):
    now = datetime.now(UTC)
    record = {
        "source": "contracts-finder",
        "ocid": "ocds-test",
        "release_id": "r1",
        "date": now.isoformat(),
        "tags": ["tender"],
        "title": "Digital transformation and automation platform",
        "description": "The authority invites bids for workflow automation software.",
        "buyer": {"name": "Example Authority"},
        "tender_value": {"amount": 500000, "currency": "GBP"},
    }
    record.update(overrides)
    return record


def test_live_relevant_tender_scores():
    scored = score_procurement_demand(_record())
    assert scored["score"] > 0
    assert "automation" in scored["matched_keywords"]


def test_award_language_is_excluded():
    scored = score_procurement_demand(
        _record(description="Award of a contract for software implementation services.")
    )
    assert scored["score"] == 0
    assert scored["excluded"] == "not_live_tender"


def test_old_record_is_excluded_even_if_relevant():
    scored = score_procurement_demand(
        _record(date=(datetime.now(UTC) - timedelta(days=90)).isoformat())
    )
    assert scored["score"] == 0


def test_weak_staffing_match_alone_is_excluded():
    scored = score_procurement_demand(
        _record(
            title="Window Cleaning Services",
            description="The supplier must maintain sufficient staffing during peak periods.",
        )
    )
    assert scored["score"] == 0
    assert scored["excluded"] == "no_strong_commercial_match"


def test_rank_drops_false_positives():
    records = [
        _record(),
        _record(
            release_id="r2",
            title="Window Cleaning Services",
            description="Tender requiring sufficient staffing during peak periods.",
        ),
    ]
    ranked = rank_procurement_demand(records)
    assert len(ranked) == 1
    assert ranked[0]["release_id"] == "r1"
