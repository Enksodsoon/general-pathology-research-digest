# Medical Event Radar repair verification — 7 September 2026

Production code commit: `81cb79b1d1369d289c79706e7fcae9c0ca858693`.
Production run: https://github.com/Enksodsoon/general-pathology-research-digest/actions/runs/34083296753
Job ID: `101622525586`.

The production job completed successfully. Its log records **101 tests passed**, followed by an actual live search, event verification, Telegram delivery, report/receipt commit, and artifact upload. This was not a replay of a manually prepared event list.

Live scan: **48 configured checks; 42 successful; 240 distinct links discovered; 180 candidate pages checked; 13 verified future events; 8 candidate-page errors**. Search coverage was correctly labelled **DEGRADED**, not all-clear. The six non-OK source/query checks and individual page outcomes are recorded in `data/verified_radar/latest.json`.

Telegram acknowledged **11 messages** between approximately **11:31:31 and 11:31:49 Asia/Bangkok**: **9 new events**, **1 date correction**, and **1 scan-health message**. The actual saved message IDs are **108–118** in `data/verified_radar/receipts.json`. The daily recovery guard recorded completion only after acknowledgements. Reports and receipts were committed by the workflow (commit beginning `af42ea0`) and also uploaded as a 30-day workflow artifact.

The correction was for the Medtec Japanese medical-device cybersecurity webinar: **9 September 2026, 14:00–15:00 Bangkok**, not April 2027. Three previously notified legitimate events were not resent. The incorrectly matched Thai obesity conference was excluded after article-boundary fixes; a neighboring free webinar cannot qualify that conference.

The schedule is **07:43 Bangkok daily**, with **10:17 recovery** when that day's scan/delivery has not completed. Both are GitHub schedules and can be delayed; the recovery is not an independent external watchdog. Completed runs send a brief status even when no new events qualify. Individual event links and certificates/CME remain separately labelled.

Known limits: institutional access blocks/timeouts, unusable search results, and image-only/login-only/ambiguous event information remain possible. The artifact action completed but emitted a platform Node-deprecation warning. Telegram message IDs establish API acceptance, not device push display or human reading. A future website change can require parser maintenance; no claim of exhaustive coverage or permanent reliability is made.

The separate research-paper digest implementation/workflow was left unchanged. Shared requirements gained BeautifulSoup so the enlarged test suite remains installable in either workflow. One-time repair scripts and raw probe content were removed before deployment.
