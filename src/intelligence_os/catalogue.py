from __future__ import annotations

import re
from dataclasses import dataclass

DATASET_LINE = re.compile(
    r"^\* \|(?P<status>OK_ICON|FIXME_ICON)\| `(?P<title>.+?) <(?P<url>https?://[^>]+)>`_"
    r"(?: \[`Meta <(?P<meta_url>https?://[^>]+)>`_\])?\s*$"
)
SECTION_LINE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &/(),.+:'’-]+$")
UNDERLINE = re.compile(r"^-{3,}$")


@dataclass(frozen=True, slots=True)
class DatasetCandidate:
    title: str
    url: str
    category: str
    healthy: bool
    metadata_url: str | None = None


def parse_awesomedata_readme(text: str) -> list[DatasetCandidate]:
    """Parse dataset candidates from the generated Awesome Public Datasets README.

    This parser intentionally returns *candidates*, not trusted SourceRecords. A candidate
    still requires licence, provenance, freshness and commercial-reuse review before it can
    be promoted into the Raeburn source registry.
    """
    lines = text.splitlines()
    candidates: list[DatasetCandidate] = []
    current_section = "uncategorised"

    for index, line in enumerate(lines):
        stripped = line.strip()

        if (
            stripped
            and SECTION_LINE.match(stripped)
            and index + 1 < len(lines)
            and UNDERLINE.match(lines[index + 1].strip())
        ):
            current_section = stripped
            continue

        match = DATASET_LINE.match(stripped)
        if not match:
            continue

        groups = match.groupdict()
        candidates.append(
            DatasetCandidate(
                title=groups["title"],
                url=groups["url"],
                category=current_section,
                healthy=groups["status"] == "OK_ICON",
                metadata_url=groups.get("meta_url"),
            )
        )

    return candidates


def filter_candidates(
    candidates: list[DatasetCandidate],
    *,
    categories: set[str] | None = None,
    healthy_only: bool = True,
) -> list[DatasetCandidate]:
    result = candidates
    if healthy_only:
        result = [candidate for candidate in result if candidate.healthy]
    if categories:
        wanted = {category.casefold() for category in categories}
        result = [candidate for candidate in result if candidate.category.casefold() in wanted]
    return result
