"""Parsing helpers for comic listing titles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


CGC_GRADE_RE = re.compile(
    r"\b(?:CGC|CBCS|PGX)?\s*(?:SS\s*)?(?:NM/MT\s*)?(10(?:\.0)?|9\.[0-9]|[1-8](?:\.[0-9])?|0\.[5-9])\b",
    re.IGNORECASE,
)
ISSUE_RE = re.compile(r"(?:#|issue\s+)([A-Za-z0-9.\-/]+)", re.IGNORECASE)
FALLBACK_ISSUE_RE = re.compile(r"\b([1-9][0-9]{0,3}(?:[A-Za-z]|/[A-Za-z])?)\b", re.IGNORECASE)
PAGE_QUALITY_RE = re.compile(
    r"\b(white pages|wp|off[- ]white(?: to white)?|oww|cream(?: to off[- ]white)?|c/ow|"
    r"tan(?: to off[- ]white)?|brittle)\b",
    re.IGNORECASE,
)
SLAB_RE = re.compile(r"\b(CGC|CBCS|PGX)\b", re.IGNORECASE)
FLAG_PATTERNS = {
    "signature_series": re.compile(r"\b(SS|signature series|signed)\b", re.IGNORECASE),
    "newsstand": re.compile(r"\bnewsstand\b", re.IGNORECASE),
    "direct": re.compile(r"\bdirect\b", re.IGNORECASE),
    "canadian_price_variant": re.compile(r"\b(CPV|canadian price variant)\b", re.IGNORECASE),
    "variant": re.compile(r"\bvariant\b", re.IGNORECASE),
    "first_appearance": re.compile(r"\b(1st|first appearance)\b", re.IGNORECASE),
}


@dataclass(frozen=True)
class ParsedListing:
    title: str
    issue_number: Optional[str]
    grade: Optional[float]
    page_quality: Optional[str]
    grading_company: Optional[str]
    flags: tuple[str, ...]

    @property
    def is_slabbed(self) -> bool:
        return self.grading_company is not None


def parse_listing_title(title: str) -> ParsedListing:
    """Extract common CGC listing details from an eBay title."""

    grade_match = CGC_GRADE_RE.search(title)
    issue_match = ISSUE_RE.search(title)
    page_match = PAGE_QUALITY_RE.search(title)
    slab_match = SLAB_RE.search(title)
    flags = tuple(name for name, pattern in FLAG_PATTERNS.items() if pattern.search(title))

    return ParsedListing(
        title=title,
        issue_number=issue_match.group(1) if issue_match else _fallback_issue_number(title, grade_match),
        grade=float(grade_match.group(1)) if grade_match else None,
        page_quality=_normalize_page_quality(page_match.group(1)) if page_match else None,
        grading_company=slab_match.group(1).upper() if slab_match else None,
        flags=flags,
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


def _fallback_issue_number(title: str, grade_match: Optional[re.Match[str]]) -> Optional[str]:
    protected_spans = []
    if grade_match:
        protected_spans.append(grade_match.span(1))

    for match in FALLBACK_ISSUE_RE.finditer(title):
        if any(_spans_overlap(match.span(1), span) for span in protected_spans):
            continue
        value = match.group(1)
        if _looks_like_year(value):
            continue
        return value
    return None


def _spans_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _looks_like_year(value: str) -> bool:
    return value.isdigit() and 1900 <= int(value) <= 2099
