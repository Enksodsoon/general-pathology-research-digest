"""Fresh live-digest -> PubMed abstract -> visual Telegram briefing prototype.

This is deliberately a preview path: it selects a result-rich paper from the newly
created daily digest, retrieves its PubMed abstract, renders four source-grounded
panels with Pillow, and only sends when --send is explicitly supplied.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1440
NAVY = "#102B49"
TEAL = "#007F86"
BLUE = "#397CC3"
INK = "#233B50"
MUTED = "#506779"
PALE = "#EAF4F6"
WHITE = "#FFFFFF"
PAPER = "#F7FAFC"
AMBER = "#8A4A00"
CREAM = "#FFF1DF"
RED = "#9A2941"
GREEN = "#087B5B"
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def parse_digest(markdown: str) -> tuple[str, list[dict[str, str]]]:
    date_match = re.search(r"^Date:\s*(\d{4}-\d{2}-\d{2})", markdown, re.M)
    date_value = date_match.group(1) if date_match else ""
    section = re.search(
        r"## Top peer-reviewed pathology papers\s*(.*?)(?=\n## |\Z)",
        markdown,
        re.S,
    )
    if not section:
        return date_value, []

    papers: list[dict[str, str]] = []
    chunks = re.split(r"(?m)^###\s+\d+\.\s+", section.group(1))
    for chunk in chunks[1:]:
        lines = chunk.strip().splitlines()
        if not lines:
            continue
        paper: dict[str, str] = {"title": lines[0].strip()}
        for line in lines[1:]:
            m = re.match(r"\*\*(.+?):\*\*\s*(.*)", line.strip())
            if m:
                paper[m.group(1).strip().lower().replace(" ", "_")] = m.group(2).strip()
        link = paper.get("link", "")
        pmid_match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", link)
        if pmid_match:
            paper["pmid"] = pmid_match.group(1)
            paper["journal"] = paper.get("journal", "")
            papers.append(paper)
    return date_value, papers


def _sentences(text: str) -> list[str]:
    compact = " ".join((text or "").split())
    if not compact:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", compact) if s.strip()]


def select_candidate(papers: list[dict[str, str]], abstracts: dict[str, str]) -> dict[str, str]:
    if not papers:
        raise ValueError("No peer-reviewed PubMed pathology papers were found in the digest.")

    def score(paper: dict[str, str]) -> tuple[int, int]:
        abstract = abstracts.get(paper.get("pmid", ""), "")
        low = f"{paper.get('title', '')} {paper.get('study_type', '')} {abstract}".lower()
        numeric = (
            abstract.count("%") * 4
            + len(re.findall(r"\bAUC\b", abstract, re.I)) * 5
            + len(re.findall(r"\b(?:κ|kappa|rho|ρ)\b", abstract, re.I)) * 4
            + len(re.findall(r"\bp\s*[<=>]", abstract, re.I)) * 2
            + len(re.findall(r"95%\s*CI", abstract, re.I)) * 2
        )
        pathology = sum(
            3 for term in ("histolog", "biopsy", "immunohist", "ihc", "patholog", "cell", "tissue")
            if term in low
        )
        original = 8
        if "protocol" in low or "will be" in abstract.lower():
            original -= 14
        if "review" in low or "systematic review" in low:
            original -= 8
        if not abstract:
            original -= 20
        return numeric + pathology + original, -papers.index(paper)

    return max(papers, key=score)


def _find_sentence(sentences: list[str], terms: Iterable[str], fallback: str = "") -> str:
    for sentence in sentences:
        low = sentence.lower()
        if any(term.lower() in low for term in terms):
            return sentence
    return fallback


def extract_highlights(abstract: str) -> dict[str, str]:
    s = _sentences(abstract)
    background = s[0] if s else "No abstract was available."
    question = _find_sentence(s, ["we evaluated", "we assessed", "we investigated", "we developed", "objective", "aimed"], background)
    design = _find_sentence(s, ["patients", "participants", "controls", "biopsies", "cohort"], question)
    methods = _find_sentence(s, ["h&e", "immunohist", "ihc", "scored", "randomized", "cross-validation"], design)
    result_primary = next((x for x in s if "%" in x and re.search(r"\bvs\.?\b", x, re.I)), "")
    if not result_primary:
        result_primary = _find_sentence(s, ["p <", "p =", "achieved", "sensitivity", "specificity"], "No quantitative primary result extracted.")
    agreement = _find_sentence(s, ["κ", "kappa", "interobserver", "agreement"], "")
    result_secondary = _find_sentence(s, ["auc", "correlation", "spearman", "accuracy"], "")
    conclusion = _find_sentence(list(reversed(s)), ["can be", "results indicate", "provide", "suggest", "may represent"], s[-1] if s else "")
    caution = (
        "Abstract-level research evidence only. Interpret the result in the study context; "
        "it is not practice-changing guidance without full-text review, external validation, and relevant guidelines."
    )
    return {
        "background": background,
        "question": question,
        "design": design,
        "methods": methods,
        "result_primary": result_primary,
        "agreement": agreement,
        "result_secondary": result_secondary,
        "conclusion": conclusion,
        "caution": caution,
    }


def fetch_pubmed_abstract(pmid: str, api_key: str = "") -> str:
    params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
    if api_key:
        params["api_key"] = api_key
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "general-pathology-research-digest/visual-preview"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        root = ET.fromstring(resp.read())
    parts: list[str] = []
    for node in root.findall(".//Abstract/AbstractText"):
        label = node.attrib.get("Label", "").strip()
        text = "".join(node.itertext()).strip()
        if text:
            parts.append(f"{label}: {text}" if label else text)
    return " ".join(parts)


def fetch_abstracts(papers: list[dict[str, str]], max_papers: int = 6) -> dict[str, str]:
    abstracts: dict[str, str] = {}
    api_key = os.environ.get("NCBI_API_KEY", "")
    for paper in papers[:max_papers]:
        pmid = paper.get("pmid", "")
        if not pmid:
            continue
        try:
            abstracts[pmid] = fetch_pubmed_abstract(pmid, api_key=api_key)
        except Exception:
            abstracts[pmid] = ""
    return abstracts


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size)


class Card:
    def __init__(self, number: int, date_label: str, kicker: str, title: str):
        self.im = Image.new("RGB", (W, H), PAPER)
        self.d = ImageDraw.Draw(self.im)
        self.d.rectangle((0, 0, W, 16), fill=TEAL)
        self.text(56, 46, "ENK'S MEDICAL BRIEF", 30, True, NAVY)
        self.text(56, 91, f"{date_label}  •  LIVE DIGEST", 19, False, MUTED)
        self.box((914, 44, 1024, 116), PALE)
        self.text(930, 57, f"{number} / 4", 25, True, TEAL)
        self.text(56, 156, kicker.upper(), 22, True, TEAL)
        self.wrap(56, 205, title, 48, True, NAVY, width=968, line=59)
        self.d.line((56, 1352, 1024, 1352), fill="#CBDCE5", width=2)

    def text(self, x: int, y: int, text: str, size: int = 26, bold: bool = False, color: str = INK):
        self.d.text((x, y), text, font=_font(size, bold), fill=color)

    def wrap(self, x: int, y: int, text: str, size: int = 27, bold: bool = False, color: str = INK, width: int = 950, line: int | None = None, max_lines: int | None = None) -> int:
        line = line or int(size * 1.42)
        drawn = 0
        for para in (text or "").split("\n"):
            row = ""
            for word in para.split():
                nxt = f"{row} {word}".strip()
                if self.d.textlength(nxt, font=_font(size, bold)) > width and row:
                    self.text(x, y, row, size, bold, color)
                    y += line
                    drawn += 1
                    if max_lines and drawn >= max_lines:
                        return y
                    row = word
                else:
                    row = nxt
            if row:
                self.text(x, y, row, size, bold, color)
                y += line
                drawn += 1
                if max_lines and drawn >= max_lines:
                    return y
        return y

    def box(self, xy, fill=WHITE, outline=None, radius=24):
        self.d.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=2)

    def note(self, y: int, label: str, text: str, fill=PALE, color=TEAL, height: int = 170):
        self.box((56, y, 1024, y + height), fill)
        self.text(82, y + 20, label, 25, True, color)
        self.wrap(82, y + 62, text, 25, width=915, line=34, max_lines=3)

    def save(self, path: Path):
        self.im.save(path, "PNG", optimize=True)


def _date_label(date_value: str) -> str:
    try:
        y, m, d = date_value.split("-")
        months = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        return f"{int(d):02d} {months[int(m)]} {y}"
    except Exception:
        return date_value.upper()


def _human_date(date_value: str) -> str:
    try:
        y, m, d = date_value.split("-")
        months = ["", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
        return f"{int(d)} {months[int(m)]} {y}"
    except Exception:
        return date_value.upper()


def _extract_percent_pair(text: str) -> tuple[float, float] | None:
    m = re.search(r"(\d+(?:\.\d+)?)%\s+vs\.?\s+(\d+(?:\.\d+)?)%", text, re.I)
    return (float(m.group(1)), float(m.group(2))) if m else None


def _extract_auc_pair(text: str) -> tuple[float, float] | None:
    m = re.search(r"AUC\s+(\d+(?:\.\d+)?)\s+vs\.?\s+(\d+(?:\.\d+)?)", text, re.I)
    return (float(m.group(1)), float(m.group(2))) if m else None


def _short_title(title: str) -> str:
    title = title.rstrip(".")
    if len(title) <= 92:
        return title
    return title[:89].rsplit(" ", 1)[0] + "…"


def _footer(card: Card, paper: dict[str, str]):
    card.text(56, 1374, f"{paper.get('journal','PubMed')}  •  PMID {paper.get('pmid','')}", 18, False, MUTED)
    card.text(56, 1401, "Fresh source-grounded preview • Research education, not treatment advice", 16, False, MUTED)


def render_panels(out: Path, date_value: str, paper: dict[str, str], abstract: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    h = extract_highlights(abstract)
    date_label = _date_label(date_value)
    title = _short_title(paper.get("title", "Fresh pathology paper"))

    # 1 — clinical context and question
    c = Card(1, date_label, "Why this paper exists", title)
    c.note(440, "CLINICAL / PATHOLOGY CONTEXT", h["background"], WHITE, NAVY, 215)
    c.note(694, "WHAT THE AUTHORS ASKED", h["question"], PALE, TEAL, 215)
    c.box((56, 950, 1024, 1227), CREAM)
    c.text(82, 976, "READ THIS FIRST", 27, True, AMBER)
    c.wrap(82, 1026, "The visual brief is generated from today's live PubMed digest. It keeps the original study question in view before showing numbers, so the result is not detached from its clinical context.", 27, width=910, line=39, max_lines=5)
    _footer(c, paper)
    paths = [out / "01-context.png"]
    c.save(paths[-1])

    # 2 — study map
    c = Card(2, date_label, "Study map", "Who was studied, and what was compared?")
    c.note(397, "DESIGN / SAMPLE", h["design"], WHITE, NAVY, 250)
    c.note(687, "HOW THE TISSUE / TEST WAS ASSESSED", h["methods"], PALE, TEAL, 250)
    nums = re.findall(r"\b\d{1,4}\b", h["design"])
    if nums:
        c.box((56, 978, 1024, 1170), CREAM)
        c.text(82, 1002, "NUMBERS VISIBLE IN THE ABSTRACT", 25, True, AMBER)
        x = 88
        for value in nums[:4]:
            c.box((x, 1057, x + 180, 1130), WHITE, radius=16)
            c.text(x + 22, 1069, value, 35, True, NAVY)
            x += 220
    c.wrap(56, 1209, "This is an observational tissue-level comparison, not a treatment trial. The visual separates study design from interpretation.", 24, width=960, line=34, max_lines=3)
    _footer(c, paper)
    paths.append(out / "02-study.png")
    c.save(paths[-1])

    # 3 — quantitative results
    c = Card(3, date_label, "Results", "What changed, and how large was the signal?")
    pair = _extract_percent_pair(h["result_primary"])
    c.text(56, 397, "PRIMARY RESULT", 27, True, NAVY)
    if pair:
        a, b = pair
        labels = ["Study / exposed group", "Comparator / control"]
        values = [a, b]
        colors = [TEAL, BLUE]
        left, right, top = 410, 948, 500
        for i, (label, value, color) in enumerate(zip(labels, values, colors)):
            yy = top + i * 115
            c.text(56, yy + 8, label, 23, True, INK)
            c.d.rounded_rectangle((left, yy, left + (right-left)*value/100, yy + 53), radius=9, fill=color)
            c.text(left + (right-left)*value/100 + 14, yy + 5, f"{value:g}%", 27, True, color)
        c.text(56, 744, f"Difference: {a-b:+.1f} percentage points", 29, True, TEAL)
    else:
        c.note(475, "QUANTITATIVE FINDING", h["result_primary"], PALE, TEAL, 260)
    c.wrap(56, 812, h["result_primary"], 24, width=960, line=34, max_lines=4)

    auc_pair = _extract_auc_pair(h["result_secondary"])
    c.box((56, 981, 1024, 1180), PALE)
    c.text(82, 1003, "SECONDARY SIGNAL", 25, True, TEAL)
    if auc_pair:
        c.text(82, 1052, f"AUC {auc_pair[0]:.3f}  vs  {auc_pair[1]:.3f}", 40, True, NAVY)
        c.wrap(82, 1110, h["result_secondary"], 22, width=910, line=31, max_lines=2)
    else:
        c.wrap(82, 1052, h["result_secondary"] or h["agreement"], 24, width=910, line=34, max_lines=3)
    if h["agreement"]:
        c.wrap(56, 1215, "Agreement: " + h["agreement"], 22, width=960, line=31, max_lines=3)
    _footer(c, paper)
    paths.append(out / "03-results.png")
    c.save(paths[-1])

    # 4 — interpretation
    c = Card(4, date_label, "Interpretation", "What should you actually remember?")
    c.note(397, "WHAT THE PAPER SUPPORTS", h["conclusion"], PALE, GREEN, 240)
    c.note(677, "WHAT NOT TO OVERCLAIM", h["caution"], "#F8E9EC", RED, 245)
    c.box((56, 965, 1024, 1216), CREAM)
    c.text(82, 988, "WHY THIS WAS SELECTED TODAY", 25, True, AMBER)
    c.wrap(82, 1038, "The live selector favors peer-reviewed pathology papers with interpretable study design and quantitative results, while penalizing protocols and reviews when an original result-rich study is available.", 26, width=910, line=37, max_lines=5)
    c.text(56, 1257, "SOURCE LEVEL: PubMed abstract • Full text not assumed", 22, True, TEAL)
    _footer(c, paper)
    paths.append(out / "04-interpretation.png")
    c.save(paths[-1])
    return paths


def build_caption(date_value: str, paper: dict[str, str], abstract: str) -> str:
    h = extract_highlights(abstract)
    title = html.escape(paper.get("title", "Fresh pathology paper"))
    journal = html.escape(paper.get("journal", "PubMed"))
    pmid = paper.get("pmid", "")
    result = html.escape(h["result_primary"])
    return (
        f"<b>ENK'S MEDICAL BRIEF — LIVE {_human_date(date_value)} DIGEST</b>\n"
        f"Fresh end-to-end test: live digest → PubMed abstract → automatic selection → four visual panels → Telegram.\n\n"
        f"<b>{title}</b>\n"
        f"{journal} • PMID {pmid}\n\n"
        f"<b>Key result:</b> {result}\n\n"
        "Open the four panels in order: context → study → results → interpretation.\n"
        "Abstract-level research surveillance only; this is <b>not practice-changing</b> without full-text review and relevant guidance.\n\n"
        f"<a href=\"https://pubmed.ncbi.nlm.nih.gov/{pmid}/\">Open PubMed source</a>"
    )


def make_payload(chat_id: str, paths: list[Path], caption: str) -> tuple[bytes, str]:
    if len(paths) != 4:
        raise ValueError("Exactly four panels are required")
    boundary = "----freshmedicalbrief" + uuid.uuid4().hex
    chunks: list[bytes] = []

    def field(name: str, value: bytes, filename: str | None = None):
        chunks.append(f"--{boundary}\r\n".encode())
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'
        chunks.append((disposition + "\r\n").encode())
        if filename:
            chunks.append(b"Content-Type: image/png\r\n")
        chunks.append(b"\r\n" + value + b"\r\n")

    media = [{"type": "photo", "media": f"attach://panel{i}"} for i in range(4)]
    media[0].update(caption=caption, parse_mode="HTML")
    field("chat_id", chat_id.encode())
    field("media", json.dumps(media, ensure_ascii=False).encode())
    for i, path in enumerate(paths):
        field(f"panel{i}", path.read_bytes(), path.name)
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def validate_response(response: dict, chat_id: str) -> dict:
    result = response.get("result")
    if response.get("ok") is not True or not isinstance(result, list) or len(result) != 4:
        raise RuntimeError("Telegram did not confirm acceptance of all four images; do not automatically retry.")
    group_ids = {r.get("media_group_id") for r in result}
    if len(group_ids) != 1 or not next(iter(group_ids)):
        raise RuntimeError("Telegram album grouping was not confirmed.")
    for item in result:
        if "message_id" not in item or str(item.get("chat", {}).get("id")) != chat_id.strip():
            raise RuntimeError("Telegram recipient or message confirmation did not match.")
    return {
        "telegram_ok": True,
        "accepted_images": 4,
        "recipient_matches": True,
        "message_ids": [r["message_id"] for r in result],
    }


def send_album(token: str, chat_id: str, paths: list[Path], caption: str) -> dict:
    if not token or not chat_id:
        raise RuntimeError("Required Telegram repository secrets are missing.")
    body, content_type = make_payload(chat_id, paths, caption)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMediaGroup",
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode())
    except Exception:
        raise RuntimeError(
            "Telegram send was not confirmed. No automatic retry: delivery could be ambiguous. Credentials are redacted."
        ) from None
    return validate_response(data, chat_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--digest", type=Path, default=Path("digests/latest.md"))
    parser.add_argument("--output", type=Path, default=Path("fresh-preview-output"))
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()

    markdown = args.digest.read_text(encoding="utf-8")
    date_value, papers = parse_digest(markdown)
    abstracts = fetch_abstracts(papers)
    chosen = select_candidate(papers, abstracts)
    abstract = abstracts.get(chosen["pmid"], "")
    if not abstract:
        raise RuntimeError(f"No PubMed abstract could be retrieved for selected PMID {chosen['pmid']}.")

    paths = render_panels(args.output, date_value, chosen, abstract)
    caption = build_caption(date_value, chosen, abstract)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "caption.html").write_text(caption, encoding="utf-8")
    selection = {
        "date": date_value,
        "pmid": chosen["pmid"],
        "title": chosen["title"],
        "journal": chosen.get("journal", ""),
        "candidate_count": len(papers),
        "abstract_chars": len(abstract),
    }
    (args.output / "selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")
    print("FRESH_SELECTION", json.dumps(selection, ensure_ascii=False))
    print(f"Rendered {len(paths)} fresh panels from the live digest.")

    if args.send:
        if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
            raise RuntimeError("Refusing workflow rerun to prevent duplicate delivery.")
        receipt = send_album(
            os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            os.environ.get("TELEGRAM_CHAT_ID", ""),
            paths,
            caption,
        )
        (args.output / "telegram-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print("TELEGRAM_ACCEPTED", json.dumps(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
