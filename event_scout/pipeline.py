from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

from .models import HttpResponse, MedicalEvent, ScanResult, SearchHit
from .parsing import parse_event_page
from .rules import evaluate_event
from .sources import Fetch, collect_search_hits, default_fetch, hit_priority, is_safe_public_url


CERT_ORDER = {"cme_cpd": 3, "confirmed": 2, "unknown": 0}
MODE_ORDER = {"hybrid_thailand": 3, "onsite_thailand": 2, "online": 1}




def find_new_events(
    events: list[MedicalEvent],
    state: dict[str, Any],
    limit: int | None = None,
) -> list[MedicalEvent]:
    new_events: list[MedicalEvent] = []
    for event in events:
        if event.key() in state:
            continue
        if limit is not None and len(new_events) >= limit:
            break
        new_events.append(event)
    return new_events


def mark_notified_event(state: dict[str, Any], event: MedicalEvent, now: datetime) -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    new_state[event.key()] = {
        "title": event.title,
        "url": event.registration_url,
        "event_start": event.start_at.isoformat() if event.start_at else None,
        "notified_at": now.isoformat(),
    }
    return new_state


def select_new_events(
    events: list[MedicalEvent],
    state: dict[str, Any],
    now: datetime,
    limit: int | None = None,
) -> tuple[list[MedicalEvent], dict[str, Any]]:
    new_state = copy.deepcopy(state)
    new_events: list[MedicalEvent] = []
    cutoff = now.astimezone(timezone.utc) - timedelta(days=550)

    for key, record in list(new_state.items()):
        event_start = record.get("event_start") if isinstance(record, dict) else None
        try:
            parsed = datetime.fromisoformat(event_start) if event_start else None
        except (TypeError, ValueError):
            parsed = None
        if parsed and parsed.astimezone(timezone.utc) < cutoff:
            new_state.pop(key, None)

    new_events = find_new_events(events, new_state, limit=limit)
    for event in new_events:
        new_state = mark_notified_event(new_state, event, now)
    return new_events, new_state


def deduplicate_events(events: list[MedicalEvent]) -> list[MedicalEvent]:
    merged: dict[str, MedicalEvent] = {}
    for event in events:
        key = event.key()
        if key not in merged:
            item = copy.deepcopy(event)
            item.evidence_sources = sorted(set(item.evidence_sources or [item.source]))
            merged[key] = item
            continue
        merged[key] = _merge_two_events(merged[key], event)
    return list(merged.values())


def run_scan(
    config: dict[str, Any],
    *,
    now: datetime,
    fetch: Fetch = default_fetch,
    state: dict[str, Any] | None = None,
) -> ScanResult:
    settings = config.get("settings", {}) if isinstance(config.get("settings"), dict) else {}
    max_pages = int(settings.get("max_candidate_pages", 100))
    max_notifications = int(settings.get("max_notifications", 20))
    lookahead_days = int(settings.get("lookahead_days", 370))

    hits, diagnostics = collect_search_hits(config, fetch)
    ranked_hits = sorted(hits, key=lambda item: (-hit_priority(item), item.url))[:max_pages]
    accepted_raw: list[MedicalEvent] = []
    rejected_count = 0
    fetched_pages = 0

    for hit in ranked_hits:
        if not is_safe_public_url(hit.url):
            rejected_count += 1
            continue
        try:
            response = fetch(hit.url)
            fetched_pages += 1
            if not _looks_like_parseable_page(response):
                rejected_count += 1
                diagnostics.append(
                    {
                        "source": "page_fetch",
                        "query_id": hit.query_id,
                        "status": "skipped",
                        "url": hit.url,
                        "error": f"unsupported-content-type:{response.content_type}",
                    }
                )
                continue
            final_url = response.final_url or hit.url
            final_hit = SearchHit(
                title=hit.title,
                url=final_url,
                snippet=hit.snippet,
                source=hit.source,
                query_id=hit.query_id,
                language_hint=hit.language_hint,
                published_at=hit.published_at,
                priority=hit.priority,
            )
            event = parse_event_page(final_hit, response.text, now=now)
            decision = evaluate_event(event, now=now, lookahead_days=lookahead_days)
            if decision.accepted:
                event.confidence = max(event.confidence, decision.score)
                accepted_raw.append(event)
            else:
                rejected_count += 1
        except Exception as exc:  # candidate isolation is intentional
            rejected_count += 1
            diagnostics.append(
                {
                    "source": "page_fetch",
                    "query_id": hit.query_id,
                    "status": "error",
                    "url": hit.url,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                }
            )

    accepted = deduplicate_events(accepted_raw)
    accepted.sort(key=_event_sort_key)
    current_state = copy.deepcopy(state or {})
    new_events = find_new_events(accepted, current_state, limit=max_notifications)

    return ScanResult(
        accepted=accepted,
        new_events=new_events,
        state=current_state,
        diagnostics=diagnostics,
        scanned_hits=len(hits),
        fetched_pages=fetched_pages,
        rejected_count=rejected_count,
    )


def _event_sort_key(event: MedicalEvent) -> tuple[int, int, int, datetime, str]:
    start = event.start_at.astimezone(timezone.utc) if event.start_at else datetime.max.replace(tzinfo=timezone.utc)
    return (
        -CERT_ORDER.get(event.certificate_status, 0),
        -MODE_ORDER.get(event.mode, 0),
        -event.confidence,
        start,
        event.title.casefold(),
    )


def _merge_two_events(left: MedicalEvent, right: MedicalEvent) -> MedicalEvent:
    left_quality = _event_quality(left)
    right_quality = _event_quality(right)
    primary = copy.deepcopy(right if right_quality > left_quality else left)
    secondary = left if primary.source == right.source and primary.registration_url == right.registration_url else right
    if primary is right:
        secondary = left

    if CERT_ORDER.get(secondary.certificate_status, 0) > CERT_ORDER.get(primary.certificate_status, 0):
        primary.certificate_status = secondary.certificate_status
        primary.certificate_evidence = secondary.certificate_evidence
    if primary.free_status != "confirmed" and secondary.free_status == "confirmed":
        primary.free_status = secondary.free_status
        primary.free_evidence = secondary.free_evidence
    if not primary.organizer and secondary.organizer:
        primary.organizer = secondary.organizer
    if not primary.location and secondary.location:
        primary.location = secondary.location
    if not primary.country and secondary.country:
        primary.country = secondary.country
    if not primary.end_at and secondary.end_at:
        primary.end_at = secondary.end_at
    if _registration_link_quality(secondary) > _registration_link_quality(primary):
        primary.registration_url = secondary.registration_url
    primary.confidence = max(primary.confidence, secondary.confidence)
    primary.evidence = sorted(set(primary.evidence + secondary.evidence))
    primary.evidence_sources = sorted(
        set((primary.evidence_sources or [primary.source]) + (secondary.evidence_sources or [secondary.source]))
    )
    return primary


def _event_quality(event: MedicalEvent) -> tuple[int, int, int, int]:
    return (
        CERT_ORDER.get(event.certificate_status, 0),
        _registration_link_quality(event),
        event.confidence,
        len(event.evidence),
    )


def _registration_link_quality(event: MedicalEvent) -> int:
    url = event.registration_url or ""
    if not url:
        return 0
    score = 1
    if url != event.source_url:
        score += 2
    parts = urlsplit(url)
    text = f"{parts.netloc}{parts.path}".casefold()
    if any(marker in text for marker in ("register", "registration", "signup", "apply", "booking", "ticket", "forms.gle", "zoom.us", "peatix", "connpass", "eventbrite", "medall")):
        score += 2
    return score


def _looks_like_parseable_page(response: HttpResponse) -> bool:
    content_type = (response.content_type or "").casefold()
    if any(marker in content_type for marker in ("html", "xml", "text/plain")):
        return True
    sample = response.text.lstrip()[:200].casefold()
    return sample.startswith(("<!doctype html", "<html", "<?xml"))
