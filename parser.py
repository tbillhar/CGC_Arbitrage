"""Parsing helpers for comic listing titles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


CGC_GRADE_RE = re.compile(
    r"\b(?:CGC|CBCS|PGX)?\s*(10(?:\.0)?|9\.[0-9]|[1-8](?:\.[0-9])?|0\.[5-9])\b",
    re.IGNORECASE,
)
ISSUE_RE = re.compile(r"(?:#|issue\s+)([A-Za-z0-9.\-/]+)", re.IGNORECASE)
PAGE_QUALITY_RE = re.compile(
    r"\b(white pages|wp|off[- ]white(?: to white)?|oww|cream(?: to off[- ]white)?|c/ow|"
    r"tan(?: to off[- ]white)?|brittle)\b",
    re.IGNORECASE,
)
SLAB_RE = re.compile(r"\b(CGC|CBCS|PGX)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedListing:
    title: str
    issue_number: Optional[str]
    grade: Optional[float]
    page_quality: Optional[str]
    grading_company: Optional[str]


def parse_listing_title(title: str) -> ParsedListing:
    """Extract common CGC listing details from an eBay title."""

    grade_match = CGC_GRADE_RE.search(title)
    issue_match = ISSUE_RE.search(title)
    page_match = PAGE_QUALITY_RE.search(title)
    slab_match = SLAB_RE.search(title)

    return ParsedListing(
        title=title,
        issue_number=issue_match.group(1) if issue_match else None,
        grade=float(grade_match.group(1)) if grade_match else None,
        page_quality=_normalize_page_quality(page_match.group(1)) if page_match else None,
        grading_company=slab_match.group(1).upper() if slab_match else None,
    )


def _normalize_page_quality(value: str) -> str:
    compact = value.strip().lower().replace("-", " ")
    aliases = {
        "wp": "White Pages",
        "white pages": "White Pages",
        "off white": "Off-White Pages",
        "off white to white": "Off-White to White Pages",
        "oww": "Off-White to White Pages",
        "cream": "Cream Pages",
        "cream to off white": "Cream to Off-White Pages",
        "c/ow": "Cream to Off-White Pages",
        "tan": "Tan Pages",
        "tan to off white": "Tan to Off-White Pages",
        "brittle": "Brittle Pages",
    }
    return aliases.get(compact, value.title())
