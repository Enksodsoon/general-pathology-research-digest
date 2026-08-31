from __future__ import annotations

import html as html_lib
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .constants import THAILAND_TERMS

def _extract_location_text(text: str, mode: str) -> str:
    if mode == "online":
        return "Online"
    if mode in {"onsite_thailand", "hybrid_thailand"}:
        for term in THAILAND_TERMS:
            if term in text.casefold():
                return term.title() if term.isascii() else term
        return "Thailand"
    return ""


def _detect_language(text: str, hint: str = "") -> str:
    thai_count = sum("\u0e00" <= char <= "\u0e7f" for char in text)
    japanese_count = sum(
        ("\u3040" <= char <= "\u30ff") or ("\u4e00" <= char <= "\u9fff") for char in text
    )
    if thai_count >= max(3, japanese_count):
        return "th"
    if japanese_count >= 3:
        return "ja"
    return hint if hint in {"en", "th", "ja"} else "en"


def _country_code(value: str) -> str:
    lower = value.casefold().strip()
    if lower in {"th", "tha", "thailand", "ประเทศไทย"}:
        return "TH"
    if lower in {"jp", "jpn", "japan", "日本"}:
        return "JP"
    if len(value.strip()) == 2:
        return value.strip().upper()
    return value.strip()

def _strip_html(value: str) -> str:
    return _clean_text(re.sub(r"<[^>]+>", " ", html_lib.unescape(value)))


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u00a0", " ").split())


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _first_nonempty(*values: str) -> str:
    for value in values:
        clean = _clean_text(value)
        if clean:
            return clean
    return ""


def _clean_url(value: str) -> str:
    value = html_lib.unescape((value or "").strip())
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"}:
        return value
    query_items = []
    for chunk in parts.query.split("&") if parts.query else []:
        key = chunk.split("=", 1)[0].casefold()
        if key.startswith("utm_") or key in {"fbclid", "gclid", "mc_cid", "mc_eid"}:
            continue
        query_items.append(chunk)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", "&".join(query_items), ""))
