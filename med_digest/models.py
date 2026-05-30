from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Paper:
    title: str
    abstract: str = ""
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    year: str = ""
    date: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    source: str = ""
    url: str = ""
    publication_type: str = ""
    category: str = ""
    is_preprint: bool = False
    matched_profiles: List[str] = field(default_factory=list)
    relevance_score: int = 0
    evidence_score: int = 0
    total_score: int = 0
    decision: str = "candidate"
    summary: str = ""
    limitations: str = ""
    confidence: str = "Low"
    raw: Dict[str, Any] = field(default_factory=dict)

    def dedupe_key(self) -> str:
        for prefix, value in (("pmid", self.pmid), ("doi", self.doi), ("pmcid", self.pmcid)):
            cleaned = (value or "").strip().lower()
            if cleaned:
                return f"{prefix}:{cleaned}"
        return "title:" + normalize_title(self.title)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_title(title: str) -> str:
    keep = []
    for ch in (title or "").lower():
        if ch.isalnum() or ch.isspace():
            keep.append(ch)
    return " ".join("".join(keep).split())
