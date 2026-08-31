from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit

from .constants import CERT_TERMS, FREE_TERMS, ONLINE_TERMS, REGISTER_ANCHOR_TERMS, THAILAND_TERMS
from .dateparse import _parse_iso_datetime
from .text_utils import _clean_url, _country_code, _string_value

def _choose_jsonld_event(scripts: Iterable[str], now: datetime) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for script in scripts:
        try:
            data = json.loads(script)
        except json.JSONDecodeError:
            continue
        for node in _walk_json(data):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if any(str(value).casefold().endswith("event") for value in types if value):
                candidates.append(node)
    if not candidates:
        return {}

    def sort_key(node: dict[str, Any]) -> tuple[int, datetime]:
        dt = _parse_iso_datetime(_string_value(node.get("startDate")))
        if dt is None:
            return (2, datetime.max.replace(tzinfo=timezone.utc))
        dt_utc = dt.astimezone(timezone.utc)
        return (0 if dt_utc >= now.astimezone(timezone.utc) else 1, dt_utc)

    return sorted(candidates, key=sort_key)[0]


def _walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if graph is not None:
            yield from _walk_json(graph)
        for key, child in value.items():
            if key == "@graph":
                continue
            if isinstance(child, (dict, list)):
                yield from _walk_json(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _extract_location(event: dict[str, Any]) -> tuple[str, str]:
    if not event:
        return "", ""
    location = event.get("location")
    if isinstance(location, list):
        location = location[0] if location else {}
    if not isinstance(location, dict):
        return _string_value(location), ""
    if "virtual" in _string_value(location.get("@type")).casefold():
        return "Online", ""
    name = _string_value(location.get("name"))
    address = location.get("address")
    country = ""
    parts = [name]
    if isinstance(address, dict):
        for key in ("streetAddress", "addressLocality", "addressRegion"):
            value = _string_value(address.get(key))
            if value and value not in parts:
                parts.append(value)
        country = _country_code(_string_value(address.get("addressCountry")))
        country_text = _string_value(address.get("addressCountry"))
        if country_text and country_text not in parts:
            parts.append(country_text)
    elif address:
        parts.append(_string_value(address))
    return ", ".join(part for part in parts if part), country


def _extract_mode(event: dict[str, Any], text: str, country: str) -> str:
    lower = text.casefold()
    attendance = _string_value(event.get("eventAttendanceMode")) if event else ""
    attendance_lower = attendance.casefold()
    is_online = "online" in attendance_lower or any(term in lower for term in ONLINE_TERMS)
    is_offline = "offline" in attendance_lower
    is_thailand = country == "TH" or any(term in lower for term in THAILAND_TERMS)
    if is_online and (is_offline or is_thailand and any(word in lower for word in ("hybrid", "onsite", "on-site", "ณ "))):
        return "hybrid_thailand" if is_thailand else "online"
    if is_online:
        return "online"
    if is_thailand:
        return "onsite_thailand"
    if is_offline or country:
        return "onsite_other"
    return "unknown"


def _extract_free_status(event: dict[str, Any], text: str) -> tuple[str, str]:
    prices: list[float] = []
    if event:
        accessible = event.get("isAccessibleForFree")
        if accessible is True or str(accessible).casefold() == "true":
            return "confirmed", "Schema metadata states the event is free"
        offers = event.get("offers")
        if not isinstance(offers, list):
            offers = [offers] if offers else []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            price = offer.get("price")
            if price is None:
                continue
            try:
                prices.append(float(str(price).replace(",", "").strip()))
            except ValueError:
                continue
        if any(price > 0 for price in prices) and not any(price == 0 for price in prices):
            return "paid", "Schema metadata lists a non-zero price"
        if any(price == 0 for price in prices):
            return "confirmed", "Schema metadata lists price 0"

    lower = text.casefold()
    paid_patterns = (
        r"registration fee.{0,45}?(?:usd|thb|jpy|\$|฿|¥)?\s*[1-9]\d*(?:[.,]\d+)?",
        r"(?:usd|thb|jpy|\$|฿|¥)\s*[1-9]\d*(?:[.,]\d+)?",
        r"ค่าลงทะเบียน.{0,45}?[1-9๐-๙][\d๐-๙,]*\s*บาท",
        r"参加費.{0,30}?[1-9]\d*[,.]?\d*\s*円",
        r"受講料.{0,30}?[1-9]\d*[,.]?\d*\s*円",
    )
    conditional_patterns = (
        r"free\s+(?:only\s+)?for\s+(?:members?|students?|residents?|employees?)",
        r"members?\s+(?:attend\s+)?free",
        r"เฉพาะสมาชิก.*?ฟรี|ฟรี.*?เฉพาะสมาชิก",
        r"会員(?:のみ)?無料|無料(?:は)?会員(?:のみ)",
    )
    negative_patterns = (
        r"not\s+free", r"no\s+free\s+registration", r"free\s+(?:trial|preview)(?:\s+only)?",
        r"ไม่ฟรี", r"無料ではありません",
    )
    has_paid = any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in paid_patterns)
    has_conditional = any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in conditional_patterns)
    has_negative = any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in negative_patterns)
    strong_free_terms = tuple(
        term for term in FREE_TERMS if term not in {"ฟรี", "無料", "complimentary"}
    )
    free_event_patterns = (
        r"\bfree\s+(?:online\s+)?(?:(?:medical|clinical|healthcare|health)\s+)?(?:webinar|seminar|conference|meeting|workshop|event|training|course)\b(?!\s+(?:brochure|programme|program|book|booklet|materials?|video|recording|preview|trial|download|guide))",
        r"\b(?:webinar|seminar|conference|meeting|workshop|event|training|course)\s+(?:attendance\s+)?(?:is\s+)?free\b",
        r"\b(?:registration|attendance|admission|entry|participation)\s+(?:is\s+)?free\b",
        r"\bfree\s+to\s+attend\b|\bno\s+(?:registration\s+)?fee\b",
        r"(?:เข้าร่วม|ลงทะเบียน|สมัคร|รับชม|ชม|เข้าอบรม|เข้าประชุม)(?:งาน|กิจกรรม)?\s*(?:ได้)?\s*ฟรี",
        r"ฟรี\s*(?:สำหรับ)?\s*(?:การเข้าร่วม|เข้าร่วม|ลงทะเบียน|สมัคร|รับชม|อบรม|สัมมนา|ประชุม)",
        r"(?:ไม่มี|ไม่เสีย)\s*ค่า(?:ใช้จ่าย|ลงทะเบียน|สมัคร)",
        r"(?:参加費|受講料|入場料)\s*無料",
        r"無料\s*(?:参加|受講|聴講|視聴|ウェビナー|セミナー|イベント)",
    )
    has_free = any(term in lower for term in strong_free_terms) or any(
        re.search(pattern, lower, flags=re.IGNORECASE) for pattern in free_event_patterns
    )
    if has_conditional:
        return "conditional", "Free attendance is restricted to a subgroup"
    if has_negative:
        return "paid" if has_paid else "unknown", "Page does not state generally free attendance"
    if has_paid:
        return "paid", "Page text states a registration fee"
    if has_free:
        matched = next((term for term in FREE_TERMS if term in lower), "free event")
        return "confirmed", f"Page states '{matched}'"
    return "unknown", ""


def _extract_certificate_status(text: str) -> tuple[str, str]:
    lower = text.casefold()
    negative_patterns = (
        r"no\s+(?:attendance\s+|completion\s+)?certificate",
        r"certificate\s+(?:is\s+)?not\s+(?:available|provided|issued)",
        r"without\s+(?:an\s+)?attendance\s+certificate",
        r"ไม่มี(?:การออก)?(?:เกียรติบัตร|ใบรับรอง|ประกาศนียบัตร)",
        r"(?:受講証明書|参加証|修了証)(?:は)?(?:発行|提供)しません",
    )
    if any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in negative_patterns):
        return "unknown", ""
    cme_patterns = (
        r"\b(?:cme|cpd)\s+(?:credit|credits|point|points|hour|hours)\b",
        r"\b(?:accredited|approved)\s+for\s+\d+(?:\.\d+)?\s+(?:cme|cpd)",
        r"คะแนน\s*(?:cme|cpd)",
        r"認定単位",
    )
    if any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in cme_patterns):
        return "cme_cpd", "Page states CME/CPD credit or accredited units"
    for term in CERT_TERMS:
        if term in lower:
            return "confirmed", f"Page states '{term}'"
    return "unknown", ""


def _schema_registration_closed(event: dict[str, Any], now: datetime) -> bool:
    if not event:
        return False
    offers = event.get("offers")
    offers = offers if isinstance(offers, list) else [offers] if offers else []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        availability = _string_value(offer.get("availability")).casefold()
        valid_through = _string_value(offer.get("validThrough"))
        if any(marker in availability for marker in ("soldout", "discontinued", "outofstock")):
            return True
        if valid_through:
            parsed = _parse_iso_datetime(valid_through)
            if parsed and parsed.astimezone(timezone.utc) < now.astimezone(timezone.utc):
                return True
    return False


def _extract_organizer(event: dict[str, Any]) -> str:
    if not event:
        return ""
    organizer = event.get("organizer")
    if isinstance(organizer, list):
        organizer = organizer[0] if organizer else ""
    if isinstance(organizer, dict):
        return _string_value(organizer.get("name"))
    return _string_value(organizer)


def _registration_url(
    event: dict[str, Any], anchors: list[tuple[str, str]], base_url: str, canonical: str
) -> str:
    if event:
        offers = event.get("offers")
        if not isinstance(offers, list):
            offers = [offers] if offers else []
        for offer in offers:
            if isinstance(offer, dict):
                url = _string_value(offer.get("url"))
                if url:
                    return _clean_url(urljoin(base_url, url))
        event_url = _string_value(event.get("url"))
        if event_url:
            return _clean_url(urljoin(base_url, event_url))
        location = event.get("location")
        locations = location if isinstance(location, list) else [location]
        for item in locations:
            if isinstance(item, dict) and "virtual" in _string_value(item.get("@type")).casefold():
                url = _string_value(item.get("url"))
                if url:
                    return _clean_url(urljoin(base_url, url))

    ranked: list[tuple[int, str]] = []
    for href, text in anchors:
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        lower_text = text.casefold()
        score = sum(2 for term in REGISTER_ANCHOR_TERMS if term in lower_text)
        absolute = _clean_url(urljoin(base_url, href))
        host = urlsplit(absolute).netloc.casefold()
        if any(domain in host for domain in ("eventbrite", "peatix", "connpass", "medall", "zoom", "forms.gle", "google.com")):
            score += 1
        if score:
            ranked.append((score, absolute))
    if ranked:
        ranked.sort(key=lambda item: (-item[0], len(item[1])))
        return ranked[0][1]
    return canonical or _clean_url(base_url)
