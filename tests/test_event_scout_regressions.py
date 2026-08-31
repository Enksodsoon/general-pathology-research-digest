from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from event_scout.correction_notify import send_pending_correction
from event_scout.models import SearchHit
from event_scout.parsing import parse_event_page
from event_scout.rules import evaluate_event


NOW = datetime(2026, 8, 31, 3, 0, tzinfo=timezone.utc)
TITLE = (
    "日・米・欧の医療機器サイバーセキュリティ対策「丸わかり講座」 "
    "～日米欧の法規制から、関連するセキュリティ要求のCRAや３省２ガイドラインなど、わかりやすく解説～"
)
REGISTER_URL = "https://us06web.zoom.us/webinar/register/1517764168120/WN_hhSqS2KDRP6Vu8pLnT8a3g"


def hit(url: str, title: str) -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        snippet="",
        source="landing:medtec-japan-free-webinars",
        query_id="medtec-japan-free-webinars",
        language_hint="ja",
    )


def test_generic_medtec_free_webinar_index_is_not_an_event() -> None:
    html = f"""
    <html><head><title>Medtec Japan | 無料聴講ウェビナー</title></head><body>
      <p>次回開催 2027年4月21日 10:00 - 17:00 東京ビッグサイト</p>
      <h1>無料聴講ウェビナー</h1>
      <p>2026年9月9日 16:00 - 17:00 無料 オンライン開催 {TITLE}</p>
      <a href="/medtecwebinar/5992/">詳細をみる</a>
    </body></html>
    """

    event = parse_event_page(
        hit("https://medtecjapan.com/medtecwebinar/free/", "無料聴講ウェビナー"),
        html,
        now=NOW,
    )
    decision = evaluate_event(event, now=NOW)

    assert event.event_relevance is False
    assert decision.accepted is False
    assert "not-an-event" in decision.reasons


def test_event_detail_uses_nearby_webinar_date_not_sitewide_exhibition_date() -> None:
    filler = " ナビゲーション" * 100
    html = f"""
    <html><head><title>Medtec Japan | {TITLE}</title></head><body>
      <p>次回開催 2027年4月21日 10:00 - 17:00 東京ビッグサイト</p>
      <nav>{filler}</nav>
      <p>2026年9月9日(水) 16:00 - 17:00</p>
      <p>無料 オンライン開催 医療機器 医師 医療従事者向けウェビナー</p>
      <h1>{TITLE}</h1>
      <p>医療機器サイバーセキュリティの臨床・法規制セミナーです。</p>
      <a href="{REGISTER_URL}">ウェビナーに申し込む</a>
      <a href="https://zoom.us/test">テストページ</a>
    </body></html>
    """

    event = parse_event_page(
        hit("https://medtecjapan.com/medtecwebinar/5992/", TITLE),
        html,
        now=NOW,
    )
    decision = evaluate_event(event, now=NOW)

    assert decision.accepted is True
    assert event.start_at is not None
    assert event.start_at.isoformat() == "2026-09-09T16:00:00+09:00"
    assert event.end_at is not None
    assert event.end_at.isoformat() == "2026-09-09T17:00:00+09:00"
    assert event.registration_url == REGISTER_URL
    assert event.certificate_status == "unknown"


def test_past_event_detail_is_not_rescued_by_future_sitewide_date() -> None:
    filler = " ナビゲーション" * 100
    title = "そのシステム、実機検証だけで大丈夫ですか？ 医療機器開発ウェビナー"
    html = f"""
    <html><head><title>Medtec Japan | {title}</title></head><body>
      <p>次回開催 2027年4月21日 10:00 - 17:00 東京ビッグサイト</p>
      <nav>{filler}</nav>
      <p>2026年7月8日(水) 14:00 - 15:00</p>
      <p>無料 オンライン開催 医療機器ウェビナー</p>
      <h1>{title}</h1>
      <a href="https://us06web.zoom.us/webinar/register/example">ウェビナーに申し込む</a>
    </body></html>
    """

    event = parse_event_page(
        hit("https://medtecjapan.com/medtecwebinar/4699/", title),
        html,
        now=NOW,
    )
    decision = evaluate_event(event, now=NOW)

    assert event.start_at is not None
    assert event.start_at.isoformat() == "2026-07-08T14:00:00+09:00"
    assert decision.accepted is False
    assert "event-past" in decision.reasons


def test_zoom_test_page_is_never_selected_as_registration_link() -> None:
    html = """
    <html><body>
      <h1>Free Clinical Medical Webinar</h1>
      <p>September 20, 2026 10:00 AM - 11:00 AM UTC. Free online webinar for doctors.</p>
      <a href="https://zoom.us/test">Register / test Zoom</a>
    </body></html>
    """

    event = parse_event_page(hit("https://example.org/event", "Free Clinical Medical Webinar"), html, now=NOW)

    assert event.registration_url == "https://example.org/event"
    assert "zoom.us/test" not in event.registration_url


def test_successful_correction_marks_receipt_and_prevents_duplicate_event(tmp_path) -> None:
    correction_path = tmp_path / "correction.json"
    state_path = tmp_path / "state.json"
    correction_path.write_text(
        json.dumps(
            {
                "pending": True,
                "text": "Correction message with exact event link",
                "event_receipt": {
                    "event_key": "verified-key",
                    "title": TITLE,
                    "url": REGISTER_URL,
                    "event_start": "2026-09-09T16:00:00+09:00",
                },
            }
        ),
        encoding="utf-8",
    )

    sent = send_pending_correction(
        correction_path=correction_path,
        state_path=state_path,
        bot_token="token",
        chat_id="chat",
        now=NOW,
        sender=lambda _token, _chat, _text: {"ok": True},
    )

    assert sent == 1
    correction = json.loads(correction_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert correction["pending"] is False
    assert correction["sent_at"] == NOW.isoformat()
    assert state["verified-key"]["notification_kind"] == "correction"
    assert state["verified-key"]["url"] == REGISTER_URL


def test_failed_correction_leaves_pending_state_untouched(tmp_path) -> None:
    correction_path = tmp_path / "correction.json"
    state_path = tmp_path / "state.json"
    correction_path.write_text(
        json.dumps({"pending": True, "text": "Correction", "event_receipt": {"event_key": "key"}}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="simulated failure"):
        send_pending_correction(
            correction_path=correction_path,
            state_path=state_path,
            bot_token="token",
            chat_id="chat",
            now=NOW,
            sender=lambda _token, _chat, _text: {"ok": False, "description": "simulated failure"},
        )

    correction = json.loads(correction_path.read_text(encoding="utf-8"))
    assert correction["pending"] is True
    assert not state_path.exists()
