# General Pathology Research Digest Prototype

Daily pathology and medical research surveillance prototype for Codex automation.

## What it does now

- Loads normalized paper records from a JSON fixture.
- Deduplicates by overlapping PMID, DOI, PMCID, and normalized title.
- Scores papers by general pathology relevance, molecular/IHC/biomarker relevance, digital pathology relevance, surgical pathology relevance, cytopathology, laboratory medicine, pathology QA/workflow/education, GP practicality, pathology-linked novel treatments, and evidence level.
- Keeps NSCLC/miRNA/FFPE and renal biopsy/glomerular disease as low-priority watchlist topics only.
- Separates preprints from peer-reviewed papers.
- Writes Markdown digest files and a machine-readable CSV log.
- Includes unit tests and a GitHub Actions schedule.

## What Codex should add next

1. Live PubMed ESearch + ESummary/EFetch fetcher refinement.
2. Live Europe PMC fetcher refinement.
3. Live medRxiv/bioRxiv fetcher as a separated preprint section.
4. Optional Notion or email delivery after digest quality is stable.

## Run locally

```bash
python -m pytest -q
python -m med_digest.cli --fixture fixtures/sample_papers.json --date 2026-05-30
```

## Safety principle

This is research surveillance and education only. The summary should never imply practice-changing evidence unless the underlying paper is a strong guideline, large RCT, or high-quality systematic review and the full text has been checked.
