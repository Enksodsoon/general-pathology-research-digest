from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .models import MedicalEvent


BANGKOK = ZoneInfo("Asia/Bangkok")


def render_report(
    *,
    date_value: str,
    accepted: list[MedicalEvent],
    new_events: list[MedicalEvent],
    scanned_hits: int,
    fetched_pages: int,
    rejected_count: int,
    diagnostics: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Free Medical Events — {date_value}",
        "",
        "Strict inclusion: confirmed free attendance, future date, and either online or onsite/hybrid in Thailand.",
        "Languages monitored: English, Thai, and Japanese. Certificate status is reported only when the source states it.",
        "",
        "## New alerts",
        "",
    ]
    if not new_events:
        lines.append("No newly discovered eligible events today.")
    else:
        for index, event in enumerate(new_events, 1):
            lines.extend(_event_markdown(event, index))

    lines.extend(["", "## All currently eligible events", ""])
    if not accepted:
        lines.append("No eligible future events were verified in this run.")
    else:
        for index, event in enumerate(accepted, 1):
            lines.extend(_event_markdown(event, index))

    ok_sources = sum(1 for item in diagnostics if item.get("status") == "ok")
    error_sources = sum(1 for item in diagnostics if item.get("status") == "error")
    lines.extend(
        [
            "",
            "## Scan QA",
            "",
            f"- Search hits discovered: {scanned_hits}",
            f"- Candidate pages fetched: {fetched_pages}",
            f"- Eligible unique events: {len(accepted)}",
            f"- New individual alerts: {len(new_events)}",
            f"- Rejected/failed candidates: {rejected_count}",
            f"- Source checks OK: {ok_sources}",
            f"- Source/page errors: {error_sources}",
            "",
            "Dates and availability can change. Open the exact event link before registering.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(
    *,
    root: Path,
    date_value: str,
    report: str,
    accepted: list[MedicalEvent],
    new_events: list[MedicalEvent],
    state: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> None:
    events_dir = root / "events"
    data_dir = root / "data"
    events_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    _write_text(events_dir / f"{date_value}.md", report)
    _write_text(events_dir / "latest.md", report)
    _write_json(data_dir / "new_events.json", [event.to_dict() for event in new_events])
    _write_json(data_dir / "event_scout_state.json", state)
    _write_json(data_dir / "event_scout_diagnostics.json", diagnostics)
    _write_text(data_dir / "events.csv", _events_csv(accepted))


def _event_markdown(event: MedicalEvent, index: int) -> list[str]:
    certificate = {
        "confirmed": "Yes",
        "cme_cpd": "CME/CPD credit",
        "unknown": "Not stated",
    }.get(event.certificate_status, "Not stated")
    mode = {
        "online": "Online",
        "onsite_thailand": f"Onsite — {event.location or 'Thailand'}",
        "hybrid_thailand": f"Hybrid — {event.location or 'Thailand'}",
    }.get(event.mode, event.mode.replace("_", " ").title())
    when = "Date/time not parsed"
    if event.start_at:
        start = event.start_at.astimezone(BANGKOK)
        when = start.strftime("%d %b %Y, %H:%M")
        if event.end_at:
            end = event.end_at.astimezone(BANGKOK)
            when += f"–{end.strftime('%H:%M') if end.date() == start.date() else end.strftime('%d %b %H:%M')}"
        when += " ICT"
    return [
        f"### {index}. {event.title}",
        "",
        f"- Date: {when}",
        f"- Format: {mode}",
        f"- Language: {event.language.upper()}",
        f"- Certificate: {certificate}",
        f"- Exact registration/event link: {event.registration_url}",
        f"- Found via: {', '.join(event.evidence_sources or [event.source])}",
        "",
    ]


def _events_csv(events: list[MedicalEvent]) -> str:
    output = StringIO()
    fieldnames = [
        "event_key",
        "title",
        "start_at",
        "end_at",
        "mode",
        "location",
        "language",
        "free_status",
        "certificate_status",
        "registration_url",
        "source_url",
        "organizer",
        "sources",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for event in events:
        writer.writerow(
            {
                "event_key": event.key(),
                "title": event.title,
                "start_at": event.start_at.isoformat() if event.start_at else "",
                "end_at": event.end_at.isoformat() if event.end_at else "",
                "mode": event.mode,
                "location": event.location,
                "language": event.language,
                "free_status": event.free_status,
                "certificate_status": event.certificate_status,
                "registration_url": event.registration_url,
                "source_url": event.source_url,
                "organizer": event.organizer,
                "sources": ";".join(event.evidence_sources or [event.source]),
            }
        )
    return output.getvalue()


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, value: str) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(value, encoding="utf-8")
    temp.replace(path)
