from __future__ import annotations

from .models import (
    Opportunity,
    OpportunityKind,
    OpportunityScoreRequest,
    ScoreComponent,
    SignalInput,
    SignalKind,
)

WEIGHTS: dict[OpportunityKind, dict[SignalKind, float]] = {
    OpportunityKind.AUTOMATION: {
        SignalKind.AUTOMATION_GAP: 1.0,
        SignalKind.HIRING_GROWTH: 0.65,
        SignalKind.TECH_HIRING: 0.55,
        SignalKind.PUBLIC_CONTRACT_WIN: 0.65,
        SignalKind.REVENUE_GROWTH: 0.55,
        SignalKind.HEADCOUNT_GROWTH: 0.45,
        SignalKind.DIGITAL_TRANSFORMATION: 0.9,
        SignalKind.PROCUREMENT_ACTIVITY: 0.45,
    },
    OpportunityKind.CONSULTING: {
        SignalKind.PUBLIC_CONTRACT_WIN: 0.7,
        SignalKind.REVENUE_GROWTH: 0.65,
        SignalKind.HEADCOUNT_GROWTH: 0.6,
        SignalKind.NEW_LOCATION: 0.65,
        SignalKind.DIRECTOR_CHANGE: 0.35,
        SignalKind.DIGITAL_TRANSFORMATION: 0.9,
        SignalKind.MARKET_GROWTH: 0.5,
    },
    OpportunityKind.RECRUITMENT: {
        SignalKind.HIRING_GROWTH: 1.0,
        SignalKind.TECH_HIRING: 0.85,
        SignalKind.HEADCOUNT_GROWTH: 0.75,
        SignalKind.NEW_LOCATION: 0.65,
        SignalKind.PUBLIC_CONTRACT_WIN: 0.55,
        SignalKind.REVENUE_GROWTH: 0.4,
    },
    OpportunityKind.SOFTWARE: {
        SignalKind.AUTOMATION_GAP: 0.8,
        SignalKind.TECH_HIRING: 0.6,
        SignalKind.DIGITAL_TRANSFORMATION: 1.0,
        SignalKind.HEADCOUNT_GROWTH: 0.45,
        SignalKind.PUBLIC_CONTRACT_WIN: 0.5,
    },
    OpportunityKind.PROCUREMENT: {
        SignalKind.PROCUREMENT_ACTIVITY: 1.0,
        SignalKind.PUBLIC_CONTRACT_WIN: 0.55,
        SignalKind.DIGITAL_TRANSFORMATION: 0.5,
        SignalKind.MARKET_GROWTH: 0.35,
    },
    OpportunityKind.MA: {
        SignalKind.REVENUE_GROWTH: 0.6,
        SignalKind.MARKET_GROWTH: 0.55,
        SignalKind.DISTRESS: 0.75,
        SignalKind.DIRECTOR_CHANGE: 0.35,
        SignalKind.HEADCOUNT_GROWTH: 0.35,
    },
    OpportunityKind.MARKET_ENTRY: {
        SignalKind.MARKET_GROWTH: 1.0,
        SignalKind.NEW_LOCATION: 0.55,
        SignalKind.PROCUREMENT_ACTIVITY: 0.5,
        SignalKind.HIRING_GROWTH: 0.35,
    },
}


def _score_kind(kind: OpportunityKind, signals: list[SignalInput]) -> Opportunity:
    weights = WEIGHTS[kind]
    components: list[ScoreComponent] = []
    weighted_sum = 0.0
    confidences: list[float] = []
    evidence_ids: set[str] = set()

    strongest_by_kind: dict[SignalKind, SignalInput] = {}
    for signal in signals:
        existing = strongest_by_kind.get(signal.kind)
        effective = signal.strength * signal.confidence
        if existing is None or effective > existing.strength * existing.confidence:
            strongest_by_kind[signal.kind] = signal

    for signal_kind, signal in strongest_by_kind.items():
        weight = weights.get(signal_kind)
        if not weight:
            continue
        contribution = weight * signal.strength * signal.confidence
        weighted_sum += contribution
        confidences.append(signal.confidence)
        evidence_ids.update(signal.evidence_ids)
        components.append(
            ScoreComponent(
                signal=signal_kind,
                weight=weight,
                strength=signal.strength,
                confidence=signal.confidence,
                contribution=round(contribution, 4),
            )
        )

    if not components:
        raw_score = 0.0
        confidence = 0.0
    else:
        # Saturating score rewards multiple corroborating signals without requiring
        # every possible signal to be present.
        raw_score = min(1.0, weighted_sum / 2.25)
        confidence = sum(confidences) / len(confidences)

    score = round(raw_score * 100)
    components.sort(key=lambda item: item.contribution, reverse=True)
    top = ", ".join(component.signal.value.replace("_", " ") for component in components[:3])
    rationale = (
        f"{kind.value.replace('_', ' ').title()} opportunity scored from "
        f"{len(components)} relevant signal(s): {top}."
        if components
        else f"No relevant evidence-backed signals currently support a {kind.value} opportunity."
    )

    return Opportunity(
        company_id="",
        kind=kind,
        score=score,
        confidence=round(confidence, 4),
        rationale=rationale,
        components=components,
        evidence_ids=sorted(evidence_ids),
    )


def score_opportunity(request: OpportunityScoreRequest) -> Opportunity:
    if request.kind is not None:
        result = _score_kind(request.kind, request.signals)
        return result.model_copy(update={"company_id": request.company_id})

    candidates = [_score_kind(kind, request.signals) for kind in OpportunityKind]
    winner = max(candidates, key=lambda item: (item.score, item.confidence))
    return winner.model_copy(update={"company_id": request.company_id})


def score_all(request: OpportunityScoreRequest) -> list[Opportunity]:
    results = []
    for kind in OpportunityKind:
        result = _score_kind(kind, request.signals)
        results.append(result.model_copy(update={"company_id": request.company_id}))
    return sorted(results, key=lambda item: (item.score, item.confidence), reverse=True)
