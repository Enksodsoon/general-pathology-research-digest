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
    lines.extend(_paper_section_lines("Top pathology", sections.get("Top pathology", []), limit=3))
    lines.append("")
    lines.extend(_paper_section_lines("GP-useful highlight", sections.get("GP-useful", []), limit=1))
    lines.append("")
    lines.extend(_paper_section_lines("Preprint highlight", sections.get("Preprints", []), limit=1))
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


def _extract_sections(markdown: str) -> dict[str, list[dict[str, str]]]:
    sections: dict[str, list[dict[str, str]]] = {}
    current = ""
    current_paper: dict[str, str] | None = None
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_paper = None
            current = SECTION_HEADINGS.get(line.removeprefix("## ").strip(), "")
            if current:
                sections.setdefault(current, [])
            continue
        if current and line.startswith("### "):
            title = line.removeprefix("### ").strip()
            parts = title.split(". ", 1)
            current_paper = {"title": parts[1] if len(parts) == 2 and parts[0].isdigit() else title}
            sections[current].append(current_paper)
            continue
        if current and current_paper is not None:
            _capture_field(current_paper, line)
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


def _paper_section_lines(label: str, papers: list[dict[str, str]], limit: int) -> list[str]:
    lines = [f"{label}:"]
    if not papers:
        return lines + ["No items met the threshold today."]
    for idx, paper in enumerate(papers[:limit], 1):
        title = paper.get("title", "Untitled")
        journal = paper.get("Journal", "")
        source = paper.get("Source", "")
        score = paper.get("Score", "")
        takeaway = _shorten(paper.get("Takeaway", ""), 420)
        link = paper.get("Link", "")
        lines.append(f"{idx}. {title}")
        meta = " | ".join(part for part in [journal, source, f"Score {score}" if score else ""] if part)
        if meta:
            lines.append(meta)
        if takeaway:
            lines.append(f"Takeaway: {takeaway}")
        if link:
            lines.append(f"Link: {link}")
        lines.append("")
    return lines


def _capture_field(paper: dict[str, str], line: str) -> None:
    if not line.startswith("**") or ":**" not in line:
        return
    label_part, value = line.split(":**", 1)
    label = label_part.removeprefix("**").strip()
    paper[label] = value.strip()


def _first_value(markdown: str, prefix: str) -> str:
    for line in markdown.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...continued in digest"


def _shorten(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


if __name__ == "__main__":
    raise SystemExit(main())
