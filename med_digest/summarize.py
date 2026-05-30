from __future__ import annotations

import re
from .models import Paper


def cautious_summary(paper: Paper) -> Paper:
    abstract = paper.abstract or ""
    first_sentence = _first_sentence(abstract) or "No abstract available. Check the full text before interpreting."
    study_type = infer_study_type(paper)
    limitation = infer_limitation(paper)

    if paper.is_preprint:
        confidence = "Low"
    elif "guideline" in study_type.lower() or "systematic review" in study_type.lower() or "meta-analysis" in study_type.lower():
        confidence = "Moderate"
    elif paper.abstract:
        confidence = "Moderate"
    else:
        confidence = "Low"

    paper.summary = f"{first_sentence} Interpretation should remain cautious because this is abstract-level surveillance."
    paper.limitations = limitation
    paper.confidence = confidence
    return paper


def infer_study_type(paper: Paper) -> str:
    text = f"{paper.title} {paper.abstract} {paper.publication_type}".lower()
    if paper.is_preprint:
        return "Preprint"
    if "guideline" in text or "recommendation" in text:
        return "Guideline / recommendation"
    if "systematic review" in text or "meta-analysis" in text:
        return "Systematic review / meta-analysis"
    if "randomized" in text or "randomised" in text:
        return "Randomized clinical trial"
    if "cohort" in text:
        return "Cohort study"
    if "case report" in text:
        return "Case report"
    if "cell line" in text or "in vitro" in text:
        return "Preclinical / in vitro"
    return paper.publication_type or "Original/research article or unclear"


def infer_limitation(paper: Paper) -> str:
    text = f"{paper.title} {paper.abstract} {paper.publication_type}".lower()
    limitations = []
    if paper.is_preprint:
        limitations.append("Preprint; not peer reviewed.")
    if not paper.abstract:
        limitations.append("No abstract available in fetched metadata.")
    if "retrospective" in text:
        limitations.append("Retrospective design may limit causal inference.")
    if "cell line" in text or "in vitro" in text or "mouse" in text or "mice" in text:
        limitations.append("Preclinical evidence; clinical applicability is uncertain.")
    if not limitations:
        limitations.append("Only metadata/abstract reviewed; verify methods, effect size, and applicability in full text.")
    return " ".join(limitations)


def _first_sentence(text: str) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    match = re.search(r"(.+?[.!?])\s", text)
    if match:
        return match.group(1)
    return text[:280] + ("..." if len(text) > 280 else "")
