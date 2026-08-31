from __future__ import annotations

from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from xml.etree import ElementTree

from .models import SearchHit
from .text_utils import _clean_text, _clean_url, _strip_html

class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.anchors: list[tuple[str, str]] = []
        self.scripts: list[str] = []
        self.canonical = ""
        self.meta: dict[str, str] = {}
        self._capture_title = False
        self._capture_h1 = False
        self._capture_script = False
        self._current_script: list[str] = []
        self._current_anchor_href = ""
        self._current_anchor_text: list[str] = []
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.casefold(): (v or "") for k, v in attrs}
        tag = tag.casefold()
        if tag == "title":
            self._capture_title = True
        elif tag == "h1":
            self._capture_h1 = True
        elif tag == "script" and "ld+json" in attrs_dict.get("type", "").casefold():
            self._capture_script = True
            self._current_script = []
        elif tag in {"script", "style", "noscript", "template"}:
            self._ignore_depth += 1
        elif tag == "a":
            self._current_anchor_href = attrs_dict.get("href", "")
            self._current_anchor_text = []
        elif tag == "link" and "canonical" in attrs_dict.get("rel", "").casefold():
            self.canonical = attrs_dict.get("href", "")
        elif tag == "meta":
            key = attrs_dict.get("property") or attrs_dict.get("name")
            value = attrs_dict.get("content", "")
            if key and value:
                self.meta[key.casefold()] = value

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "title":
            self._capture_title = False
        elif tag == "h1":
            self._capture_h1 = False
        elif tag == "script" and self._capture_script:
            self._capture_script = False
            script = "".join(self._current_script).strip()
            if script:
                self.scripts.append(script)
            self._current_script = []
        elif tag in {"script", "style", "noscript", "template"} and self._ignore_depth:
            self._ignore_depth -= 1
        elif tag == "a" and self._current_anchor_href:
            self.anchors.append((self._current_anchor_href, _clean_text(" ".join(self._current_anchor_text))))
            self._current_anchor_href = ""
            self._current_anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._capture_script:
            self._current_script.append(data)
            return
        if self._ignore_depth:
            return
        clean = _clean_text(data)
        if not clean:
            return
        self.text_parts.append(clean)
        if self._capture_title:
            self.title_parts.append(clean)
        if self._capture_h1:
            self.h1_parts.append(clean)
        if self._current_anchor_href:
            self._current_anchor_text.append(clean)



def extract_page_links(html: str) -> list[tuple[str, str]]:
    parser = _PageParser()
    parser.feed(html)
    return parser.anchors


def parse_rss(xml: str, source: str, query_id: str, language_hint: str = "") -> list[SearchHit]:
    root = ElementTree.fromstring(xml)
    hits: list[SearchHit] = []
    for item in root.findall(".//item"):
        title = _clean_text(item.findtext("title") or "")
        url = _clean_url(item.findtext("link") or "")
        description = _strip_html(item.findtext("description") or "")
        published_at = None
        raw_date = item.findtext("pubDate") or ""
        if raw_date:
            try:
                published_at = parsedate_to_datetime(raw_date)
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                published_at = None
        if title and url:
            hits.append(
                SearchHit(
                    title=title,
                    url=url,
                    snippet=description,
                    source=source,
                    query_id=query_id,
                    language_hint=language_hint,
                    published_at=published_at,
                )
            )
    return hits
