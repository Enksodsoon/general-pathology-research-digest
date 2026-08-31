from __future__ import annotations

import ipaddress
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from .models import HttpResponse, SearchHit
from .parsing import EVENT_TERMS, MEDICAL_TERMS, extract_page_links, parse_rss


Fetch = Callable[[str], HttpResponse]

LOCALES = {
    "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "th": {"hl": "th", "gl": "TH", "ceid": "TH:th"},
    "ja": {"hl": "ja", "gl": "JP", "ceid": "JP:ja"},
}

KNOWN_EVENT_HOSTS = (
    "medall.org",
    "eventbrite.",
    "peatix.com",
    "connpass.com",
    "zoom.us",
    "tghn.org",
    "who.int",
    "mahidol.ac.th",
    "chula.ac.th",
    "cmu.ac.th",
    "psu.ac.th",
    "tu.ac.th",
    "moph.go.th",
    "medicalcouncil.or.th",
)

BLOCKED_HOSTS = (
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
)


def build_search_url(source: str, query: str, language: str) -> str:
    language = language if language in LOCALES else "en"
    if source == "bing":
        params = urllib.parse.urlencode({"q": query, "format": "rss", "setlang": language})
        return f"https://www.bing.com/search?{params}"
    if source == "google_news":
        params = {"q": query, **LOCALES[language]}
        return f"https://news.google.com/rss/search?{urllib.parse.urlencode(params)}"
    if source == "gdelt":
        params = urllib.parse.urlencode(
            {
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": "75",
                "sort": "datedesc",
                "timespan": "14d",
            }
        )
        return f"https://api.gdeltproject.org/api/v2/doc/doc?{params}"
    raise ValueError(f"Unsupported source: {source}")


def parse_gdelt_articles(payload: str, query_id: str, language_hint: str = "") -> list[SearchHit]:
    data = json.loads(payload)
    articles = data.get("articles", []) if isinstance(data, dict) else []
    hits: list[SearchHit] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        title = _clean_text(str(article.get("title", "")))
        url = str(article.get("url", "")).strip()
        if not title or not is_safe_public_url(url):
            continue
        published_at = _parse_gdelt_date(str(article.get("seendate", "")))
        hits.append(
            SearchHit(
                title=title,
                url=url,
                snippet="",
                source="gdelt",
                query_id=query_id,
                language_hint=language_hint,
                published_at=published_at,
            )
        )
    return hits


def extract_candidate_links(
    html: str,
    *,
    base_url: str,
    source: str,
    query_id: str,
    language_hint: str,
    limit: int = 100,
    inherited_text: str = "",
    include_all_same_host_links: bool = False,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for href, anchor_text in extract_page_links(html):
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urllib.parse.urljoin(base_url, href)
        if not is_safe_public_url(url):
            continue
        normalized = _normalize_url(url)
        if normalized in seen:
            continue
        parts = urllib.parse.urlsplit(normalized)
        lower = f"{anchor_text} {parts.path} {parts.query}".casefold()
        host = parts.netloc.casefold()
        event_like = any(term in lower for term in EVENT_TERMS)
        platform_like = any(marker in host for marker in KNOWN_EVENT_HOSTS)
        route_like = any(marker in lower for marker in ("/event", "/webinar", "/seminar", "/conference", "/training", "/course", "/poster"))
        same_host = host == urllib.parse.urlsplit(base_url).netloc.casefold()
        if not (event_like or route_like or platform_like and anchor_text or include_all_same_host_links and same_host and anchor_text):
            continue
        if any(blocked in host for blocked in BLOCKED_HOSTS):
            continue
        seen.add(normalized)
        hits.append(
            SearchHit(
                title=anchor_text or parts.path.rsplit("/", 1)[-1].replace("-", " "),
                url=normalized,
                snippet=inherited_text,
                source=source,
                query_id=query_id,
                language_hint=language_hint,
                priority=2,
            )
        )
        if len(hits) >= limit:
            break
    return hits


def collect_search_hits(config: dict[str, Any], fetch: Fetch) -> tuple[list[SearchHit], list[dict[str, Any]]]:
    hits: list[SearchHit] = []
    diagnostics: list[dict[str, Any]] = []

    for query in config.get("queries", []):
        if not isinstance(query, dict):
            continue
        query_id = str(query.get("id", "query"))
        language = str(query.get("language", "en"))
        text = str(query.get("query", "")).strip()
        current_year = datetime.now(timezone.utc).year
        try:
            text = text.format(
                year=current_year,
                next_year=current_year + 1,
                thai_year=current_year + 543,
                next_thai_year=current_year + 544,
            )
        except (KeyError, ValueError):
            pass
        if not text:
            continue
        sources = query.get("sources", ["bing", "google_news"])
        for source in sources:
            source = str(source)
            try:
                url = build_search_url(source, text, language)
                response = fetch(url)
                if source == "gdelt":
                    found = parse_gdelt_articles(response.text, query_id=query_id, language_hint=language)
                else:
                    found = parse_rss(response.text, source=source, query_id=query_id, language_hint=language)
                hits.extend(found)
                diagnostics.append(
                    {
                        "source": source,
                        "query_id": query_id,
                        "status": "ok",
                        "count": len(found),
                        "url": url,
                    }
                )
            except Exception as exc:  # source isolation is intentional
                diagnostics.append(
                    {
                        "source": source,
                        "query_id": query_id,
                        "status": "error",
                        "count": 0,
                        "error": _short_error(exc),
                    }
                )

    for landing in config.get("landing_pages", []):
        if not isinstance(landing, dict):
            continue
        landing_id = str(landing.get("id", "landing"))
        language = str(landing.get("language", "en"))
        url = str(landing.get("url", "")).strip()
        if not is_safe_public_url(url):
            diagnostics.append(
                {"source": f"landing:{landing_id}", "query_id": landing_id, "status": "error", "count": 0, "error": "unsafe-or-invalid-url"}
            )
            continue
        try:
            response = fetch(url)
            found = extract_candidate_links(
                response.text,
                base_url=response.final_url or url,
                source=f"landing:{landing_id}",
                query_id=landing_id,
                language_hint=language,
                limit=int(landing.get("max_links", 100)),
                inherited_text=str(landing.get("inherited_text", "")),
                include_all_same_host_links=bool(landing.get("include_all_same_host_links", False)),
            )
            hits.extend(found)
            diagnostics.append(
                {
                    "source": f"landing:{landing_id}",
                    "query_id": landing_id,
                    "status": "ok",
                    "count": len(found),
                    "url": url,
                }
            )
        except Exception as exc:  # source isolation is intentional
            diagnostics.append(
                {
                    "source": f"landing:{landing_id}",
                    "query_id": landing_id,
                    "status": "error",
                    "count": 0,
                    "error": _short_error(exc),
                }
            )

    return _deduplicate_hits(hits), diagnostics


def default_fetch(
    url: str,
    *,
    timeout: int = 25,
    max_bytes: int = 3_000_000,
    attempts: int = 3,
) -> HttpResponse:
    if not is_safe_public_url(url):
        raise ValueError("Refusing non-public or invalid URL")
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MedicalEventScout/1.0; +https://github.com/Enksodsoon/general-pathology-research-digest)",
        "Accept": "text/html,application/xhtml+xml,application/xml,application/rss+xml,application/json;q=0.9,*/*;q=0.7",
        "Accept-Language": "en,th;q=0.9,ja;q=0.8",
        "Cache-Control": "no-cache",
    }
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                final_url = response.geturl()
                if not is_safe_public_url(final_url):
                    raise ValueError("Redirected to non-public URL")
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise ValueError(f"Response exceeds {max_bytes} bytes")
                content_type = response.headers.get_content_type() or "application/octet-stream"
                charset = response.headers.get_content_charset() or "utf-8"
                try:
                    text = raw.decode(charset, errors="replace")
                except LookupError:
                    text = raw.decode("utf-8", errors="replace")
                return HttpResponse(
                    url=url,
                    final_url=final_url,
                    status=getattr(response, "status", 200),
                    content_type=content_type,
                    text=text,
                )
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, socket.timeout, ValueError) as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                break
            retry_after = 0.8 * (2**attempt)
            if isinstance(exc, urllib.error.HTTPError):
                header = exc.headers.get("Retry-After") if exc.headers else None
                if header and header.isdigit():
                    retry_after = min(float(header), 10.0)
                if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                    break
            time.sleep(retry_after)
    assert last_error is not None
    raise last_error


def is_safe_public_url(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return False
    if parts.username or parts.password:
        return False
    host = parts.hostname.casefold().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def hit_priority(hit: SearchHit) -> int:
    text = f"{hit.title} {hit.snippet}".casefold()
    host = urllib.parse.urlsplit(hit.url).netloc.casefold()
    score = hit.priority
    score += 4 if any(term in text for term in EVENT_TERMS) else 0
    score += 4 if any(term in text for term in MEDICAL_TERMS) else 0
    score += 3 if any(term in text for term in ("free", "ฟรี", "無料", "no cost", "ไม่มีค่าใช้จ่าย")) else 0
    score += 2 if any(term in text for term in ("certificate", "cme", "cpd", "เกียรติบัตร", "ใบรับรอง", "修了証", "受講証")) else 0
    score += 2 if any(marker in host for marker in KNOWN_EVENT_HOSTS) else 0
    score -= 5 if any(blocked in host for blocked in BLOCKED_HOSTS) else 0
    return score


def _deduplicate_hits(hits: list[SearchHit]) -> list[SearchHit]:
    by_url: dict[str, SearchHit] = {}
    for hit in hits:
        if not is_safe_public_url(hit.url):
            continue
        normalized = _normalize_url(hit.url)
        candidate = SearchHit(
            title=hit.title,
            url=normalized,
            snippet=hit.snippet,
            source=hit.source,
            query_id=hit.query_id,
            language_hint=hit.language_hint,
            published_at=hit.published_at,
            priority=hit.priority,
        )
        current = by_url.get(normalized)
        if current is None or hit_priority(candidate) > hit_priority(current):
            by_url[normalized] = candidate
    return sorted(by_url.values(), key=lambda item: (-hit_priority(item), item.url))


def _normalize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = []
    for key, value in urllib.parse.parse_qsl(parts.query, keep_blank_values=True):
        if key.casefold().startswith("utm_") or key.casefold() in {"fbclid", "gclid", "mc_cid", "mc_eid"}:
            continue
        query.append((key, value))
    return urllib.parse.urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), parts.path or "/", urllib.parse.urlencode(query), "")
    )


def _parse_gdelt_date(value: str) -> datetime | None:
    value = value.strip()
    for pattern in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _short_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    return text[:300]


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())
