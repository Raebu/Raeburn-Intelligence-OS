from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from hashlib import sha256
from html import unescape
from typing import Any

import httpx

from .config import get_settings
from .db import (
    EvidenceRow,
    get_company,
    list_evidence,
    replace_signals,
    save_evidence,
)
from .signals import derive_signals
from .uk import ExternalServiceError

FACT_ALIASES = {
    "turnover": ("turnoverrevenue", "revenue", "turnover"),
    "cash": ("cashbankonhand", "cashandcashequivalents", "cash"),
    "net_assets": ("netassetsliabilities", "netassets"),
    "liabilities": ("creditors", "totalliabilities"),
    "employees": ("averagenumberemployeesduringperiod", "averageemployees", "employees"),
}


def _auth_header(api_key: str) -> str:
    token = base64.b64encode(f"{api_key}:".encode()).decode()
    return f"Basic {token}"


def _number(text: str) -> float | None:
    cleaned = unescape(re.sub(r"<[^>]+>", "", text)).strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.replace(",", "").replace("£", "").replace("(", "").replace(")", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    value = float(match.group())
    return -value if negative else value


def extract_ixbrl_metrics(content: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    tags = re.findall(
        r"<(?:ix:)?(?:nonfraction|nonnumeric)[^>]*name=[\"']([^\"']+)[\"'][^>]*>(.*?)</(?:ix:)?(?:nonfraction|nonnumeric)>",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for fact_name, body in tags:
        normalized = re.sub(r"[^a-z0-9]", "", fact_name.lower().split(":")[-1])
        for metric, aliases in FACT_ALIASES.items():
            if metric in metrics:
                continue
            if any(alias in normalized for alias in aliases):
                value = _number(body)
                if value is not None:
                    metrics[metric] = value
    return metrics


def _accounts_documents(company_id: str, limit: int = 2) -> list[tuple[str, str]]:
    filing = next((row for row in list_evidence(company_id) if row.fact_type == "filing_history"), None)
    if not filing:
        return []
    documents: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in (filing.value or {}).get("items", []):
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").lower()
        description = str(item.get("description") or "").lower()
        if "account" not in category and "account" not in description:
            continue
        links = item.get("links") or {}
        metadata = str(links.get("document_metadata") or "")
        match = re.search(r"/document/([^/?]+)", metadata)
        if not match:
            continue
        document_id = match.group(1)
        if document_id in seen:
            continue
        seen.add(document_id)
        documents.append((document_id, str(item.get("date") or item.get("made_up_date") or "")))
        if len(documents) >= limit:
            break
    return documents


def _fetch_metrics(
    document_id: str,
    headers: dict[str, str],
    base_url: str,
    timeout: float,
) -> tuple[str, dict[str, float]]:
    url = f"{base_url.rstrip('/')}/document/{document_id}/content"
    response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ExternalServiceError(f"Companies House Document API returned {response.status_code}") from exc
    return url, extract_ixbrl_metrics(response.text)


def _cached_financials(company_id: str) -> dict[str, EvidenceRow]:
    return {
        str((row.value or {}).get("document_id") or row.raw_reference): row
        for row in list_evidence(company_id)
        if row.fact_type == "financial_metrics"
        and ((row.value or {}).get("document_id") or row.raw_reference)
    }


def enrich_latest_accounts(company_id: str) -> dict[str, Any]:
    company = get_company(company_id)
    if company is None:
        raise KeyError(company_id)
    documents = _accounts_documents(company_id, limit=2)
    if not documents:
        raise KeyError("No accounts filing with a document link is stored")
    settings = get_settings()
    if not settings.companies_house_api_key:
        raise ExternalServiceError("Companies House accounts access requires RIOS_COMPANIES_HOUSE_API_KEY")
    headers = {
        "Authorization": _auth_header(settings.companies_house_api_key),
        "User-Agent": settings.user_agent,
        "Accept": "application/xhtml+xml,application/xml,text/html;q=0.9,*/*;q=0.1",
    }

    cached = _cached_financials(company_id)
    saved: list[dict[str, Any]] = []
    fetched = 0
    for document_id, filing_date in documents:
        existing = cached.get(document_id)
        if existing is not None:
            saved.append(
                {
                    "document_id": document_id,
                    "filing_date": str((existing.value or {}).get("filing_date") or filing_date),
                    "metrics": {
                        key: value
                        for key, value in (existing.value or {}).items()
                        if key in FACT_ALIASES
                    },
                    "evidence_id": existing.id,
                    "cached": True,
                }
            )
            continue

        url, metrics = _fetch_metrics(
            document_id,
            headers,
            settings.companies_house_document_base_url,
            settings.request_timeout_seconds,
        )
        payload = {
            **metrics,
            "document_id": document_id,
            "filing_date": filing_date,
            "extraction_method": "ixbrl-fact-alias-v1",
        }
        digest = sha256(repr(payload).encode()).hexdigest()[:20]
        evidence_id = f"ch-accounts:{company_id}:{digest}"
        evidence = EvidenceRow(
            id=evidence_id,
            company_id=company_id,
            source_id="companies-house-document-api",
            fact_type="financial_metrics",
            observed_at=datetime.now(UTC),
            source_url=url,
            value=payload,
            confidence=0.9 if metrics else 0.5,
            raw_reference=document_id,
        )
        save_evidence([evidence])
        fetched += 1
        saved.append(
            {
                "document_id": document_id,
                "filing_date": filing_date,
                "metrics": metrics,
                "evidence_id": evidence_id,
                "cached": False,
            }
        )

    replace_signals(company_id, derive_signals(company_id, list_evidence(company_id)))
    latest = saved[0]
    return {
        "company_id": company_id,
        "document_id": latest["document_id"],
        "filing_date": latest["filing_date"],
        "metrics": latest["metrics"],
        "evidence_id": latest["evidence_id"],
        "documents_ingested": len(saved),
        "documents_fetched": fetched,
        "history": saved,
    }
