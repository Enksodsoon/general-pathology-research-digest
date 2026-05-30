from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Iterable, List, Tuple
from .models import Paper
from .scoring import dedupe_papers, load_config, score_and_rank
from .summarize import cautious_summary
from .render import render_markdown, write_digest


def run_pipeline(papers: Iterable[Paper], topics_config_path: str | Path, settings_path: str | Path, out_dir: str | Path = "digests", data_dir: str | Path = "data", today: str | None = None) -> Tuple[str, List[Paper], List[Paper]]:
    topics = load_config(topics_config_path)
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    today = today or date.today().isoformat()

    unique, duplicates = dedupe_papers(papers)
    scored = score_and_rank(unique, topics)
    summarized = [cautious_summary(p) for p in scored]

    markdown = render_markdown(summarized, settings=settings, today=today)
    write_digest(markdown, out_dir, today)
    append_paper_log(summarized, data_dir, today)
    return markdown, summarized, duplicates


def append_paper_log(papers: Iterable[Paper], data_dir: str | Path, today: str) -> None:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "papers.csv"
    fieldnames = [
        "date_seen", "title", "journal", "year", "doi", "pmid", "pmcid", "source", "publication_type",
        "is_preprint", "matched_profiles", "relevance_score", "evidence_score", "total_score", "decision", "url", "summary"
    ]
    existing_rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_rows = [row for row in reader if row.get("date_seen") != today]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)
        for p in papers:
            writer.writerow({
                "date_seen": today,
                "title": p.title,
                "journal": p.journal,
                "year": p.year,
                "doi": p.doi,
                "pmid": p.pmid,
                "pmcid": p.pmcid,
                "source": p.source,
                "publication_type": p.publication_type,
                "is_preprint": p.is_preprint,
                "matched_profiles": ";".join(p.matched_profiles),
                "relevance_score": p.relevance_score,
                "evidence_score": p.evidence_score,
                "total_score": p.total_score,
                "decision": p.decision,
                "url": p.url,
                "summary": p.summary,
            })
