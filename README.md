# General Pathology Research Digest

Two independent educational automations: a daily pathology research digest and a multilingual free medical-event radar.

## Pathology research digest

The paper pipeline fetches PubMed, Europe PMC, medRxiv and bioRxiv records, deduplicates PMID/DOI/PMCID and titles, ranks relevance, and writes Markdown and CSV outputs. Its focus includes general pathology, molecular/IHC biomarkers, digital pathology, surgical pathology, cytopathology, laboratory medicine, quality assurance, education and clinically useful general medicine. Preprints are separated from peer-reviewed work. Older project-specific NSCLC/miRNA and renal-biopsy topics are low-priority watchlists, not the dominant scope.

The research-paper implementation and its scheduled workflow are unchanged by the event-radar reliability repair.

## Free medical event radar

Finds future live medical meetings, webinars, seminars, workshops and training with explicitly free attendance. Online events may be worldwide; onsite events must be in Thailand. English, Thai and Japanese sources are searched. Certificates and CME/CPD are reported separately with conditions rather than assumed available or recognized in Thailand.

**Daily primary:** 07:43 Bangkok. **Recovery opportunities:** 10:17, 13:17 and 16:17, and after the research digest's scheduled run completes. Recovery is bounded to three actual attempts per day with a two-hour cooldown. A degraded or incomplete day remains eligible; a fully healthy acknowledged day without pending items is skipped. GitHub scheduling is best-effort, not an exact delivery-time guarantee, and the recovery paths are not independent of GitHub.

Every completed delivery run sends a compact health message. New or changed events each receive their own short Telegram alert and exact event/registration link. Unsent events persist in a backlog and must be reverified before later delivery. Actual Telegram message IDs are recorded; missing credentials, failed delivery and corrupted state are explicit errors.

The configuration includes 50 source/query checks and a 220-page candidate budget with host balancing, rotating search results and backlog priority. Valid searches with no relevant results are distinguished from source failures. Inaccessible Chula Hospital and MOPH pages have additional official alternatives and publisher-scoped discovery, but their original access gaps remain labelled as partial coverage.

Current reports and evidence:

- [`events/latest.md`](events/latest.md) — latest event report.
- `events/YYYY-MM-DD.md` — dated reports.
- `data/verified_radar/latest.json` — source attempts, verification results and inspected-page outcomes.
- `data/verified_radar/receipts.json` — acknowledged messages and recovery state.
- `data/verified_radar/backlog.json` — unsent events awaiting re-verification.
- `data/verified_radar/delivery.json` — delivery totals and failures.
- [`docs/MEDICAL_EVENT_RADAR.md`](docs/MEDICAL_EVENT_RADAR.md) — full operating contract and limitations.

The original event CLI/CSV and hand-curated notification payloads are historical and do not drive scheduled production. The legacy delivery ledger is preserved for migration and deduplication. Manual event notification invokes the same fresh-search workflow as the daily run.

## Run locally

```sh
python -m pip install -r requirements.txt
python -m pytest -q
python -m med_digest.cli --live
python -m event_scout.verified_scan
python -m event_scout.verified_notify --guard --stage recovery
```

Repository secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` enable Telegram delivery. No attendee registration, purchase, or personal-data submission is automated. A Telegram acknowledgement proves API acceptance, not that a phone displayed a push notification or someone read the message.

## Evidence and maintenance

The event pipeline requires event-specific dates, known timezones, explicit free attendance and a suitable location/format. Shared banners and neighboring posts are not evidence for the selected event. Blocked, image-only, login-only or ambiguous listings can remain unverified. Empty search results do not establish that no suitable events exist.

Review source diagnostics after organizer website changes. Do not weaken verification or conceal warnings merely to increase alert counts or display a green status. Research summaries remain cautious and educational; they should not imply practice-changing evidence without appropriate full-text appraisal. Organizer registration pages remain the final authority on event availability and certificate conditions.
