# Agent Instructions — Daily General Pathology Research Digest

## Mission

Build and maintain a daily medical research surveillance automation for a Thai doctor with a pathology focus. The system must fetch recent pathology and clinically useful medical research, filter noise, rank relevance, summarize cautiously, and save a daily digest.

## Current user priority profile

Primary focus:
- General pathology news and new research across surgical pathology, cytopathology, molecular pathology, IHC/biomarkers, laboratory medicine, and digital/computational pathology.
- Diagnostic updates that change how pathologists classify, grade, stage, report, or interpret disease.
- New biomarkers, IHC markers, molecular alterations, companion diagnostics, and therapy-linked pathology findings.
- Pathology workflow, QA, interobserver agreement, diagnostic reproducibility, structured reporting, and pathology education.
- Novel treatments only when they have pathology relevance, such as predictive biomarkers, companion diagnostics, pathologic response, targeted therapy, immunotherapy, antibody-drug conjugates, or tumor-agnostic indications.

Secondary focus:
- GP-useful medical updates and high-quality general medical knowledge that is practical for outpatient care.
- Guidelines, systematic reviews, meta-analyses, major trials, and practice-relevant diagnostic studies.

Low-priority watchlist only:
- NSCLC/miRNA/FFPE biomarker papers.
- Renal biopsy/glomerular disease papers.

These older project-specific topics should not dominate the digest. Include them only if they are unusually important, high evidence, or clearly relevant to broad pathology practice.

## Core rules

1. Use official/free APIs first: PubMed/NCBI E-utilities, Europe PMC, medRxiv/bioRxiv.
2. Use a 7-day rolling window; do not rely on “today only.”
3. Deduplicate by PMID, DOI, PMCID, then normalized title.
4. Keep preprints in a separate section and label them clearly as not peer reviewed.
5. Score before summarizing.
6. Summaries must be cautious and abstract-level unless full text is available.
7. Never overstate biomarker, AI, diagnostic, or preliminary treatment findings.
8. Always write both human-readable Markdown and machine-readable CSV.
9. Tests must pass before committing digest output.
10. GitHub Actions should run at a non-round minute and include workflow_dispatch.

## Evidence interpretation style

Prefer wording like:
- “suggests”
- “was associated with”
- “showed potential”
- “may help refine diagnosis/reporting”
- “requires external validation”
- “not practice-changing by itself”

Avoid wording like:
- “proves”
- “cures”
- “definitively diagnoses” unless guideline-level evidence supports it
- “practice-changing” unless justified

## Output format

Daily digest sections:
1. Top peer-reviewed pathology papers
2. General medical / GP-useful updates
3. Preprints — not peer reviewed
4. Additional watchlist
5. Pipeline QA

Each paper summary must include:
- Source
- Journal
- Study type
- Matched profile
- Score
- Link
- Takeaway
- Limitations
- Confidence
