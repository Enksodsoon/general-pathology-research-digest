from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
import time
from typing import Callable
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from .models import MedicalEvent
from .pipeline import mark_notified_event


BANGKOK = ZoneInfo("Asia/Bangkok")


def build_event_message(event: MedicalEvent) -> str:
    certificate = {
        "confirmed": "Yes",
        "cme_cpd": "CME/CPD",
        "unknown": "Not stated",
    }.get(event.certificate_status, "Not stated")
    mode = {
        "online": "Online",
        "onsite_thailand": f"Onsite — {event.location or 'Thailand'}",
        "hybrid_thailand": f"Hybrid — {event.location or 'Thailand'}",
    }.get(event.mode, event.mode.replace("_", " ").title())

    lines = ["🩺 FREE MEDICAL EVENT", event.title]
    if event.start_at:
        start = event.start_at.astimezone(BANGKOK)
        date_text = start.strftime("%d %b %Y")
        time_text = start.strftime("%H:%M")
        if event.end_at:
            end = event.end_at.astimezone(BANGKOK)
            if end.date() == start.date():
                time_text += f"–{end.strftime('%H:%M')}"
            else:
                time_text += f"–{end.strftime('%d %b %H:%M')}"
        lines.append(f"📅 {date_text}, {time_text} ICT")
    else:
        lines.append("📅 Date/time: verify on event page")
    lines.append(f"📍 {mode}")
    lines.append(f"🗣 {event.language.upper()}")
    lines.append(f"🎓 Certificate: {certificate}")
    lines.append(f"🔗 {event.registration_url}")
    return "\n".join(lines)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


Sender = Callable[[str, str, str], dict]


def notify_events(
    events: list[MedicalEvent],
    *,
    state_path: Path,
    bot_token: str,
    chat_id: str,
    now: datetime,
    sender: Sender = send_telegram_message,
    delay: float = 0.45,
) -> int:
    state = _load_state(state_path)
    sent = 0
    for index, event in enumerate(events):
        response = sender(bot_token, chat_id, build_event_message(event))
        if not response.get("ok"):
            description = response.get("description") or str(response)
            raise RuntimeError(f"Telegram send failed for {event.title}: {description}")
        state = mark_notified_event(state, event, now)
        _write_state(state_path, state)
        sent += 1
        if index + 1 < len(events):
            time.sleep(max(0.0, delay))
    return sent


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one Telegram notification per newly discovered medical event")
    parser.add_argument("--events", default="data/new_events.json")
    parser.add_argument("--delay", type=float, default=0.45)
    args = parser.parse_args()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        print("Telegram secrets missing; skipping event notifications.")
        return 0

    path = Path(args.events)
    if not path.exists():
        print("No event payload found; skipping notification.")
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    events = [MedicalEvent.from_dict(item) for item in data if isinstance(item, dict)]
    if not events:
        print("No new eligible events; no Telegram message sent.")
        return 0

    try:
        sent = notify_events(
            events,
            state_path=Path("data/event_scout_state.json"),
            bot_token=bot_token,
            chat_id=chat_id,
            now=datetime.now(BANGKOK),
            delay=args.delay,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Sent {sent} individual medical-event notifications.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
