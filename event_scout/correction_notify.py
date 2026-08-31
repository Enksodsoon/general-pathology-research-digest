from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from .telegram_notify import send_telegram_message


BANGKOK = ZoneInfo("Asia/Bangkok")
Sender = Callable[[str, str, str], dict]


def send_pending_correction(
    *,
    correction_path: Path,
    state_path: Path,
    bot_token: str,
    chat_id: str,
    now: datetime,
    sender: Sender = send_telegram_message,
) -> int:
    correction = _load_json(correction_path, {})
    if not isinstance(correction, dict) or not correction.get("pending"):
        return 0

    text = str(correction.get("text", "")).strip()
    if not text:
        raise RuntimeError("Pending correction has no message text")
    response = sender(bot_token, chat_id, text)
    if not response.get("ok"):
        description = response.get("description") or str(response)
        raise RuntimeError(f"Telegram correction failed: {description}")

    receipt = correction.get("event_receipt")
    if isinstance(receipt, dict) and receipt.get("event_key"):
        state = _load_json(state_path, {})
        if not isinstance(state, dict):
            state = {}
        state[str(receipt["event_key"])] = {
            "title": str(receipt.get("title", "")),
            "url": str(receipt.get("url", "")),
            "event_start": receipt.get("event_start"),
            "notified_at": now.isoformat(),
            "notification_kind": "correction",
        }
        _write_json(state_path, state)

    correction["pending"] = False
    correction["sent_at"] = now.isoformat()
    _write_json(correction_path, correction)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one pending Medical Event Radar correction")
    parser.add_argument("--file", default="data/event_scout_correction.json")
    parser.add_argument("--state", default="data/event_scout_state.json")
    args = parser.parse_args()

    correction_path = Path(args.file)
    correction = _load_json(correction_path, {})
    if not isinstance(correction, dict) or not correction.get("pending"):
        print("No pending event correction.")
        return 0

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        raise SystemExit("Telegram secrets are required while an event correction is pending.")

    try:
        sent = send_pending_correction(
            correction_path=correction_path,
            state_path=Path(args.state),
            bot_token=bot_token,
            chat_id=chat_id,
            now=datetime.now(BANGKOK),
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Sent {sent} Medical Event Radar correction.")
    return 0


def _load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
