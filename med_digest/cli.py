from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from .models import Paper
from .pipeline import run_pipeline
from .fetchers import build_profile_query, fetch_europepmc, fetch_medrxiv, fetch_pubmed
from .scoring import load_config


def load_fixture(path: str | Path):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Paper(**r) for r in records]


def fetch_live(topics_path: str | Path, per_query: int = 10, include_preprints: bool = True) -> list[Paper]:
    """Fetch live records using grouped queries, not one request per profile.

    The first implementation queried every profile separately, which is simple
    but slow and easy to time out. Grouped queries reduce API calls while the
    downstream scorer still explains which profiles matched.
    """
    config = load_config(topics_path)
    days = int(config.get("window_days", 7))
    papers: list[Paper] = []
    ncbi_key = os.environ.get("NCBI_API_KEY")
    groups = build_query_groups(config)
    for group_id, query in groups.items():
        if not query:
            continue
        papers.extend(fetch_pubmed(query, days=days, retmax=per_query, api_key=ncbi_key))
        papers.extend(fetch_europepmc(query, days=days, page_size=per_query))
    if include_preprints:
        papers.extend(fetch_medrxiv(days=days, server="medrxiv"))
        papers.extend(fetch_medrxiv(days=days, server="biorxiv"))
    return papers


def build_query_groups(config: dict) -> dict[str, str]:
    profile_map = {p.get("id"): p for p in config.get("profiles", [])}

    def terms(*ids: str) -> list[str]:
        output: list[str] = []
        for pid in ids:
            output.extend(profile_map.get(pid, {}).get("terms", []))
        # Keep high-signal terms first and avoid overlong URLs.
        seen = set()
        deduped = []
        for term in output:
            low = term.lower()
            if low not in seen:
                seen.add(low)
                deduped.append(term)
        return deduped[:18]

    pathology_anchor = build_profile_query(
        [
            "pathology",
            "histopathology",
            "surgical pathology",
            "diagnostic pathology",
            "cytopathology",
            "immunohistochemistry",
            "molecular pathology",
            "digital pathology",
            "laboratory medicine",
            "structured reporting",
        ],
        max_terms=10,
    )

    return {
        "general_pathology": build_profile_query(
            terms("general_pathology_research", "surgical_pathology_updates"), max_terms=18
        ),
        "molecular_digital_pathology": (
            f"({pathology_anchor}) AND "
            f"({build_profile_query(terms('molecular_ihc_biomarkers', 'digital_computational_pathology'), max_terms=18)})"
        ),
        "cyto_lab_quality": build_profile_query(
            terms("cytopathology_small_biopsy", "laboratory_medicine_transfusion", "pathology_quality_education_workflow"),
            max_terms=18,
        ),
        "treatment_and_gp": (
            f"({pathology_anchor}) AND "
            f"({build_profile_query(terms('novel_treatment_pathology_linked', 'general_medical_gp_updates'), max_terms=18)})"
        ),
        "guidelines_reviews": (
            f"({pathology_anchor}) AND "
            f"({build_profile_query(terms('guidelines_reviews_high_level_evidence'), max_terms=10)})"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run medical research digest pipeline")
    parser.add_argument("--fixture", help="JSON fixture of normalized Paper records")
    parser.add_argument("--live", action="store_true", help="Fetch live records from configured sources")
    parser.add_argument("--topics", default="config/topics.json")
    parser.add_argument("--settings", default="config/settings.json")
    parser.add_argument("--out-dir", default="digests")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--date", default=None)
    parser.add_argument("--per-query", type=int, default=10)
    parser.add_argument("--no-preprints", action="store_true")
    args = parser.parse_args()

    if args.fixture:
        papers = load_fixture(args.fixture)
    elif args.live:
        try:
            papers = fetch_live(args.topics, per_query=args.per_query, include_preprints=not args.no_preprints)
        except Exception as exc:
            print(f"ERROR: live fetch failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        if not papers:
            raise SystemExit("Live fetch returned zero papers. Check API access or query settings.")
    else:
        raise SystemExit("Use --fixture for test mode or --live for API mode.")

    markdown, scored, duplicates = run_pipeline(papers, args.topics, args.settings, args.out_dir, args.data_dir, args.date)
    print(markdown)
    print(f"\nQA: fetched={len(papers)} scored={len(scored)} duplicates={len(duplicates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
