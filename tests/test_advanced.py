from intelligence_os.advanced import tender_score


def test_tender_score_rewards_service_fit_and_preaward_stage():
    result = tender_score(
        {
            "title": "AI automation and digital transformation services",
            "description": "Software, data and consulting delivery",
            "tags": ["tender"],
            "buyer": {"name": "Example Council"},
            "tender_value": {"amount": 250000, "currency": "GBP"},
        }
    )
    assert result["score"] >= 70
    assert result["reasons"]


def test_tender_score_penalises_already_awarded_record():
    result = tender_score(
        {
            "title": "Software services",
            "tags": ["award"],
            "buyer": {"name": "Example Authority"},
        }
    )
    assert result["score"] < 50
