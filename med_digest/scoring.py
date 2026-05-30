from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from .models import Paper


EVIDENCE_POSITIVE = {
    "guideline": 5,
    "practice guideline": 5,
    "systematic review": 4,
    "meta-analysis": 4,
    "randomized": 4,
    "randomised": 4,
    "phase 3": 3,
    "phase iii": 3,
    "cohort": 2,
    "external validation": 3,
    "clinical trial": 3,
    "diagnostic accuracy": 2,
}

EVIDENCE_NEGATIVE = {
    "editorial": -3,
    "comment": -3,
    "letter": -2,
    "case report": -1,
    "mouse": -2,
    "mice": -2,
    "murine": -2,
    "rat model": -2,
    "cell line": -2,
    "in vitro": -2,
    "protocol": -1,
}


PRIMARY_PATHOLOGY_PROFILES = {
    "general_pathology_research",
    "surgical_pathology_updates",
    "cytopathology_small_biopsy",
    "laboratory_medicine_transfusion",
    "pathology_quality_education_workflow",
    "guidelines_reviews_high_level_evidence",
}
CORE_PATHOLOGY_PROFILES = {
    "general_pathology_research",
    "surgical_pathology_updates",
    "digital_computational_pathology",
    "cytopathology_small_biopsy",
    "laboratory_medicine_transfusion",
    "pathology_quality_education_workflow",
}
GP_PROFILE = "general_medical_gp_updates"
LEGACY_PROFILE = "legacy_project_watch_low_priority"
PATHOLOGY_ANCHOR_TERMS = {
    "pathologist",
    "histopathology",
    "histologic",
    "surgical pathology",
    "diagnostic pathology",
    "anatomic pathology",
    "clinicopathologic",
    "pathologic diagnosis",
    "pathologic complete response",
    "pathologic response",
    "tumor classification",
    "WHO classification",
    "immunohistochemistry",
    "molecular pathology",
    "digital pathology",
    "whole slide imaging",
    "cytopathology",
    "cytology",
    "fine needle aspiration",
    "cell block",
    "laboratory medicine",
    "clinical pathology",
    "transfusion medicine",
    "synoptic report",
    "structured reporting",
    "interobserver agreement",
    "diagnostic reproducibility",
}


def load_config(path: str | Path) -> Dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def paper_keys(paper: Paper) -> set[str]:
    """Return all stable identifiers for duplicate detection.

    Using only a single preferred key is unsafe because one source may provide
    PMID+DOI while another provides DOI only. A paper is considered duplicate
    when any stable key overlaps.
    """
    keys: set[str] = set()
    for prefix, value in (("pmid", paper.pmid), ("doi", paper.doi), ("pmcid", paper.pmcid)):
        cleaned = (value or "").strip().lower()
        if cleaned:
            keys.add(f"{prefix}:{cleaned}")
    # Title fallback is intentionally last: useful, but less stable.
    from .models import normalize_title
    normalized_title = normalize_title(paper.title)
    if normalized_title:
        keys.add(f"title:{normalized_title}")
    return keys


def dedupe_papers(papers: Iterable[Paper]) -> Tuple[List[Paper], List[Paper]]:
    seen: set[str] = set()
    unique: List[Paper] = []
    duplicates: List[Paper] = []
    for paper in papers:
        keys = paper_keys(paper)
        if keys & seen:
            duplicates.append(paper)
            seen.update(keys)
            continue
        seen.update(keys)
        unique.append(paper)
    return unique, duplicates


def score_paper(paper: Paper, config: Dict) -> Paper:
    haystack = f"{paper.title} {paper.abstract} {paper.publication_type} {paper.category}"
    matched_profiles: List[str] = []
    relevance = 0

    for profile in config.get("profiles", []):
        hits = [term for term in profile.get("terms", []) if _contains_term(haystack, term)]
        if hits:
            matched_profiles.append(profile["id"])
            relevance += int(profile.get("weight", 1)) + min(len(hits), 4)

    for term in config.get("negative_terms", []):
        if _contains_term(haystack, term):
            relevance -= 2

    haystack_lower = haystack.lower()
    evidence = 0
    for term, value in EVIDENCE_POSITIVE.items():
        if _contains_term(haystack_lower, term):
            evidence += value
    for term, value in EVIDENCE_NEGATIVE.items():
        if _contains_term(haystack_lower, term):
            evidence += value

    if paper.is_preprint:
        evidence -= 3

    # User asked to stop emphasizing old project-specific topics
    # (NSCLC/miRNA/FFPE and renal/glomerular disease). Keep them as
    # watchlist candidates unless they also match broad pathology profiles.
    if LEGACY_PROFILE in matched_profiles and not (PRIMARY_PATHOLOGY_PROFILES & set(matched_profiles)):
        relevance -= 8

    if paper.abstract:
        evidence += 1
    else:
        evidence -= 3
    if paper.doi or paper.pmid or paper.pmcid:
        evidence += 1

    total = relevance + evidence
    paper.matched_profiles = matched_profiles
    paper.relevance_score = relevance
    paper.evidence_score = evidence
    paper.total_score = total
    paper.decision = decide(paper, config)
    return paper


def decide(paper: Paper, config: Dict) -> str:
    min_score = int(config.get("min_digest_score", 4))
    profiles = set(paper.matched_profiles)
    text = f"{paper.title} {paper.abstract} {paper.publication_type} {paper.category}"
    has_core_pathology = bool(CORE_PATHOLOGY_PROFILES & profiles) and _has_pathology_anchor(text)
    is_gp_only = GP_PROFILE in profiles and not (profiles & (CORE_PATHOLOGY_PROFILES | {"molecular_ihc_biomarkers", "novel_treatment_pathology_linked"}))

    # Old project-specific areas are still tracked, but they should not dominate
    # the daily digest unless they are also clearly broad pathology/guideline items.
    if LEGACY_PROFILE in profiles and not has_core_pathology:
        if paper.total_score >= 1:
            return "watchlist"
        return "skip"

    if paper.is_preprint and paper.total_score >= min_score:
        return "preprint_watch"
    if paper.total_score >= min_score and (has_core_pathology or is_gp_only):
        return "digest"
    if paper.total_score >= 1:
        return "watchlist"
    return "skip"


def score_and_rank(papers: Iterable[Paper], config: Dict) -> List[Paper]:
    scored = [score_paper(p, config) for p in papers]
    return sorted(scored, key=lambda p: (p.decision != "digest", -p.total_score, p.is_preprint, p.title.lower()))


def _contains_term(text: str, term: str) -> bool:
    """Match configured terms as words/phrases, not arbitrary substrings.

    Short molecular terms such as ISH and PCR should not match inside unrelated
    words like "established" or "practice"; this materially affects ranking.
    """
    term = (term or "").strip()
    if not term:
        return False
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in term.split()) + r"(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _has_pathology_anchor(text: str) -> bool:
    return any(_contains_term(text, term) for term in PATHOLOGY_ANCHOR_TERMS)
