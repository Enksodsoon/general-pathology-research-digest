from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Dict, Iterable, List
from .models import Paper
from .normalize import clean_text, normalize_preprint_record, normalize_europepmc_record


class FetchError(RuntimeError):
    pass


def http_text(url: str, timeout: int = 30, sleep_seconds: float = 0.34) -> str:
    # Sleep by default to respect NCBI's 3 requests/sec unauthenticated guidance.
    time.sleep(sleep_seconds)
    req = urllib.request.Request(url, headers={"User-Agent": "medical-research-digest/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as exc:  # pragma: no cover - real network only
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc


def http_json(url: str, timeout: int = 30, sleep_seconds: float = 0.34) -> Dict:
    return json.loads(http_text(url, timeout=timeout, sleep_seconds=sleep_seconds))


def fetch_pubmed(query: str, days: int = 7, retmax: int = 25, api_key: str | None = None) -> List[Paper]:
    """Fetch PubMed records using ESearch then EFetch XML.

    ESearch is used to identify recent PMIDs by query/date window. EFetch XML is
    used instead of ESummary so the abstract and publication types are available.
    """
    end = date.today()
    start = end - timedelta(days=days)
    term = f"({query}) AND ({start.isoformat()}:{end.isoformat()}[edat])"
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": term, "retmode": "json", "retmax": str(retmax), "sort": "pub+date"}
    if api_key:
        params["api_key"] = api_key
    search_data = http_json(f"{base}?{urllib.parse.urlencode(params)}")
    ids = search_data.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    return fetch_pubmed_by_ids(ids, api_key=api_key)


def fetch_pubmed_by_ids(pmids: Iterable[str], api_key: str | None = None) -> List[Paper]:
    ids = [str(p) for p in pmids if str(p).strip()]
    if not ids:
        return []
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
    if api_key:
        params["api_key"] = api_key
    xml_text = http_text(f"{base}?{urllib.parse.urlencode(params)}")
    return parse_pubmed_xml(xml_text)


def parse_pubmed_xml(xml_text: str) -> List[Paper]:
    root = ET.fromstring(xml_text)
    papers: List[Paper] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article.find(".//MedlineCitation/PMID"))
        article_node = article.find(".//Article")
        title = _iter_text(article_node.find("ArticleTitle") if article_node is not None else None)
        abstract_parts = []
        for abs_text in article.findall(".//Abstract/AbstractText"):
            label = abs_text.attrib.get("Label")
            content = _iter_text(abs_text)
            if content:
                abstract_parts.append(f"{label}: {content}" if label else content)
        abstract = clean_text(" ".join(abstract_parts))
        journal = _iter_text(article.find(".//Journal/Title")) or _iter_text(article.find(".//Journal/ISOAbbreviation"))
        year = _text(article.find(".//JournalIssue/PubDate/Year")) or _text(article.find(".//ArticleDate/Year"))
        date_value = _pubmed_date(article)
        doi = _article_id(article, "doi")
        pmcid = _article_id(article, "pmc")
        authors = []
        for author in article.findall(".//AuthorList/Author"):
            last = _text(author.find("LastName"))
            fore = _text(author.find("ForeName"))
            collective = _text(author.find("CollectiveName"))
            name = " ".join([fore, last]).strip() or collective
            if name:
                authors.append(name)
        pubtypes = [_iter_text(pt) for pt in article.findall(".//PublicationTypeList/PublicationType")]
        papers.append(Paper(
            title=clean_text(title),
            abstract=abstract,
            authors=authors,
            journal=clean_text(journal),
            year=year,
            date=date_value,
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            source="PubMed",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            publication_type=", ".join([p for p in pubtypes if p]),
            is_preprint=False,
        ))
    return papers


def fetch_europepmc(query: str, page_size: int = 25) -> List[Paper]:
    base = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = urllib.parse.urlencode({"query": query, "format": "json", "pageSize": page_size, "sort": "FIRST_PDATE_D desc"})
    data = http_json(f"{base}?{params}")
    records = data.get("resultList", {}).get("result", [])
    return [normalize_europepmc_record(r) for r in records]


def fetch_medrxiv(days: int = 7, server: str = "medrxiv") -> List[Paper]:
    end = date.today()
    start = end - timedelta(days=days)
    url = f"https://api.biorxiv.org/details/{server}/{start.isoformat()}/{end.isoformat()}/0/json"
    data = http_json(url)
    records = data.get("collection", [])
    return [normalize_preprint_record(r, server=server) for r in records]


def build_profile_query(terms: List[str], max_terms: int = 10) -> str:
    selected = [t for t in terms if t.strip()][:max_terms]
    return " OR ".join(f'"{t}"' if " " in t else t for t in selected)


def _text(node) -> str:
    return clean_text(node.text if node is not None else "")


def _iter_text(node) -> str:
    if node is None:
        return ""
    return clean_text("".join(node.itertext()))


def _article_id(article, id_type: str) -> str:
    for node in article.findall(".//ArticleIdList/ArticleId"):
        if node.attrib.get("IdType", "").lower() == id_type.lower():
            return clean_text(node.text)
    return ""


def _pubmed_date(article) -> str:
    year = _text(article.find(".//ArticleDate/Year")) or _text(article.find(".//JournalIssue/PubDate/Year"))
    month = _text(article.find(".//ArticleDate/Month")) or _text(article.find(".//JournalIssue/PubDate/Month"))
    day = _text(article.find(".//ArticleDate/Day")) or _text(article.find(".//JournalIssue/PubDate/Day"))
    if year and month and day:
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return year
