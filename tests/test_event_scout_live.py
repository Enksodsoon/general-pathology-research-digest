from __future__ import annotations

import json
from datetime import datetime, timezone

from event_scout.models import HttpResponse, MedicalEvent, SearchHit
from event_scout.outputs import render_report, write_outputs
from event_scout.pipeline import deduplicate_events, run_scan, select_new_events
from event_scout.sources import (
    build_search_url,
    collect_search_hits,
    extract_candidate_links,
    parse_gdelt_articles,
)


NOW = datetime(2026, 8, 31, 3, 0, tzinfo=timezone.utc)


def event(
    *,
    title: str,
    url: str,
    start: str,
    certificate: str = "unknown",
    confidence: int = 8,
    source: str = "test",
) -> MedicalEvent:
    return MedicalEvent(
        title=title,
        source_url=url,
        registration_url=url,
        source=source,
        query_id="q",
        language="en",
        start_at=datetime.fromisoformat(start),
        mode="online",
        location="Online",
        free_status="confirmed",
        certificate_status=certificate,
        medical_relevance=True,
        event_relevance=True,
        confidence=confidence,
    )


def test_search_urls_are_localized_and_keyless() -> None:
    bing = build_search_url("bing", "สัมมนาแพทย์ ฟรี", "th")
    google = build_search_url("google_news", "医療 セミナー 無料", "ja")
    gdelt = build_search_url("gdelt", "free medical webinar", "en")

    assert bing.startswith("https://www.bing.com/search?")
    assert "format=rss" in bing
    assert google.startswith("https://news.google.com/rss/search?")
    assert "ceid=JP%3Aja" in google
    assert gdelt.startswith("https://api.gdeltproject.org/api/v2/doc/doc?")
    assert "format=json" in gdelt
    assert "maxrecords=" in gdelt


def test_gdelt_parser_returns_direct_article_urls() -> None:
    payload = json.dumps(
        {
            "articles": [
                {
                    "title": "Free clinical webinar announced",
                    "url": "https://hospital.example.org/events/clinical-webinar",
                    "seendate": "20260830T020000Z",
                    "language": "English",
                }
            ]
        }
    )

    hits = parse_gdelt_articles(payload, query_id="en-general", language_hint="en")

    assert len(hits) == 1
    assert hits[0].url == "https://hospital.example.org/events/clinical-webinar"
    assert hits[0].published_at is not None


def test_landing_page_extraction_keeps_only_event_like_public_links() -> None:
    html = """
    <html><body>
      <a href="/events/pathology-webinar">Free pathology webinar</a>
      <a href="https://127.0.0.1/admin">Medical seminar</a>
      <a href="mailto:info@example.org">Contact</a>
      <a href="/about">About our hospital</a>
      <a href="/events/pathology-webinar">Register for webinar</a>
    </body></html>
    """

    hits = extract_candidate_links(
        html,
        base_url="https://hospital.example.org/education",
        source="landing:example",
        query_id="landing-example",
        language_hint="en",
    )

    assert [item.url for item in hits] == ["https://hospital.example.org/events/pathology-webinar"]


def test_collect_search_hits_continues_when_one_source_fails() -> None:
    config = {
        "queries": [
            {
                "id": "en-general",
                "language": "en",
                "query": "free medical webinar",
                "sources": ["bing", "google_news", "gdelt"],
            }
        ],
        "landing_pages": [],
    }

    def fetch(url: str) -> HttpResponse:
        if "bing.com" in url:
            raise OSError("temporary Bing failure")
        if "news.google.com" in url:
            return HttpResponse(
                url=url,
                final_url=url,
                status=200,
                content_type="application/rss+xml",
                text="""<?xml version='1.0'?><rss><channel><item>
                <title>Free Medical Webinar</title>
                <link>https://events.example.org/free-medical</link>
                <description>Online event for physicians</description>
                </item></channel></rss>""",
            )
        return HttpResponse(
            url=url,
            final_url=url,
            status=200,
            content_type="application/json",
            text=json.dumps({"articles": []}),
        )

    hits, diagnostics = collect_search_hits(config, fetch)

    assert len(hits) == 1
    assert hits[0].source == "google_news"
    assert any(item["source"] == "bing" and item["status"] == "error" for item in diagnostics)
    assert any(item["source"] == "google_news" and item["status"] == "ok" for item in diagnostics)


def test_event_deduplication_merges_cross_source_evidence_and_keeps_direct_link() -> None:
    first = event(
        title="Free Clinical Pathology Webinar",
        url="https://news.example.org/announcement",
        start="2026-09-15T12:00:00+00:00",
        certificate="unknown",
        confidence=8,
        source="gdelt",
    )
    second = event(
        title="FREE clinical pathology webinar!",
        url="https://events.example.org/register/123",
        start="2026-09-15T12:00:00+00:00",
        certificate="confirmed",
        confidence=10,
        source="bing",
    )
    second.organizer = "Example Medical Society"

    merged = deduplicate_events([first, second])

    assert len(merged) == 1
    assert merged[0].registration_url == "https://events.example.org/register/123"
    assert merged[0].certificate_status == "confirmed"
    assert set(merged[0].evidence_sources) == {"bing", "gdelt"}


def test_notification_limit_only_marks_events_that_will_be_sent() -> None:
    events = [
        event(title=f"Free Medical Webinar {index}", url=f"https://example.org/{index}", start=f"2026-09-{10 + index:02d}T10:00:00+00:00")
        for index in range(1, 4)
    ]

    first, state = select_new_events(events, {}, now=NOW, limit=2)
    second, state2 = select_new_events(events, state, now=NOW, limit=2)

    assert len(first) == 2
    assert len(state) == 2
    assert len(second) == 1
    assert len(state2) == 3


def test_run_scan_fetches_candidates_filters_and_sorts_certificate_first() -> None:
    config = {
        "settings": {"max_candidate_pages": 10, "lookahead_days": 370, "max_notifications": 10},
        "queries": [
            {
                "id": "en-general",
                "language": "en",
                "query": "free medical webinar",
                "sources": ["bing"],
            }
        ],
        "landing_pages": [],
    }
    rss = """<?xml version='1.0'?><rss><channel>
      <item><title>Medical webinar A</title><link>https://events.example.org/a</link><description>free online webinar for doctors</description></item>
      <item><title>Medical webinar B</title><link>https://events.example.org/b</link><description>free online webinar for doctors</description></item>
    </channel></rss>"""
    pages = {
        "https://events.example.org/a": """<html><body><h1>Free Medical Webinar A</h1><p>September 15, 2026 10:00 AM UTC. Online webinar for physicians. Free registration.</p><a href='/register/a'>Register</a></body></html>""",
        "https://events.example.org/b": """<html><body><h1>Free Medical Webinar B</h1><p>September 16, 2026 10:00 AM UTC. Online webinar for physicians. Free registration. Certificate of attendance available.</p><a href='/register/b'>Register</a></body></html>""",
    }

    def fetch(url: str) -> HttpResponse:
        if "bing.com/search" in url:
            return HttpResponse(url=url, final_url=url, status=200, content_type="application/rss+xml", text=rss)
        return HttpResponse(url=url, final_url=url, status=200, content_type="text/html", text=pages[url])

    result = run_scan(config, now=NOW, fetch=fetch, state={})

    assert [item.title for item in result.accepted] == ["Free Medical Webinar B", "Free Medical Webinar A"]
    assert len(result.new_events) == 2
    assert result.accepted[0].registration_url == "https://events.example.org/register/b"
    assert result.rejected_count == 0


def test_report_and_output_files_include_each_exact_registration_link(tmp_path) -> None:
    accepted = [
        event(title="Free Pathology Webinar", url="https://events.example.org/pathology", start="2026-09-15T12:00:00+00:00", certificate="confirmed")
    ]
    report = render_report(
        date_value="2026-08-31",
        accepted=accepted,
        new_events=accepted,
        scanned_hits=12,
        fetched_pages=7,
        rejected_count=3,
        diagnostics=[{"source": "bing", "status": "ok", "count": 4}],
    )
    assert "https://events.example.org/pathology" in report
    assert "Certificate: Yes" in report

    write_outputs(
        root=tmp_path,
        date_value="2026-08-31",
        report=report,
        accepted=accepted,
        new_events=accepted,
        state={accepted[0].key(): {"title": accepted[0].title}},
        diagnostics=[{"source": "bing", "status": "ok", "count": 4}],
    )

    assert (tmp_path / "events" / "2026-08-31.md").exists()
    assert (tmp_path / "events" / "latest.md").read_text(encoding="utf-8") == report
    payload = json.loads((tmp_path / "data" / "new_events.json").read_text(encoding="utf-8"))
    assert payload[0]["registration_url"] == "https://events.example.org/pathology"
    csv_text = (tmp_path / "data" / "events.csv").read_text(encoding="utf-8")
    assert "https://events.example.org/pathology" in csv_text


def test_run_scan_does_not_mark_events_notified_before_delivery() -> None:
    config = {
        "settings": {"max_candidate_pages": 5, "lookahead_days": 370, "max_notifications": 5},
        "queries": [{"id": "q", "language": "en", "query": "free medical webinar", "sources": ["bing"]}],
        "landing_pages": [],
    }
    rss = """<?xml version='1.0'?><rss><channel><item><title>Free Medical Webinar</title><link>https://events.example.org/a</link><description>online medical webinar</description></item></channel></rss>"""
    page = """<html><body><h1>Free Medical Webinar</h1><p>September 15, 2026 10:00 AM UTC. Free online medical webinar.</p><a href='https://events.example.org/register/a'>Register</a></body></html>"""

    def fetch(url: str) -> HttpResponse:
        if "bing.com/search" in url:
            return HttpResponse(url=url, final_url=url, status=200, content_type="application/rss+xml", text=rss)
        return HttpResponse(url=url, final_url=url, status=200, content_type="text/html", text=page)

    result = run_scan(config, now=NOW, fetch=fetch, state={})

    assert len(result.new_events) == 1
    assert result.state == {}
