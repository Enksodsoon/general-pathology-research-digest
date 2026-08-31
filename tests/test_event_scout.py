from __future__ import annotations

from datetime import datetime, timezone

from event_scout.models import SearchHit
from event_scout.parsing import parse_event_page, parse_rss
from event_scout.pipeline import select_new_events
from event_scout.rules import evaluate_event
from event_scout.telegram_notify import build_event_message, notify_events


NOW = datetime(2026, 8, 31, 3, 0, tzinfo=timezone.utc)


def hit(url: str, title: str = "Medical event") -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        snippet="",
        source="test",
        query_id="test-query",
        language_hint="en",
    )


def test_jsonld_online_free_event_is_accepted_and_rendered_in_bangkok_time() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="https://events.example.org/pathology-webinar">
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": "Free Clinical Pathology Webinar",
        "startDate": "2026-09-15T12:00:00+00:00",
        "endDate": "2026-09-15T13:00:00+00:00",
        "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
        "location": {"@type": "VirtualLocation", "url": "https://zoom.us/webinar/register/abc"},
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "url": "https://events.example.org/register/pathology"}
      }
      </script>
    </head><body>
      <h1>Free Clinical Pathology Webinar</h1>
      <p>For physicians and healthcare professionals. Attendance certificate available.</p>
    </body></html>
    """

    event = parse_event_page(hit("https://events.example.org/news"), html, now=NOW)
    decision = evaluate_event(event, now=NOW)

    assert decision.accepted is True
    assert event.title == "Free Clinical Pathology Webinar"
    assert event.mode == "online"
    assert event.free_status == "confirmed"
    assert event.certificate_status == "confirmed"
    assert event.registration_url == "https://events.example.org/register/pathology"
    assert event.start_at is not None
    assert event.start_at.isoformat() == "2026-09-15T12:00:00+00:00"

    message = build_event_message(event)
    assert "15 Sep 2026, 19:00–20:00 ICT" in message
    assert "Certificate: Yes" in message
    assert "https://events.example.org/register/pathology" in message


def test_thai_buddhist_date_onsite_thailand_free_certificate_is_parsed() -> None:
    html = """
    <html><head><title>สัมมนาเวชศาสตร์แม่นยำ</title></head><body>
      <h1>สัมมนาเวชศาสตร์แม่นยำสำหรับแพทย์</h1>
      <p>วันที่ 20 กันยายน 2569 เวลา 09.00-12.00 น.</p>
      <p>ณ คณะแพทยศาสตร์ จุฬาลงกรณ์มหาวิทยาลัย กรุงเทพฯ ประเทศไทย</p>
      <p>เข้าร่วมฟรี ไม่มีค่าใช้จ่าย และรับเกียรติบัตรหลังจบงาน</p>
      <a href="https://forms.example.th/register">ลงทะเบียน</a>
    </body></html>
    """

    event = parse_event_page(
        hit("https://medicine.example.th/seminar", "สัมมนาเวชศาสตร์แม่นยำ"),
        html,
        now=NOW,
    )
    decision = evaluate_event(event, now=NOW)

    assert decision.accepted is True
    assert event.language == "th"
    assert event.mode == "onsite_thailand"
    assert event.free_status == "confirmed"
    assert event.certificate_status == "confirmed"
    assert event.start_at is not None
    assert event.start_at.isoformat() == "2026-09-20T09:00:00+07:00"
    assert event.end_at is not None
    assert event.end_at.isoformat() == "2026-09-20T12:00:00+07:00"
    assert event.registration_url == "https://forms.example.th/register"


def test_japanese_online_event_is_converted_from_jst() -> None:
    html = """
    <html><head><title>医療AIオンラインセミナー</title></head><body>
      <h1>医療AIオンラインセミナー</h1>
      <p>2026年9月18日（金）19:00〜20:30（JST）</p>
      <p>医師・医療従事者向け。参加費無料。受講証明書を発行します。</p>
      <a href="https://peatix.com/event/medical-ai">お申し込み</a>
    </body></html>
    """

    event = parse_event_page(
        hit("https://example.jp/medical-ai", "医療AIオンラインセミナー"),
        html,
        now=NOW,
    )
    decision = evaluate_event(event, now=NOW)

    assert decision.accepted is True
    assert event.language == "ja"
    assert event.mode == "online"
    assert event.start_at is not None
    assert event.start_at.isoformat() == "2026-09-18T19:00:00+09:00"
    message = build_event_message(event)
    assert "18 Sep 2026, 17:00–18:30 ICT" in message


def test_nonzero_price_is_rejected_even_when_page_mentions_free_preview() -> None:
    html = """
    <html><head><script type="application/ld+json">
      {
        "@context":"https://schema.org",
        "@type":"Event",
        "name":"Clinical Update Conference",
        "startDate":"2026-10-10T10:00:00+07:00",
        "eventAttendanceMode":"https://schema.org/OnlineEventAttendanceMode",
        "offers":{"@type":"Offer","price":"50","priceCurrency":"USD","url":"https://paid.example/register"}
      }
    </script></head><body>
      <p>Medical conference for doctors. Free preview video available. Registration fee applies.</p>
    </body></html>
    """

    event = parse_event_page(hit("https://paid.example/event"), html, now=NOW)
    decision = evaluate_event(event, now=NOW)

    assert event.free_status == "paid"
    assert decision.accepted is False
    assert "not-confirmed-free" in decision.reasons


def test_free_onsite_event_outside_thailand_is_rejected() -> None:
    html = """
    <html><head><script type="application/ld+json">
      {
        "@context":"https://schema.org",
        "@type":"Event",
        "name":"Tokyo Clinical Seminar",
        "startDate":"2026-10-12T18:00:00+09:00",
        "eventAttendanceMode":"https://schema.org/OfflineEventAttendanceMode",
        "location":{"@type":"Place","name":"Tokyo Medical Hall","address":{"addressCountry":"JP","addressLocality":"Tokyo"}},
        "offers":{"@type":"Offer","price":"0","priceCurrency":"JPY"}
      }
    </script></head><body><p>Medical seminar for physicians. Free.</p></body></html>
    """

    event = parse_event_page(hit("https://example.jp/tokyo-clinical"), html, now=NOW)
    decision = evaluate_event(event, now=NOW)

    assert event.mode == "onsite_other"
    assert decision.accepted is False
    assert "not-online-or-thailand" in decision.reasons


def test_closed_registration_is_rejected() -> None:
    html = """
    <html><body>
      <h1>Free Medical Webinar</h1>
      <p>September 20, 2026 7:00 PM GMT. Online webinar for healthcare professionals.</p>
      <p>Free. Attendance certificate available. Registration closed.</p>
    </body></html>
    """

    event = parse_event_page(hit("https://example.org/closed", "Free Medical Webinar"), html, now=NOW)
    decision = evaluate_event(event, now=NOW)

    assert event.registration_closed is True
    assert decision.accepted is False
    assert "registration-closed" in decision.reasons


def test_rss_parser_preserves_direct_result_links() -> None:
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>Free Medical Webinar</title><link>https://events.example.org/free-medical</link>
      <description>Online seminar for doctors, free registration.</description><pubDate>Mon, 31 Aug 2026 01:00:00 GMT</pubDate></item>
    </channel></rss>"""

    results = parse_rss(xml, source="bing", query_id="en-general", language_hint="en")

    assert len(results) == 1
    assert results[0].url == "https://events.example.org/free-medical"
    assert results[0].title == "Free Medical Webinar"
    assert results[0].published_at is not None


def test_state_deduplicates_previously_notified_event() -> None:
    html = """
    <html><body>
      <h1>Free Online Medical Seminar</h1>
      <p>September 25, 2026 10:00 AM ICT. Free online webinar for doctors.</p>
      <a href="https://example.org/register">Register</a>
    </body></html>
    """
    event = parse_event_page(hit("https://example.org/event", "Free Online Medical Seminar"), html, now=NOW)
    assert evaluate_event(event, now=NOW).accepted

    first, state = select_new_events([event], {}, now=NOW)
    second, state2 = select_new_events([event], state, now=NOW)

    assert len(first) == 1
    assert second == []
    assert state2 == state


def test_negative_certificate_statement_does_not_claim_certificate() -> None:
    html = """
    <html><body>
      <h1>Free Medical Webinar</h1>
      <p>September 22, 2026 10:00 AM UTC. Free online webinar for physicians.</p>
      <p>No certificate of attendance will be issued.</p>
      <a href="https://example.org/register">Register</a>
    </body></html>
    """
    event = parse_event_page(hit("https://example.org/no-cert"), html, now=NOW)
    assert event.certificate_status == "unknown"


def test_free_for_members_only_is_not_treated_as_generally_free() -> None:
    html = """
    <html><body>
      <h1>Clinical Medicine Webinar</h1>
      <p>September 23, 2026 10:00 AM UTC. Online webinar for doctors.</p>
      <p>Free for members only; non-members pay USD 50.</p>
      <a href="https://example.org/register">Register</a>
    </body></html>
    """
    event = parse_event_page(hit("https://example.org/members"), html, now=NOW)
    assert event.free_status != "confirmed"
    assert evaluate_event(event, now=NOW).accepted is False


def test_javascript_text_is_not_used_as_event_evidence() -> None:
    html = """
    <html><head><script>window.labels = 'free medical webinar certificate online';</script></head>
    <body><h1>Hospital annual report</h1><p>Published September 2026.</p></body></html>
    """
    event = parse_event_page(hit("https://example.org/annual-report", "Hospital annual report"), html, now=NOW)
    assert event.free_status == "unknown"
    assert event.certificate_status == "unknown"
    assert event.event_relevance is False


def test_english_time_range_with_meridiem_only_on_end_applies_to_start() -> None:
    html = """
    <html><body>
      <h1>Free Oncology Webinar</h1>
      <p>29th Sep 2026, 5:00 - 5:45pm (GMT)</p>
      <p>Free online medical webinar. Attendance certificate available.</p>
      <a href="https://example.org/register">Register</a>
    </body></html>
    """
    event = parse_event_page(hit("https://example.org/oncology"), html, now=NOW)
    assert event.start_at is not None
    assert event.start_at.isoformat() == "2026-09-29T17:00:00+00:00"
    assert event.end_at is not None
    assert event.end_at.isoformat() == "2026-09-29T17:45:00+00:00"


def test_search_snippet_cannot_substitute_for_page_evidence() -> None:
    misleading_hit = SearchHit(
        title="Hospital annual report",
        url="https://example.org/annual-report",
        snippet="Free online medical webinar September 30, 2026 10:00 AM UTC with certificate",
        source="search",
        query_id="q",
        language_hint="en",
    )
    html = """<html><body><h1>Hospital annual report</h1><p>Financial and service statistics.</p></body></html>"""

    event = parse_event_page(misleading_hit, html, now=NOW)

    assert event.free_status == "unknown"
    assert event.start_at is None
    assert event.event_relevance is False


def test_notify_events_records_only_successfully_sent_alerts(tmp_path) -> None:
    first = parse_event_page(
        hit("https://example.org/one", "Free Medical Webinar One"),
        """<html><body><h1>Free Medical Webinar One</h1><p>September 25, 2026 10:00 AM UTC. Free online medical webinar.</p><a href='https://example.org/register/one'>Register</a></body></html>""",
        now=NOW,
    )
    second = parse_event_page(
        hit("https://example.org/two", "Free Medical Webinar Two"),
        """<html><body><h1>Free Medical Webinar Two</h1><p>September 26, 2026 10:00 AM UTC. Free online medical webinar.</p><a href='https://example.org/register/two'>Register</a></body></html>""",
        now=NOW,
    )
    state_path = tmp_path / "state.json"
    attempts: list[str] = []

    def sender(_token: str, _chat: str, text: str) -> dict:
        attempts.append(text)
        if len(attempts) == 2:
            return {"ok": False, "description": "simulated failure"}
        return {"ok": True}

    try:
        notify_events(
            [first, second],
            state_path=state_path,
            bot_token="token",
            chat_id="chat",
            now=NOW,
            sender=sender,
            delay=0,
        )
    except RuntimeError as exc:
        assert "simulated failure" in str(exc)
    else:
        raise AssertionError("Expected the second notification to fail")

    saved = __import__("json").loads(state_path.read_text(encoding="utf-8"))
    assert first.key() in saved
    assert second.key() not in saved


def test_free_material_does_not_override_paid_registration() -> None:
    html = """
    <html><body>
      <h1>ประชุมวิชาการโลหิตวิทยาแห่งปี</h1>
      <p>วันที่ 7 มีนาคม 2570 เวลา 09.00-16.00 น.</p>
      <p>ขอเชิญแพทย์และบุคลากรทางการแพทย์เข้าร่วมประชุม</p>
      <p>ฟรี! หนังสือประกอบการประชุม</p>
      <p>ค่าลงทะเบียน Onsite 1,500 บาท | Online 1,000 บาท</p>
    </body></html>
    """

    event = parse_event_page(hit("https://example.th/paid-conference", "ประชุมวิชาการโลหิตวิทยา"), html, now=NOW)

    assert event.free_status == "paid"
    assert evaluate_event(event, now=NOW).accepted is False


def test_free_brochure_does_not_prove_free_attendance() -> None:
    html = """
    <html><body>
      <h1>Clinical Medicine Conference</h1>
      <p>October 10, 2026 09:00 AM UTC. Conference for physicians.</p>
      <p>Download the free conference brochure and programme.</p>
      <a href="https://example.org/register">Register</a>
    </body></html>
    """

    event = parse_event_page(hit("https://example.org/conference"), html, now=NOW)

    assert event.free_status == "unknown"
    assert evaluate_event(event, now=NOW).accepted is False
