# Medical Event Radar — operating and recovery contract

## Daily operation

The production workflow `Daily Free Medical Events` performs fresh discovery, event-page verification, individual Telegram notifications and a compact scan-health message. It uses the existing repository Telegram secrets and does not submit attendee registrations or personal information.

Primary schedule: **07:43 Asia/Bangkok** (00:43 UTC). Recovery opportunities: **10:17, 13:17 and 16:17 Bangkok**. Recovery also checks after the separate `Daily Digest` scheduled workflow finishes on this repository's `main` branch. This listener does not change the research-paper digest.

The guard requires a real successful Telegram heartbeat receipt before considering a daily delivery complete. A degraded scan, unsent backlog, or delivery failure remains eligible for recovery after a two-hour cooldown. Automatic work is bounded to three actual attempts per Bangkok day. A fully healthy completed day without pending events is skipped. Manual runs explicitly requested by the owner can still run.

These triggers all use GitHub Actions. They reduce missed-run risk but do not constitute an independent external scheduler or a guarantee of exact start time. GitHub outages or delayed cron delivery remain platform dependencies. Trigger type and schedule are recorded in the job summary; a push/manual run must never be described as a timer-triggered run.

## Search and source health

The inventory has **50 configured checks**: 24 institutional/event-source pages or feeds and 26 English, Thai and Japanese Google News queries. Search results rotate over time and the bounded page budget is 220 candidate pages per run. Host balancing and pending-event priority prevent one publisher from consuming the entire budget.

Chulalongkorn Hospital and the MOPH main website are still checked. When they cannot be reached, official Chula Faculty of Medicine and Department of Medical Sciences pages provide additional coverage. Publisher-scoped searches also discover relevant announcements. These alternatives are labelled **partial**; they do not prove the original blocked publisher was fully searched.

A valid search response with no relevant results is an `OK` search with `no-relevant-results`, not a broken source. HTTP/access failures, redirect-resolution failures, parsing errors and partial fallback coverage remain visible warnings. Unrelated results are excluded before verification. Empty results never establish that no eligible meetings exist anywhere on the web.

Transient network failures are retried once. Explicit access denials, certificate errors and bot challenges are not bypassed. Candidate and source errors are isolated so one website does not stop the entire scan.

## Event verification

Future dates and times must come from the event's own content or matching structured metadata, with a known timezone. Shared site banners, archive pages and neighboring events cannot supply the date, fee or registration link. Outbound links do not inherit an unrelated publisher's timezone or medical status.

Attendance must be explicitly free. Closed, past, paid, cancelled, members-only and ambiguous events are rejected. Online events may be hosted worldwide; onsite events must be in Thailand. Accepted content languages are English, Thai and Japanese. Certificates, CME/CPD and any conditions are separate fields; no Thai credit recognition is assumed.

Registration links are checked without submitting information. A form that needs login or JavaScript remains labelled accordingly. When a direct form cannot be checked, the exact event page is provided rather than an unrelated homepage. Such a temporary presentation fallback does not generate a duplicate event alert.

## Delivery, backlog and evidence

The Telegram API must return `ok=true` and a positive integer `message_id` before a successful receipt is written. The file is atomically saved before in-memory state is updated. Ambiguous network failures are not immediately retried because the message may already have reached Telegram. Explicit rate-limit rejections are retried within a bounded delay.

Up to 20 new/updated events are sent per run. Every unsent or failed event is retained in a persistent backlog and prioritized for a fresh source-page check. Stale backlog entries are never sent without re-verification. A single event delivery failure does not stop delivery of independent events. Failed events remain queued, the daily summary reports the problem, and the workflow fails visibly.

Equivalent timezone representations, URL encoding or transient link fallbacks do not create new alerts. A real schedule/content change or an explicitly changed registration target can generate an update. Old receipts remain usable after the fingerprint-format migration.

Evidence is uploaded as a 30-day workflow artifact before the Git persistence step. Reports, receipts, attempt counts and backlog are then committed. Storage failures trigger an explicit failure-notification attempt. Successful Telegram acknowledgement proves server acceptance, not phone push display or human reading. A process crash between network acceptance and durable receipt persistence can still cause an at-least-once retry; exactly-once delivery is not promised.

## Files

- `events/latest.md`, `events/YYYY-MM-DD.md`: event reports.
- `data/verified_radar/latest.json`: verified events, source attempts and every inspected page outcome.
- `data/verified_radar/receipts.json`: actual Telegram acknowledgements and recovery state.
- `data/verified_radar/backlog.json`: unsent future events awaiting re-verification/delivery.
- `data/verified_radar/delivery.json`: current delivery totals and failures.
- `config/verified_sources.json`: source/query inventory and fallback definitions.
- `event_scout/verified_reliability.py`: pure recovery, canonicalization, health and queue rules.

The original event modules/CSV and hand-selected payloads are historical, not scheduled production inputs. The prior ledger is read for deduplication/migration only. Manual event notification uses the same current live pipeline.

## Verification commands

```sh
python -m pip install -r requirements.txt
python -m pytest -q
python -m compileall -q event_scout
python -m event_scout.verified_scan
python -m event_scout.verified_notify --guard --stage recovery
# Only with the existing Telegram environment secrets:
python -m event_scout.verified_notify
```

Operational readiness and external coverage are separate: regression and delivery checks can pass while publisher access remains partial. Do not remove source warnings or weaken eligibility rules merely to display a green badge.
