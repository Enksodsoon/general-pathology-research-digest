# General Pathology Research Digest Prototype

Daily pathology and medical research surveillance prototype for Codex automation.

## What it does now

- Loads normalized paper records from a JSON fixture for tests and calibration.
- Fetches live records from PubMed, Europe PMC, medRxiv, and bioRxiv.
- Deduplicates by overlapping PMID, DOI, PMCID, and normalized title.
- Scores papers by general pathology relevance, molecular/IHC/biomarker relevance, digital pathology relevance, surgical pathology relevance, cytopathology, laboratory medicine, pathology QA/workflow/education, GP practicality, pathology-linked novel treatments, and evidence level.
- Keeps NSCLC/miRNA/FFPE and renal biopsy/glomerular disease as low-priority watchlist topics only.
- Separates preprints from peer-reviewed papers.
- Writes Markdown digest files and a machine-readable CSV log.
- Includes unit tests and a GitHub Actions schedule with manual dispatch.

## What Codex should add next

1. Calibrate scoring after 3-5 days of manual digest review.
2. Add source-response caching if live API volume grows.
3. Optional Notion or email delivery after digest quality is stable.

## Run locally

```bash
python3 -m pytest -q
python3 -m med_digest.cli --fixture fixtures/sample_papers.json --date 2026-05-30
python3 -m med_digest.cli --live
```

## Telegram daily summary

The GitHub Actions workflow can send a short Telegram news-style message after
each digest run. Add these repository secrets to enable it:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

The notification includes the top pathology papers, GP/preprint/watchlist
counts, and a link to `digests/latest.md`. If the secrets are missing, the
workflow skips Telegram and still generates the digest normally.

## Safety principle

This is research surveillance and education only. The summary should never imply practice-changing evidence unless the underlying paper is a strong guideline, large RCT, or high-quality systematic review and the full text has been checked.
