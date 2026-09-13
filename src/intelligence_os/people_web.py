from __future__ import annotations

import re
from datetime import UTC, datetime
from hashlib import sha256
from html import unescape
from urllib.parse import urlparse

import httpx

from .config import get_settings
from .db import EvidenceRow, PersonRow, get_company, list_people, replace_people, save_evidence
from .uk import ExternalServiceError

ROLE_PATTERNS = {
    "executive": ["chief executive officer", "chief executive", "ceo", "managing director"],
    "technology": ["chief technology officer", "cto", "chief information officer", "cio"],
    "operations": ["chief operating officer", "coo", "operations director"],
    "transformation": ["transformation director", "head of transformation", "digital director"],
    "people": ["people director", "hr director", "talent director", "head of talent"],
    "finance": ["chief financial officer", "cfo", "finance director"],
}


def _clean_html(html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def extract_decision_makers(html: str) -> list[dict]:
    text = _clean_html(html)
    results: list[dict] = []
    name = r"[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){1,3}"
    for family, roles in ROLE_PATTERNS.items():
        for role in roles:
            escaped = re.escape(role)
            patterns = [
                rf"(?P<name>{name})\s*[-–—,:|]\s*(?P<role>{escaped})\b",
                rf"(?P<role>{escaped})\s*[-–—,:|]\s*(?P<name>{name})\b",
                rf"(?P<name>{name})\s+(?:is\s+)?(?:the\s+)?(?P<role>{escaped})\b",
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, text, flags=re.I):
                    person = match.group("name").strip()
                    if len(person.split()) < 2:
                        continue
                    record = {
                        "name": person,
                        "role": role,
                        "role_family": family,
                        "confidence": 0.6,
                    }
                    if record not in results:
                        results.append(record)
    return results[:50]


def enrich_public_people(company_id: str, url: str) -> dict:
    company = get_company(company_id)
    if company is None:
        raise KeyError(company_id)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("A valid public http(s) URL is required")
    settings = get_settings()
    response = httpx.get(
        url,
        timeout=settings.request_timeout_seconds,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ExternalServiceError(f"Leadership page returned {response.status_code}") from exc
    records = extract_decision_makers(response.text[:2_000_000])
    observed = datetime.now(UTC)
    payload = {"url": str(response.url), "people": records, "method": "public-role-text-v1"}
    digest = sha256(repr(payload).encode()).hexdigest()[:20]
    evidence = EvidenceRow(
        id=f"web-people:{company_id}:{digest}",
        company_id=company_id,
        source_id="public-company-website",
        fact_type="decision_makers",
        observed_at=observed,
        source_url=str(response.url),
        value=payload,
        confidence=0.6,
        raw_reference=str(response.url),
    )
    save_evidence([evidence])

    existing = list_people(company_id)
    by_key = {(row.name.lower(), (row.role or "").lower()): row for row in existing}
    for record in records:
        key = (record["name"].lower(), record["role"].lower())
        if key in by_key:
            continue
        row = PersonRow(
            id=f"{company_id}:web:{digest}:{len(by_key)}",
            company_id=company_id,
            name=record["name"],
            role=record["role"],
            role_family=record["role_family"],
            confidence=record["confidence"],
            source_url=str(response.url),
            evidence_ids=[evidence.id],
            updated_at=observed,
        )
        by_key[key] = row
    replace_people(company_id, list(by_key.values()))
    return {"company_id": company_id, "people_found": records, "evidence_id": evidence.id}
