from __future__ import annotations

import re
from typing import Any

from .schema import _extract_free_status as _base_extract_free_status


_CONTEXTUAL_FREE_PATTERNS = (
    # Event-detail pages commonly render these as adjacent badges/lines.
    r"無料\s*(?:オンライン開催|オンライン|ライブ配信|zoom|ウェビナー|セミナー)",
    r"(?:オンライン開催|オンライン|ライブ配信)\s*無料",
    r"ฟรี\s*(?:ออนไลน์|ผ่าน\s*(?:ระบบ\s*)?zoom|เว็บบินาร์|สัมมนา|ประชุม)",
    r"(?:ออนไลน์|ผ่าน\s*(?:ระบบ\s*)?zoom)\s*ฟรี",
)


def extract_free_status(event: dict[str, Any], text: str) -> tuple[str, str]:
    """Extend strict fee parsing for event-detail free/online badges.

    The base parser still wins for paid, conditional, negative, schema.org, and
    explicit free-registration wording. These extra phrases do not match free
    brochures, downloads, previews, books, or other non-attendance materials.
    """
    status, evidence = _base_extract_free_status(event, text)
    if status != "unknown":
        return status, evidence
    lower = text.casefold()
    for pattern in _CONTEXTUAL_FREE_PATTERNS:
        if re.search(pattern, lower, flags=re.IGNORECASE):
            return "confirmed", "Event detail states free online attendance"
    return status, evidence
