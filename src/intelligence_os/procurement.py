from __future__ import annotations

import re
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from .db import EvidenceRow, get_company_by_number, list_evidence, replace_signals, save_evidence
from .service import refresh_company
from .signals import derive_signals
from .uk import CompaniesHouseClient, ContractsFinderClient, ExternalServiceError, FindATenderClient


def _now() -> datetime:
    return datetime.now(UTC)


def _release_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    releases = payload.get("releases")
    if isinstance(releases, list):
        return [row for row in releases if isinstance(row, dict)]
    packages = payload.get("releasePackages")
    if isinstance(packages, list):
        rows: list[dict[str, Any]] = []
        for package in packages:
            if isinstance(package, dict):
                rows.extend(row for row in package.get("releases", []) if isinstance(row, dict))
        return rows
    return []


def normalize_release(release: dict[str, Any], source: str) -> dict[str, Any]:
    tender = release.get("tender") or {}
    buyer = release.get("buyer") or {}
    awards = release.get("awards") or []
    tags = release.get("tag") or release.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    suppliers: list[dict[str, Any]] = []
    award_value = None
    for award in awards:
        if not isinstance(award, dict):
            continue
        value = award.get("value") or {}
        if award_value is None and isinstance(value, dict):
            award_value = value
        for supplier in award.get("suppliers") or []:
            if isinstance(supplier, dict):
                suppliers.append(supplier)
    tender_value = tender.get("value") if isinstance(tender, dict) else None
    return {
        "source": source,
        "ocid": release.get("ocid"),
        "release_id": release.get("id"),
        "date": release.get("date"),
        "tags": tags,
        "title": tender.get("title") or release.get("title"),
        "description": tender.get("description") or release.get("description"),
        "buyer": buyer,
        "tender_value": tender_value,
        "award_value": award_value,
        "suppliers": suppliers,
        "raw": release,
    }


def find_a_tender_feed(
    *,
    updated_from: str | None = None,
    updated_to: str | None = None,
    stages: str | None = None,
    limit: int = 100,
    cursor: str | None = None,
) -> list[dict[str, Any]]:
    payload = FindATenderClient().releases(
        updated_from=updated_from,
        updated_to=updated_to,
        stages=stages,
        limit=limit,
        cursor=cursor,
    )
    return [normalize_release(row, "find-a-tender") for row in _release_rows(payload)]


def contracts_finder_feed(
    *,
    published_from: str | None = None,
    published_to: str | None = None,
    stages: list[str] | None = None,
    size: int = 100,
    page: int = 1,
) -> list[dict[str, Any]]:
    payload = ContractsFinderClient().search(
        published_from=published_from,
        published_to=published_to,
        stages=stages,
        size=size,
        page=page,
    )
    return [normalize_release(row, "contracts-finder") for row in _release_rows(payload)]


def _valid_company_number(value: object) -> str | None:
    if value is None:
        return None
    number = re.sub(r"\s+", "", str(value)).upper()
    if re.fullmatch(r"(?:\d{8}|[A-Z]{2}\d{6}|[A-Z]\d{7})", number):
        return number
    return None


def _company_number_from_supplier(supplier: dict[str, Any]) -> str | None:
    identifier = supplier.get("identifier") or {}
    identifiers = [identifier] if isinstance(identifier, dict) else []
    additional = supplier.get("additionalIdentifiers") or supplier.get("additional_identifiers") or []
    identifiers.extend(row for row in additional if isinstance(row, dict))

    direct = _valid_company_number(supplier.get("company_number"))
    if direct:
        return direct

    # Prefer identifiers explicitly declared as UK Companies House identifiers.
    for row in identifiers:
        scheme = str(row.get("scheme") or "").upper()
        if scheme in {"GB-COH", "GB-CHC", "UK-COH", "COH"}:
            number = _valid_company_number(row.get("id"))
            if number:
                return number

    # Some UK procurement feeds omit the scheme but still publish the CH number as id.
    for row in identifiers:
        number = _valid_company_number(row.get("id"))
        if number:
            return number
    return None


def _normalise_name(value: str) -> str:
    value = value.upper().replace("&", "AND")
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    words = value.split()
    suffixes = {"LIMITED", "LTD", "PLC", "LLP"}
    while words and words[-1] in suffixes:
        words.pop()
    return " ".join(words)


def _resolve_supplier_by_name(supplier: dict[str, Any], client: CompaniesHouseClient) -> str | None:
    name = str(supplier.get("name") or "").strip()
    if len(name) < 3:
        return None
    target = _normalise_name(name)
    if not target:
        return None
    matches = client.search(name, items_per_page=10)
    exact = [row for row in matches if _normalise_name(str(row.get("title") or "")) == target]
    active = [row for row in exact if row.get("company_status") == "active"]
    candidates = active or exact
    if len(candidates) != 1:
        return None
    return _valid_company_number(candidates[0].get("company_number"))


def attach_awards_to_indexed_companies(
    records: list[dict[str, Any]], *, bootstrap_missing: bool = False
) -> dict[str, int]:
    linked = 0
    awards = 0
    bootstrapped = 0
    bootstrap_failures = 0
    suppliers_seen = 0
    suppliers_with_number = 0
    suppliers_resolved_by_name = 0
    unresolved_suppliers = 0
    seen_numbers: set[str] = set()
    seen_names: dict[str, str | None] = {}
    ch_client = CompaniesHouseClient() if bootstrap_missing else None

    for record in records:
        for supplier in record.get("suppliers", []):
            suppliers_seen += 1
            number = _company_number_from_supplier(supplier)
            if number:
                suppliers_with_number += 1
            elif bootstrap_missing and ch_client is not None:
                name = str(supplier.get("name") or "").strip()
                cache_key = _normalise_name(name)
                if cache_key not in seen_names:
                    try:
                        seen_names[cache_key] = _resolve_supplier_by_name(supplier, ch_client)
                    except (ExternalServiceError, KeyError, ValueError):
                        seen_names[cache_key] = None
                        bootstrap_failures += 1
                number = seen_names.get(cache_key)
                if number:
                    suppliers_resolved_by_name += 1

            if not number:
                unresolved_suppliers += 1
                continue

            company = get_company_by_number(number)
            if company is None and bootstrap_missing and number not in seen_numbers:
                seen_numbers.add(number)
                try:
                    company = refresh_company(number)
                    bootstrapped += 1
                except (ExternalServiceError, KeyError, ValueError):
                    bootstrap_failures += 1
                    company = None
            if company is None:
                continue

            payload = {
                "source": record.get("source"),
                "ocid": record.get("ocid"),
                "release_id": record.get("release_id"),
                "title": record.get("title"),
                "buyer": record.get("buyer"),
                "award_value": record.get("award_value"),
                "supplier": supplier,
            }
            digest = sha256(repr(payload).encode()).hexdigest()[:20]
            row = EvidenceRow(
                id=f"procurement-award:{company.id}:{digest}",
                company_id=company.id,
                source_id=str(record.get("source") or "procurement"),
                fact_type="contract_award",
                observed_at=_now(),
                source_url=None,
                value=payload,
                confidence=0.95,
                raw_reference=str(record.get("ocid") or record.get("release_id") or digest),
            )
            save_evidence([row])
            replace_signals(company.id, derive_signals(company.id, list_evidence(company.id)))
            linked += 1
            awards += 1

    return {
        "records": len(records),
        "suppliers_seen": suppliers_seen,
        "suppliers_with_number": suppliers_with_number,
        "suppliers_resolved_by_name": suppliers_resolved_by_name,
        "unresolved_suppliers": unresolved_suppliers,
        "linked_companies": linked,
        "awards_attached": awards,
        "companies_bootstrapped": bootstrapped,
        "bootstrap_failures": bootstrap_failures,
    }
