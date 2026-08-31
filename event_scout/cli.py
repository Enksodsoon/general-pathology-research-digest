from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .outputs import render_report, write_outputs
from .pipeline import run_scan


BANGKOK = ZoneInfo("Asia/Bangkok")


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover free medical events in English, Thai, and Japanese")
    parser.add_argument("--live", action="store_true", help="Run the live web sweep")
    parser.add_argument("--date", default="", help="Output date in YYYY-MM-DD (Bangkok time)")
    parser.add_argument("--config", default="config/event_queries.json")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    if not args.live:
        parser.error("--live is required")

    root = Path(args.root).resolve()
    config = json.loads((root / args.config).read_text(encoding="utf-8"))
    state_path = root / "data" / "event_scout_state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    else:
        state = {}

    now = datetime.now(BANGKOK)
    date_value = args.date or now.date().isoformat()
    result = run_scan(config, now=now, state=state)
    report = render_report(
        date_value=date_value,
        accepted=result.accepted,
        new_events=result.new_events,
        scanned_hits=result.scanned_hits,
        fetched_pages=result.fetched_pages,
        rejected_count=result.rejected_count,
        diagnostics=result.diagnostics,
    )
    write_outputs(
        root=root,
        date_value=date_value,
        report=report,
        accepted=result.accepted,
        new_events=result.new_events,
        state=result.state,
        diagnostics=result.diagnostics,
    )
    print(
        f"Medical event scan complete: {result.scanned_hits} hits, "
        f"{len(result.accepted)} eligible, {len(result.new_events)} new alerts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
