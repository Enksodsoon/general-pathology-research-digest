from __future__ import annotations

from datetime import datetime, timezone

from event_scout.models import SearchHit
from event_scout.parsing import parse_event_page
from event_scout.rules import evaluate_event


NOW = datetime(2026, 8, 31, 3, 0, tzinfo=timezone.utc)
TITLE = "医療機器サイバーセキュリティ対策 丸わかり講座"
REGISTER_URL = "https://us06web.zoom.us/webinar/register/verified"


def test_mismatched_sitewide_jsonld_event_is_ignored_on_webinar_detail_page() -> None:
    filler = " ナビゲーション" * 100
    html = f"""
    <html><head>
      <title>Medtec Japan | {TITLE}</title>
      <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "Event",
        "name": "Medtec Japan 2027 Exhibition",
        "startDate": "2027-04-21T10:00:00+09:00",
        "endDate": "2027-04-23T17:00:00+09:00",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {{"@type": "Place", "name": "Tokyo Big Sight", "address": {{"addressCountry": "JP"}}}},
        "offers": {{"@type": "Offer", "price": "0", "url": "https://medtecjapan.com/visit/"}}
      }}
      </script>
    </head><body>
      <p>次回開催 2027年4月21日 10:00 - 17:00 東京ビッグサイト</p>
      <nav>{filler}</nav>
      <p>2026年9月9日(水) 16:00 - 17:00</p>
      <p>無料 オンライン開催 医療機器 医師向けウェビナー</p>
      <h1>{TITLE}</h1>
      <a href="{REGISTER_URL}">ウェビナーに申し込む</a>
    </body></html>
    """
    hit = SearchHit(
        title=TITLE,
        url="https://medtecjapan.com/medtecwebinar/5992/",
        snippet="",
        source="test",
        query_id="jsonld-regression",
        language_hint="ja",
    )

    event = parse_event_page(hit, html, now=NOW)
    decision = evaluate_event(event, now=NOW)

    assert decision.accepted is True
    assert event.title == TITLE
    assert event.start_at is not None
    assert event.start_at.isoformat() == "2026-09-09T16:00:00+09:00"
    assert event.mode == "online"
    assert event.registration_url == REGISTER_URL
