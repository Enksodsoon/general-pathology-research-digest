from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit

from .constants import CLOSED_TERMS, EVENT_TERMS, MEDICAL_TERMS
from .dateparse import _parse_iso_datetime, _parse_text_datetime
from .htmlparse import _PageParser, extract_page_links, parse_rss
from .link_selection import registration_url as _registration_url
from .models import MedicalEvent, SearchHit
from .schema import (
    _choose_jsonld_event,
    _extract_certificate_status,
    _extract_free_status,
    _extract_location,
    _extract_mode,
    _extract_organizer,
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


_GENERIC_PAGE_LABELS = {
    "event",
    "events",
    "event listings",
    "upcoming events",
    "webinar",
    "webinars",
    "webinar webinar",
    "seminar",
    "seminars",
    "past webinars",
    "archived webinar",
    "archived webinars",
    "on demand",
    "on demand webinar",
    "on demand webinars",
    "free attendance webinar",
    "free webinars",
    "ウェビナー",
    "webinar ウェビナー",
    "無料聴講ウェビナー",
    "過去のウェビナー",
    "オンデマンド",
    "オンデマンドウェビナー",
    "イベント一覧",
    "セミナー一覧",
    "กิจกรรม",
    "รายการกิจกรรม",
}

_GENERIC_PATH_PARTS = {
    "event",
    "events",
    "webinar",
    "webinars",
    "seminar",
    "seminars",
    "past",
    "archive",
    "archived",
    "ondemand",
    "on-demand",
    "free",
}


def parse_event_page(hit: SearchHit, html: str, now: datetime) -> MedicalEvent:
    parser = _PageParser()
    parser.feed(html)
    page_text = _clean_text(" ".join(parser.text_parts))
    h1_text = _clean_text(" ".join(parser.h1_parts))
    document_title = _clean_text(" ".join(parser.title_parts))

    jsonld_event = _choose_jsonld_event(parser.scripts, now)
    if jsonld_event and h1_text and not _jsonld_matches_heading(jsonld_event, h1_text):
        # Shared site templates sometimes embed the parent trade show's Event
        # object on every webinar page. Ignore it when it describes another event.
        jsonld_event = {}
    canonical = _clean_url(urljoin(hit.url, parser.canonical)) if parser.canonical else _clean_url(hit.url)

    title = _first_nonempty(
        _string_value(jsonld_event.get("name")) if jsonld_event else "",
        h1_text,
        parser.meta.get("og:title", ""),
        document_title,
        hit.title,
    )

    event_context = _event_context(page_text, h1_text or title)
    evidence_text = _clean_text(
        " ".join(
            [
                h1_text,
                title,
                parser.meta.get("description", ""),
                parser.meta.get("og:description", ""),
                event_context,
            ]
        )
    )
    combined_text = _clean_text(" ".join([hit.title, hit.snippet, evidence_text]))
    lower = evidence_text.casefold()
    # Generic listing/archive pages remain listings even when a sitewide
    # exhibition Event object is embedded in their shared page template.
    event_specific = _is_event_specific_page(
        h1_text=h1_text,
        document_title=document_title,
        canonical=canonical,
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
        # Only inspect the event-specific content window. Sitewide headers often
        # carry an unrelated conference date that must never become a webinar date.
        start_at, end_at = _parse_text_datetime(event_context, now)

    mode = _extract_mode(jsonld_event, evidence_text, country)
    if not location:
        location = _extract_location_text(evidence_text, mode)
    if not country and mode == "onsite_thailand":
        country = "TH"

    free_status, free_evidence = _extract_free_status(jsonld_event, evidence_text)
    certificate_status, certificate_evidence = _extract_certificate_status(evidence_text)
    registration_closed = any(term in lower for term in CLOSED_TERMS) or _schema_registration_closed(jsonld_event, now)
    language = _detect_language(combined_text, hit.language_hint)
    organizer = _extract_organizer(jsonld_event)
    registration_url = _registration_url(jsonld_event, parser.anchors, hit.url, canonical)

    medical_relevance = any(term in lower for term in MEDICAL_TERMS)
    event_relevance = event_specific and any(term in lower for term in EVENT_TERMS)

    evidence: list[str] = []
    if jsonld_event:
        evidence.append("schema.org Event metadata")
    if not event_specific:
        evidence.append("Rejected generic event index/archive page")
    if free_evidence:
        evidence.append(free_evidence)
    if certificate_evidence:
        evidence.append(certificate_evidence)

    confidence = sum(
        [
            3 if jsonld_event else 0,
            2 if event_specific else 0,
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


def _event_context(page_text: str, heading: str, before: int = 300, after: int = 6500) -> str:
    """Return a bounded visible-text window around the event heading.

    Choosing the last heading occurrence avoids image-alt duplicates that often
    appear immediately before the true H1. The bounded prefix excludes global
    masthead dates, while the suffix retains event details and registration notes.
    """
    if not page_text or not heading:
        return page_text[:after]
    folded_page = page_text.casefold()
    folded_heading = heading.casefold()
    index = folded_page.rfind(folded_heading)
    if index < 0:
        return page_text[:after]
    return page_text[max(0, index - before) : min(len(page_text), index + after)]


def _is_event_specific_page(*, h1_text: str, document_title: str, canonical: str) -> bool:
    labels = [h1_text, document_title.rsplit("|", 1)[-1] if document_title else ""]
    normalized = {_normalize_page_label(value) for value in labels if value}
    if normalized & _GENERIC_PAGE_LABELS:
        return False

    path_parts = [part.casefold() for part in urlsplit(canonical).path.split("/") if part]
    if path_parts and path_parts[-1] in _GENERIC_PATH_PARTS:
        # A descriptive topic heading can rescue a route such as /events/free,
        # but a blank or generic heading remains an index page.
        descriptive = [value for value in normalized if value and value not in _GENERIC_PAGE_LABELS]
        if not descriptive or all(len(value) < 18 for value in descriptive):
            return False
    return True


def _jsonld_matches_heading(event: dict[str, object], heading: str) -> bool:
    name = _string_value(event.get("name"))
    if not name or not heading:
        return True
    normalized_name = _normalize_page_label(name)
    normalized_heading = _normalize_page_label(heading)
    if not normalized_name or not normalized_heading:
        return True
    if normalized_name in normalized_heading or normalized_heading in normalized_name:
        return True
    name_tokens = set(normalized_name.split())
    heading_tokens = set(normalized_heading.split())
    if not name_tokens or not heading_tokens:
        return False
    overlap = len(name_tokens & heading_tokens) / max(1, min(len(name_tokens), len(heading_tokens)))
    return overlap >= 0.7


def _normalize_page_label(value: str) -> str:
    value = value.casefold().replace("‐", "-").replace("‑", "-").replace("–", "-").replace("—", "-")
    value = re.sub(r"[^\w\u0e00-\u0e7f\u3040-\u30ff\u4e00-\u9fff]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())
