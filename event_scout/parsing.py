from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from .constants import CLOSED_TERMS, EVENT_TERMS, MEDICAL_TERMS
from .dateparse import _parse_iso_datetime, _parse_text_datetime
from .htmlparse import _PageParser, extract_page_links, parse_rss
from .models import MedicalEvent, SearchHit
from .schema import (
    _choose_jsonld_event,
    _extract_certificate_status,
    _extract_free_status,
    _extract_location,
    _extract_mode,
    _extract_organizer,
    _registration_url,
    _schema_registration_closed,
)
from .text_utils import (
    _clean_text,
    _clean_url,
    _detect_language,
    _extract_location_text,
    _first_nonempty,
    _string_value,
)

def parse_event_page(hit: SearchHit, html: str, now: datetime) -> MedicalEvent:
    parser = _PageParser()
    parser.feed(html)
    page_text = _clean_text(" ".join(parser.text_parts))
    page_evidence_text = _clean_text(
        " ".join(
            [
                " ".join(parser.h1_parts),
                " ".join(parser.title_parts),
                parser.meta.get("description", ""),
                parser.meta.get("og:description", ""),
                page_text,
            ]
        )
    )
    combined_text = _clean_text(" ".join([hit.title, hit.snippet, page_evidence_text]))
    lower = page_evidence_text.casefold()

    jsonld_event = _choose_jsonld_event(parser.scripts, now)
    canonical = _clean_url(urljoin(hit.url, parser.canonical)) if parser.canonical else _clean_url(hit.url)

    title = _first_nonempty(
        _string_value(jsonld_event.get("name")) if jsonld_event else "",
        _clean_text(" ".join(parser.h1_parts)),
        parser.meta.get("og:title", ""),
        _clean_text(" ".join(parser.title_parts)),
        hit.title,
    )

    location, country = _extract_location(jsonld_event)
    default_tz = timezone.utc
    if country == "TH":
        default_tz = timezone(timedelta(hours=7))
    elif country == "JP":
        default_tz = timezone(timedelta(hours=9))

    start_at = _parse_iso_datetime(_string_value(jsonld_event.get("startDate")), default_tz) if jsonld_event else None
    end_at = _parse_iso_datetime(_string_value(jsonld_event.get("endDate")), default_tz) if jsonld_event else None
    if start_at is None:
        start_at, end_at = _parse_text_datetime(page_evidence_text, now)

    mode = _extract_mode(jsonld_event, page_evidence_text, country)
    if not location:
        location = _extract_location_text(page_evidence_text, mode)
    if not country and mode == "onsite_thailand":
        country = "TH"

    free_status, free_evidence = _extract_free_status(jsonld_event, page_evidence_text)
    certificate_status, certificate_evidence = _extract_certificate_status(page_evidence_text)
    registration_closed = any(term in lower for term in CLOSED_TERMS) or _schema_registration_closed(jsonld_event, now)
    language = _detect_language(combined_text, hit.language_hint)
    organizer = _extract_organizer(jsonld_event)
    registration_url = _registration_url(jsonld_event, parser.anchors, hit.url, canonical)

    medical_relevance = any(term in lower for term in MEDICAL_TERMS)
    event_relevance = any(term in lower for term in EVENT_TERMS)

    evidence: list[str] = []
    if jsonld_event:
        evidence.append("schema.org Event metadata")
    if free_evidence:
        evidence.append(free_evidence)
    if certificate_evidence:
        evidence.append(certificate_evidence)

    confidence = sum(
        [
            3 if jsonld_event else 0,
            2 if free_status == "confirmed" else 0,
            2 if mode in {"online", "hybrid_thailand", "onsite_thailand"} else 0,
            2 if start_at else 0,
            1 if medical_relevance else 0,
            1 if event_relevance else 0,
            1 if certificate_status != "unknown" else 0,
            1 if registration_url else 0,
        ]
    )

    return MedicalEvent(
        title=title or hit.title or "Untitled medical event",
        source_url=canonical or _clean_url(hit.url),
        registration_url=registration_url or canonical or _clean_url(hit.url),
        source=hit.source,
        query_id=hit.query_id,
        language=language,
        start_at=start_at,
        end_at=end_at,
        mode=mode,
        location=location,
        country=country,
        free_status=free_status,
        free_evidence=free_evidence,
        certificate_status=certificate_status,
        certificate_evidence=certificate_evidence,
        registration_closed=registration_closed,
        medical_relevance=medical_relevance,
        event_relevance=event_relevance,
        organizer=organizer,
        confidence=confidence,
        evidence=evidence,
        evidence_sources=[hit.source],
    )
