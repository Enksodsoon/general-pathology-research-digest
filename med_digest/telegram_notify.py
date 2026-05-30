from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


SECTION_HEADINGS = {
    "Top peer-reviewed pathology papers": "Top pathology",
    "General medical / GP-useful updates": "GP-useful",
    "Preprints - not peer reviewed": "Preprints",
    "Preprints — not peer reviewed": "Preprints",
    "Additional watchlist": "Watchlist",
}


def build_message(markdown: str, digest_url: str = "") -> str:
    date_value = _first_value(markdown, "Date:") or "today"
    sections = _extract_sections(markdown)
    qa = _extract_qa(markdown)

    lines = [
        f"Daily Pathology Digest - {date_value}",
        "",
    ]
    lines.extend(_section_lines("Top pathology", sections.get("Top pathology", []), limit=3))
    lines.append("")
    gp_count = qa.get("GP-useful digest items", str(len(sections.get("GP-useful", []))))
    preprint_count = qa.get("Preprint watch items", str(len(sections.get("Preprints", []))))
    watchlist_count = qa.get("Watchlist items", str(len(sections.get("Watchlist", []))))
    lines.append(f"At a glance: GP {gp_count} | Preprints {preprint_count} | Watchlist {watchlist_count}")
    if digest_url:
        lines.append(f"Full digest: {digest_url}")
    lines.append("")
    lines.append("Research surveillance only; verify full text before changing practice.")
    return _truncate("\n".join(lines), limit=3900)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Send digest summary to Telegram")
    parser.add_argument("--digest", default="digests/latest.md")
    parser.add_argument("--url", default="")
    args = parser.parse_args()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        print("Telegram secrets missing; skipping notification.")
        return 0

    markdown = Path(args.digest).read_text(encoding="utf-8")
    message = build_message(markdown, digest_url=args.url)
    response = send_telegram_message(bot_token, chat_id, message)
    if not response.get("ok"):
        raise SystemExit(f"Telegram send failed: {response}")
    print("Telegram notification sent.")
    return 0


def _extract_sections(markdown: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current = SECTION_HEADINGS.get(line.removeprefix("## ").strip(), "")
            if current:
                sections.setdefault(current, [])
            continue
        if current and line.startswith("### "):
            title = line.removeprefix("### ").strip()
            parts = title.split(". ", 1)
            sections[current].append(parts[1] if len(parts) == 2 and parts[0].isdigit() else title)
    return sections


def _extract_qa(markdown: str) -> dict[str, str]:
    qa: dict[str, str] = {}
    in_qa = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line == "## Pipeline QA":
            in_qa = True
            continue
        if in_qa and line.startswith("## "):
            break
        if in_qa and line.startswith("- ") and ":" in line:
            key, value = line.removeprefix("- ").split(":", 1)
            qa[key.strip()] = value.strip()
    return qa


def _section_lines(label: str, titles: list[str], limit: int) -> list[str]:
    lines = [f"{label}:"]
    if not titles:
        return lines + ["No items met the threshold today."]
    for idx, title in enumerate(titles[:limit], 1):
        lines.append(f"{idx}. {title}")
    return lines


def _first_value(markdown: str, prefix: str) -> str:
    for line in markdown.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...continued in digest"


if __name__ == "__main__":
    raise SystemExit(main())
