from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .constants import EN_MONTHS, THAI_MONTHS, TZ_OFFSETS

def _parse_text_datetime(text: str, now: datetime) -> tuple[datetime | None, datetime | None]:
    normalized = _translate_thai_digits(text)
    parsed = _parse_thai_datetime(normalized)
    if parsed[0] is not None:
        return parsed
    parsed = _parse_japanese_datetime(normalized)
    if parsed[0] is not None:
        return parsed
    parsed = _parse_english_datetime(normalized)
    if parsed[0] is not None:
        return parsed
    return _parse_numeric_datetime(normalized, now)


def _parse_thai_datetime(text: str) -> tuple[datetime | None, datetime | None]:
    month_pattern = "|".join(sorted((re.escape(key) for key in THAI_MONTHS), key=len, reverse=True))
    match = re.search(
        rf"(?:วันที่\s*)?(\d{{1,2}})\s*({month_pattern})\s*(\d{{2,4}}).*?(?:เวลา\s*)?(\d{{1,2}})[.:](\d{{2}})\s*(?:-|–|—|ถึง)\s*(\d{{1,2}})[.:](\d{{2}})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None, None
    day, month_name, year, sh, sm, eh, em = match.groups()
    year_value = _thai_year(int(year))
    tz = timezone(timedelta(hours=7))
    start = datetime(year_value, THAI_MONTHS[month_name], int(day), int(sh), int(sm), tzinfo=tz)
    end = datetime(year_value, THAI_MONTHS[month_name], int(day), int(eh), int(em), tzinfo=tz)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def _parse_japanese_datetime(text: str) -> tuple[datetime | None, datetime | None]:
    match = re.search(
        r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日.*?(\d{1,2}):(\d{2})\s*(?:〜|～|-|–|—)\s*(\d{1,2}):(\d{2})",
        text,
    )
    if not match:
        return None, None
    year, month, day, sh, sm, eh, em = map(int, match.groups())
    tz = timezone(timedelta(hours=9)) if "JST" in text.upper() or "日本時間" in text else timezone(timedelta(hours=9))
    start = datetime(year, month, day, sh, sm, tzinfo=tz)
    end = datetime(year, month, day, eh, em, tzinfo=tz)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def _parse_english_datetime(text: str) -> tuple[datetime | None, datetime | None]:
    month_pattern = "|".join(EN_MONTHS)
    match = re.search(
        rf"\b({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}}).*?(\d{{1,2}})(?::(\d{{2}}))?\s*(AM|PM)?(?:\s*(?:-|–|—|to)\s*(\d{{1,2}})(?::(\d{{2}}))?\s*(AM|PM)?)?\s*(UTC|GMT|ICT|JST|BST|CET|CEST|EST|EDT|CST|CDT|MST|MDT|PST|PDT)?",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(
            rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})[,]?\s+(20\d{{2}}).*?(\d{{1,2}})(?::(\d{{2}}))?\s*(AM|PM)?(?:\s*(?:-|–|—|to)\s*(\d{{1,2}})(?::(\d{{2}}))?\s*(AM|PM)?)?\s*(UTC|GMT|ICT|JST|BST|CET|CEST|EST|EDT|CST|CDT|MST|MDT|PST|PDT)?",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None, None
        day, month_name, year, sh, sm, sap, eh, em, eap, tz_name = match.groups()
    else:
        month_name, day, year, sh, sm, sap, eh, em, eap, tz_name = match.groups()
    tz = TZ_OFFSETS.get((tz_name or "").upper(), timezone.utc)
    start_ap = sap or (eap if eh else None)
    start_hour = _hour_24(int(sh), start_ap)
    start = datetime(int(year), EN_MONTHS[month_name.casefold()], int(day), start_hour, int(sm or 0), tzinfo=tz)
    end = None
    if eh:
        end_ap = eap or sap
        end = datetime(int(year), EN_MONTHS[month_name.casefold()], int(day), _hour_24(int(eh), end_ap), int(em or 0), tzinfo=tz)
        if end <= start:
            end += timedelta(days=1)
    return start, end


def _parse_numeric_datetime(text: str, now: datetime) -> tuple[datetime | None, datetime | None]:
    match = re.search(
        r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2}).*?(\d{1,2}):(\d{2})(?:\s*(?:-|–|—|to)\s*(\d{1,2}):(\d{2}))?\s*(UTC|GMT|ICT|JST|BST|CET|CEST)?",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None, None
    year, month, day, sh, sm, eh, em, tz_name = match.groups()
    tz = TZ_OFFSETS.get((tz_name or "").upper(), now.tzinfo or timezone.utc)
    start = datetime(int(year), int(month), int(day), int(sh), int(sm), tzinfo=tz)
    end = None
    if eh:
        end = datetime(int(year), int(month), int(day), int(eh), int(em), tzinfo=tz)
        if end <= start:
            end += timedelta(days=1)
    return start, end


def _parse_iso_datetime(value: str, default_tz: timezone = timezone.utc) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed


def _thai_year(year: int) -> int:
    if year < 100:
        year += 2500
    return year - 543 if year >= 2400 else year


def _hour_24(hour: int, ampm: str | None) -> int:
    if not ampm:
        return hour
    marker = ampm.upper()
    if marker == "AM":
        return 0 if hour == 12 else hour
    return 12 if hour == 12 else hour + 12


def _translate_thai_digits(text: str) -> str:
    return text.translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789"))
