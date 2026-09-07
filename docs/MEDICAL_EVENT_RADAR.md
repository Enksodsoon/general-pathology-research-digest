# Medical Event Radar — repaired September 2026

## Operational contract

The GitHub Actions workflow `Daily Free Medical Events` performs live discovery, event-page verification and Telegram delivery. It runs daily at **07:43 Asia/Bangkok**, expressed explicitly as 00:43 UTC. A second schedule at **10:17 Bangkok** retries when that day's scan and notifications have not completed. GitHub scheduling is best-effort, not an exact delivery-time guarantee. Both attempts depend on GitHub availability; this is not an independent external outage watchdog.

Every completed notification run sends one compact status message, including on days with no new events. Individual new events and material corrections are sent separately, up to 20 per run. Previously acknowledged events are suppressed; unsent eligible events remain candidates for the next scan. The existing Telegram bot and chat secrets are reused. No attendee registration is submitted automatically.

## Discovery and verification

The source configuration includes 24 institutional/society/event-platform pages or feeds and 24 multilingual search queries across Bing RSS and Google News RSS. The latter uses a rolling 30-day publication window and resolves public article redirects to publisher URLs. No paid search API key, proxy bypass or CAPTCHA bypass is used. Query-result relevance is checked before spending the page-inspection budget. An irrelevant or unresolvable feed is reported as degraded, not silently successful.

A bounded 180-candidate scan balances hosts, prioritizes event-specific URLs and rotates deeper queues. This is deliberately not a claim to crawl the whole internet. Event dates must be linked to the actual event heading or matching structured metadata, with a known timezone. Shared exhibition headers, generic indexes and archive pages are not valid evidence for a webinar date. A specific NCC adapter uses the organizer's explicitly shared series clock and each individually dated session/link.

Attendance must be explicitly free. Past, clearly paid, closed, cancelled, members-only or ambiguous events are rejected. Online events can be hosted anywhere; in-person events must be in Thailand. Certificates and CME/CPD are separate fields: accreditation is not proof of a certificate or Thai credit recognition, and pending accreditation is not marked accredited. Registration links are checked without submitting personal information; JavaScript/login-only forms remain labelled as requiring confirmation. A generic learning portal is replaced by the exact event-information page rather than mislabelled as a direct individual registration URL.

## Health and delivery evidence

- `OK`: configured source checks succeeded and the scan verified events.
- `DEGRADED`: a source was blocked, timed out, returned unusable results, or verification coverage was limited. Zero matches is not proof that no events exist.
- `FAILED`: scan/delivery could not complete. The workflow fails visibly and attempts a Telegram failure notice when credentials/connectivity allow.

Telegram `ok=true` plus an integer `message_id` is required before writing a successful receipt. Missing credentials and corrupt receipt state fail explicitly. Receipts are written after each acknowledgement, persisted to Git and also uploaded as a workflow artifact. This proves Telegram API acceptance, not whether a device displayed a push or whether a person read the message. Network failure between sending and saving can still create an at-least-once retry; absolute exactly-once delivery is not promised.

## Current files

- `events/latest.md` and dated reports: human-readable verified results.
- `data/verified_radar/latest.json`: events, discovery sources, all inspected URLs and rejection reasons.
- `data/verified_radar/receipts.json`: successful event/status acknowledgements and daily recovery guard.
- `config/verified_sources.json`: editable source and query inventory.
- `event_scout/verified_extract.py`, `verified_scan.py`, `verified_news.py`, `verified_notify.py`: production implementation.

Legacy `event_scout.cli`, old CSV/JSON outputs and hand-curated test payloads are historical, not the scheduled production path. The old notification ledger is read only to suppress valid previous messages and identify corrections. The manual notification workflow now calls the same live scan as the daily workflow; it cannot replay a fixed old event list.

## Run and maintain

```sh
python -m pip install -r requirements.txt
python -m pytest -q
python -m event_scout.verified_scan
# Requires existing TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment secrets:
python -m event_scout.verified_notify
```

Review source errors and fixtures after organizer layout changes. Do not loosen free-attendance/date/link checks merely to increase alert counts. Pages that prohibit automated access are not bypassed. Image-only, login-only or inaccessible listings remain coverage limitations. The independent pathology paper digest is unchanged; BeautifulSoup is added to shared requirements so the expanded regression suite works in both workflows.
