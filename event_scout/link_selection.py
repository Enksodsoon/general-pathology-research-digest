from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlsplit

from .constants import REGISTER_ANCHOR_TERMS
from .text_utils import _clean_url, _string_value


_STRONG_TEXT_TERMS = (
    "register",
    "registration",
    "sign up",
    "book now",
    "apply",
    "join event",
    "reserve",
    "ลงทะเบียน",
    "สมัคร",
    "สำรองที่นั่ง",
    "เข้าร่วม",
    "お申し込み",
    "申込み",
    "申し込み",
    "参加登録",
    "予約",
    "登録",
)

_URL_SIGNALS = (
    "/register",
    "/registration",
    "/signup",
    "/sign-up",
    "/apply",
    "/booking",
    "/ticket",
    "/rsvp",
    "forms.gle/",
    "docs.google.com/forms/",
)

_BLOCKED_URL_SIGNALS = (
    "zoom.us/test",
    "/test/",
    "/test?",
    "/download",
    "/setup",
    "/support",
    "/help",
    "/privacy",
    "/terms",
)

_PLATFORM_HOSTS = (
    "eventbrite.",
    "peatix.com",
    "connpass.com",
    "medall.org",
    "zoom.us",
    "forms.gle",
    "docs.google.com",
)


def registration_url(
    event: dict[str, Any], anchors: list[tuple[str, str]], base_url: str, canonical: str
) -> str:
    """Select a genuine registration or event URL, never a setup/test link."""
    ranked: list[tuple[int, str]] = []

    if event:
        offers = event.get("offers")
        offers = offers if isinstance(offers, list) else [offers] if offers else []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            candidate = _candidate_url(_string_value(offer.get("url")), base_url)
            if candidate:
                ranked.append((12 if _has_url_signal(candidate) else 9, candidate))

    for href, text in anchors:
        candidate = _candidate_url(href, base_url)
        if not candidate:
            continue
        lower_text = text.casefold()
        strong_matches = sum(1 for term in _STRONG_TEXT_TERMS if term in lower_text)
        weak_matches = sum(
            1 for term in REGISTER_ANCHOR_TERMS if term in lower_text and term not in _STRONG_TEXT_TERMS
        )
        url_signal = _has_url_signal(candidate)
        if not strong_matches and not url_signal and not weak_matches:
            continue
        score = strong_matches * 5 + (3 if url_signal else 0) + weak_matches
        host = urlsplit(candidate).netloc.casefold()
        if score > 0 and any(platform in host for platform in _PLATFORM_HOSTS):
            score += 2
        ranked.append((score, candidate))

    if ranked:
        ranked.sort(key=lambda item: (-item[0], len(item[1])))
        return ranked[0][1]

    if event:
        event_url = _candidate_url(_string_value(event.get("url")), base_url)
        if event_url:
            return event_url
        location = event.get("location")
        locations = location if isinstance(location, list) else [location]
        for item in locations:
            if not isinstance(item, dict) or "virtual" not in _string_value(item.get("@type")).casefold():
                continue
            candidate = _candidate_url(_string_value(item.get("url")), base_url)
            if candidate:
                return candidate

    return canonical or _clean_url(base_url)


def _candidate_url(value: str, base_url: str) -> str:
    if not value or value.startswith(("mailto:", "tel:", "javascript:", "#")):
        return ""
    candidate = _clean_url(urljoin(base_url, value))
    parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    lowered = candidate.casefold()
    if any(signal in lowered for signal in _BLOCKED_URL_SIGNALS):
        return ""
    return candidate


def _has_url_signal(url: str) -> bool:
    lowered = url.casefold()
    return any(signal in lowered for signal in _URL_SIGNALS)
