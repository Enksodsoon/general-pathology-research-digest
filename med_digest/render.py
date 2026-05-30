from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, List
from .models import Paper
from .summarize import infer_study_type


def render_markdown(papers: Iterable[Paper], settings: dict | None = None, today: str | None = None) -> str:
    settings = settings or {}
    papers = list(papers)
    today = today or date.today().isoformat()
    digest = [p for p in papers if p.decision == "digest" and not p.is_preprint]
    pathology_digest = [p for p in digest if not _is_gp_only(p)]
    gp_digest = [p for p in digest if _is_gp_only(p)]
    preprints = [p for p in papers if p.decision in {"preprint_watch", "digest"} and p.is_preprint]
    watchlist = [p for p in papers if p.decision == "watchlist"]

    lines: List[str] = []
    lines.append(f"# {settings.get('digest_title', 'Daily General Pathology Research Digest')}")
    lines.append(f"Date: {today}")
    lines.append("")
    lines.append(f"> {settings.get('safety_note', 'Research surveillance and education only.')}" )
    lines.append("")
    lines.append("## Top peer-reviewed pathology papers")
    lines.extend(_render_section(pathology_digest[:10], empty="No peer-reviewed pathology papers met the digest threshold today."))
    lines.append("")
    lines.append("## General medical / GP-useful updates")
    lines.extend(_render_section(gp_digest[:5], empty="No GP-useful papers met the digest threshold today."))
    lines.append("")
    lines.append("## Preprints — not peer reviewed")
    lines.extend(_render_section(preprints[:5], empty="No preprints met the watch threshold today."))
    lines.append("")
    lines.append("## Additional watchlist")
    lines.extend(_render_section(watchlist[:8], empty="No additional watchlist papers today."))
    lines.append("")
    lines.append("## Pipeline QA")
    lines.append(f"- Total scored candidates: {len(papers)}")
    lines.append(f"- Peer-reviewed pathology digest items: {len(pathology_digest)}")
    lines.append(f"- GP-useful digest items: {len(gp_digest)}")
    lines.append(f"- Preprint watch items: {len(preprints)}")
    lines.append(f"- Watchlist items: {len(watchlist)}")
    return "\n".join(lines).strip() + "\n"


def _is_gp_only(paper: Paper) -> bool:
    profiles = set(paper.matched_profiles)
    pathology_profiles = {
        "general_pathology_research",
        "surgical_pathology_updates",
        "molecular_ihc_biomarkers",
        "digital_computational_pathology",
        "cytopathology_small_biopsy",
        "laboratory_medicine_transfusion",
        "pathology_quality_education_workflow",
        "novel_treatment_pathology_linked",
        "guidelines_reviews_high_level_evidence",
    }
    return "general_medical_gp_updates" in profiles and not (profiles & pathology_profiles)


def _render_section(papers: List[Paper], empty: str) -> List[str]:
    if not papers:
        return [empty]
    lines: List[str] = []
    for idx, p in enumerate(papers, 1):
        profiles = ", ".join(p.matched_profiles) if p.matched_profiles else "No configured profile matched"
        link = p.url or (f"https://doi.org/{p.doi}" if p.doi else "")
        lines.append(f"### {idx}. {p.title}")
        lines.append(f"**Source:** {p.source}  ")
        lines.append(f"**Journal:** {p.journal or 'Unknown'}  ")
        lines.append(f"**Study type:** {infer_study_type(p)}  ")
        lines.append(f"**Matched profile:** {profiles}  ")
        lines.append(f"**Score:** {p.total_score} = relevance {p.relevance_score} + evidence {p.evidence_score}  ")
        if link:
            lines.append(f"**Link:** {link}  ")
        lines.append(f"**Takeaway:** {p.summary}")
        lines.append(f"**Limitations:** {p.limitations}")
        lines.append(f"**Confidence:** {p.confidence}")
        lines.append("")
    return lines


def write_digest(markdown: str, out_dir: str | Path, today: str) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{today}.md").write_text(markdown, encoding="utf-8")
    (out_dir / "latest.md").write_text(markdown, encoding="utf-8")
