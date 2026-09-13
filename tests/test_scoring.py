from intelligence_os.models import OpportunityKind, OpportunityScoreRequest, SignalInput, SignalKind
from intelligence_os.scoring import score_all, score_opportunity


def test_automation_signals_produce_strong_score() -> None:
    request = OpportunityScoreRequest(
        company_id="acme",
        kind=OpportunityKind.AUTOMATION,
        signals=[
            SignalInput(kind=SignalKind.AUTOMATION_GAP, strength=0.95, confidence=0.9),
            SignalInput(kind=SignalKind.PUBLIC_CONTRACT_WIN, strength=0.8, confidence=0.95),
            SignalInput(kind=SignalKind.HIRING_GROWTH, strength=0.75, confidence=0.9),
        ],
    )

    opportunity = score_opportunity(request)

    assert opportunity.company_id == "acme"
    assert opportunity.kind is OpportunityKind.AUTOMATION
    assert opportunity.score >= 70
    assert opportunity.components


def test_score_all_returns_every_opportunity_kind() -> None:
    request = OpportunityScoreRequest(
        company_id="acme",
        signals=[SignalInput(kind=SignalKind.HIRING_GROWTH, strength=1, confidence=1)],
    )

    opportunities = score_all(request)

    assert {item.kind for item in opportunities} == set(OpportunityKind)
    assert opportunities[0].score >= opportunities[-1].score
