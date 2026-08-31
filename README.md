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

## Daily free medical event scout

A second independent workflow performs a broad daily sweep for medical meetings, seminars, webinars, workshops, conferences, and training events.

- Languages: English, Thai, and Japanese.
- Includes only events whose source confirms that attendance is free.
- Includes online events worldwide and onsite/hybrid events only when they are in Thailand.
- Prioritizes events with attendance certificates, CME/CPD credit, and Thailand venues.
- Searches Bing RSS, Google News RSS, GDELT, and curated official event pages; one source failure does not stop the remaining sweep.
- Verifies the event page, future date, delivery mode, fee status, registration status, and exact registration/event URL before inclusion.
- Deduplicates the same event found through different sources and records an event only after its Telegram alert succeeds.
- Sends one short Telegram message per newly discovered event using Bangkok time.
- Runs daily at 07:43 Asia/Bangkok and can also be started manually from GitHub Actions.

Event outputs:

- `events/latest.md` — latest verified event report.
- `events/YYYY-MM-DD.md` — dated report.
- `data/new_events.json` — events selected for individual Telegram alerts.
- `data/events.csv` — current eligible event table.
- `data/event_scout_state.json` — duplicate-suppression state.
- `data/event_scout_diagnostics.json` — source and page-fetch health.

Strictness is intentional: an event is rejected when free attendance, a future date, or an eligible online/Thailand format cannot be verified. Certificate status is shown as `Not stated` unless the source explicitly supports it.

## What Codex should add next

1. Calibrate research-paper scoring after 3-5 days of manual digest review.
2. Add source-response caching if live API volume grows.
3. Review the event scout's first week of diagnostics and tune source/query coverage if a recurring source blocks automation.

## Run locally

```bash
python3 -m pytest -q
python3 -m med_digest.cli --fixture fixtures/sample_papers.json --date 2026-05-30
python3 -m med_digest.cli --live
python3 -m event_scout.cli --live
```

## Telegram daily summaries

The GitHub Actions workflows can send Telegram notifications. Add these repository secrets to enable delivery:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

The pathology workflow sends a short daily digest. The event workflow sends each newly discovered medical event as a separate concise message with its exact registration/event link. If the secrets are missing, both workflows still generate their repository outputs.

## Safety principle

Research surveillance and event discovery are for education and planning. The paper digest should never imply practice-changing evidence unless the underlying paper is a strong guideline, large RCT, or high-quality systematic review and the full text has been checked. Event dates, availability, fees, and certificate rules can change, so the registration page remains the final source of truth.
