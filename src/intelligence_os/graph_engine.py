from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from .advanced import infer_people
from .db import (
    RelationRow,
    get_company,
    list_evidence,
    list_people,
    replace_relations,
)


def rebuild_enriched_graph(company_id: str) -> dict:
    company = get_company(company_id)
    if company is None:
        raise KeyError(company_id)
    people = list_people(company_id)
    if not people:
        infer_people(company_id)
        people = list_people(company_id)
    evidence = list_evidence(company_id)
    relations: list[RelationRow] = []
    now = datetime.now(UTC)

    for person in people:
        relations.append(
            RelationRow(
                id=str(uuid4()),
                source_type="company",
                source_id=company_id,
                relation="has_person",
                target_type="person",
                target_id=person.id,
                confidence=person.confidence,
                evidence_ids=person.evidence_ids,
                observed_at=now,
            )
        )

    psc = next(
        (row for row in evidence if row.fact_type == "persons_with_significant_control"),
        None,
    )
    if psc:
        for item in (psc.value or {}).get("items", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("name_elements") or "").strip()
            links = item.get("links") or {}
            target_id = str(links.get("self") or name).strip()
            if not target_id:
                continue
            kind = str(item.get("kind") or "psc")
            target_type = "company" if "corporate" in kind else "person"
            relations.append(
                RelationRow(
                    id=str(uuid4()),
                    source_type="company",
                    source_id=company_id,
                    relation="controlled_by",
                    target_type=target_type,
                    target_id=target_id,
                    confidence=1.0,
                    evidence_ids=[psc.id],
                    observed_at=psc.observed_at,
                )
            )

    for row in evidence:
        if row.fact_type == "contract_award":
            buyer = (row.value or {}).get("buyer") or {}
            buyer_id = str(buyer.get("id") or buyer.get("name") or "").strip()
            if buyer_id:
                relations.append(
                    RelationRow(
                        id=str(uuid4()),
                        source_type="company",
                        source_id=company_id,
                        relation="won_contract_from",
                        target_type="buyer",
                        target_id=buyer_id,
                        confidence=row.confidence,
                        evidence_ids=[row.id],
                        observed_at=row.observed_at,
                    )
                )
        elif row.fact_type == "technology_profile":
            for technology in (row.value or {}).get("technologies", []):
                relations.append(
                    RelationRow(
                        id=str(uuid4()),
                        source_type="company",
                        source_id=company_id,
                        relation="uses_technology",
                        target_type="technology",
                        target_id=str(technology),
                        confidence=row.confidence,
                        evidence_ids=[row.id],
                        observed_at=row.observed_at,
                    )
                )

    for sic in company.sic_codes:
        relations.append(
            RelationRow(
                id=str(uuid4()),
                source_type="company",
                source_id=company_id,
                relation="classified_as",
                target_type="sic",
                target_id=sic,
                confidence=1.0,
                evidence_ids=[],
                observed_at=now,
            )
        )

    replace_relations("company", company_id, relations)
    return {
        "company": company.model_dump(),
        "people": [row.model_dump() for row in people],
        "relations": [row.model_dump() for row in relations],
    }
