from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class HttpResponse:
    url: str
    final_url: str
    status: int
    content_type: str
    text: str


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    source: str
    query_id: str
    language_hint: str = ""
    published_at: datetime | None = None
    priority: int = 0


@dataclass
class MedicalEvent:
    title: str
    source_url: str
    registration_url: str
    source: str
    query_id: str
    language: str
    start_at: datetime | None = None
    end_at: datetime | None = None
    mode: str = "unknown"
    location: str = ""
    country: str = ""
    free_status: str = "unknown"
    free_evidence: str = ""
    certificate_status: str = "unknown"
    certificate_evidence: str = ""
    registration_closed: bool = False
    medical_relevance: bool = False
    event_relevance: bool = False
    organizer: str = ""
    confidence: int = 0
    evidence: list[str] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)

    def key(self) -> str:
        """Stable cross-source identity for one occurrence of an event."""
        start = ""
        if self.start_at:
            start = self.start_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        base = "|".join([_normalize_title(self.title), start])
        return sha256(base.encode("utf-8")).hexdigest()[:24]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["start_at"] = self.start_at.isoformat() if self.start_at else None
        data["end_at"] = self.end_at.isoformat() if self.end_at else None
        data["event_key"] = self.key()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MedicalEvent":
        values = dict(data)
        values.pop("event_key", None)
        for field_name in ("start_at", "end_at"):
            value = values.get(field_name)
            values[field_name] = datetime.fromisoformat(value) if value else None
        values.setdefault("evidence_sources", [])
        return cls(**values)


@dataclass(frozen=True)
class EligibilityDecision:
    accepted: bool
    reasons: tuple[str, ...]
    score: int


@dataclass
class ScanResult:
    accepted: list[MedicalEvent]
    new_events: list[MedicalEvent]
    state: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    scanned_hits: int
    fetched_pages: int
    rejected_count: int


def _normalize_title(value: str) -> str:
    value = (value or "").casefold()
    value = re.sub(r"[^\w\u0e00-\u0e7f\u3040-\u30ff\u4e00-\u9fff]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())
