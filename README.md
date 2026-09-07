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

## Daily free medical event radar

The repaired event workflow is independent of the research-paper digest. It searches English, Thai and Japanese sources for future medical meetings, webinars, seminars and training with explicitly free attendance. Online events can be hosted worldwide; in-person events must be in Thailand. Certificates and CME/CPD are reported separately without assuming Thai recognition.

The normal schedule is **07:43 Asia/Bangkok**, with a **10:17 recovery attempt** if that day's scan and notification delivery did not finish. GitHub may delay execution. Every completed notification run sends a short status message, even with no new events; each new or corrected event has a separate message and exact event/registration link. Source failures or unusable search results are marked **DEGRADED**, not hidden behind a successful job status.

The source inventory includes 24 institutional/society/platform pages or feeds and 24 search queries using Google News RSS. Up to 180 candidate pages are checked with host balancing and rotating deeper coverage. Blocked, image-only, login-only and ambiguous listings remain limitations; the scan does not claim exhaustive internet coverage.

Current outputs:

- [`events/latest.md`](events/latest.md): latest verified event report.
- `events/YYYY-MM-DD.md`: dated event reports.
- `data/verified_radar/latest.json`: event evidence, inspected URLs and source health.
- `data/verified_radar/receipts.json`: Telegram acknowledgement IDs and recovery state.
- [`docs/MEDICAL_EVENT_RADAR.md`](docs/MEDICAL_EVENT_RADAR.md): operating contract, safeguards and troubleshooting.

The old `data/events.csv`, `new_events.json`, original event modules and manually curated payloads are historical; they no longer drive scheduled notifications. The previous delivery ledger is retained for migration/deduplication. Manual notification now runs the same live workflow rather than replaying an old fixed list.

## What Codex should add next

1. Calibrate research-paper scoring after 3-5 days of manual digest review.
2. Add source-response caching if live API volume grows.
3. Review event source-health reports after organizer website changes; do not weaken verification merely to produce more alerts.

## Run locally

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -m med_digest.cli --fixture fixtures/sample_papers.json --date 2026-05-30
python3 -m med_digest.cli --live
python3 -m event_scout.verified_scan
```

## Telegram notifications

Repository secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` enable delivery. The research workflow sends its existing daily paper summary. The event workflow sends new/corrected events plus a health message and requires Telegram to return a successful response containing a message ID before recording delivery.

Missing credentials or failed delivery are explicit errors in the repaired event workflow. API acknowledgement does not prove that a phone displayed a push notification or that a message was read. No attendee registration or personal-data submission is automated.

## Safety principle

Research surveillance and event discovery are for education and planning. The paper digest should never imply practice-changing evidence unless the underlying paper is a strong guideline, large RCT, or high-quality systematic review and the full text has been checked. Event dates, availability, fees, and certificate rules can change; the organizer's registration page remains the final source of truth.

Bing RSS is no longer scheduled: repeated live checks returned unrelated results. The optional adapter remains for tests; active discovery uses the configured Google News queries and institutional feeds.
