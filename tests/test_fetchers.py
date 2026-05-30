import sys
from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest

from med_digest.cli import main
from med_digest.fetchers import fetch_europepmc, fetch_medrxiv, fetch_pubmed, parse_pubmed_xml
from med_digest.models import Paper


def test_parse_pubmed_xml_extracts_abstract_and_ids():
    xml = '''<?xml version="1.0" ?><PubmedArticleSet><PubmedArticle>
    <MedlineCitation><PMID>123</PMID><Article>
      <Journal><Title>Test Journal</Title><JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue></Journal>
      <ArticleTitle>Test title</ArticleTitle>
      <Abstract><AbstractText Label="BACKGROUND">Background text.</AbstractText><AbstractText>Result text.</AbstractText></Abstract>
      <AuthorList><Author><ForeName>Alice</ForeName><LastName>Smith</LastName></Author></AuthorList>
      <PublicationTypeList><PublicationType>Randomized Controlled Trial</PublicationType></PublicationTypeList>
    </Article></MedlineCitation>
    <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/test</ArticleId><ArticleId IdType="pmc">PMC123</ArticleId></ArticleIdList></PubmedData>
    </PubmedArticle></PubmedArticleSet>'''
    papers = parse_pubmed_xml(xml)
    assert len(papers) == 1
    p = papers[0]
    assert p.pmid == "123"
    assert p.doi == "10.1/test"
    assert p.pmcid == "PMC123"
    assert "BACKGROUND" in p.abstract
    assert p.authors == ["Alice Smith"]


def test_pubmed_live_fetch_uses_rolling_window_and_optional_api_key(monkeypatch):
    calls = {}

    def fake_http_json(url, timeout=30, sleep_seconds=0.34):
        calls["search_url"] = url
        calls["search_sleep"] = sleep_seconds
        return {"esearchresult": {"idlist": ["123", "456"]}}

    def fake_fetch_by_ids(pmids, api_key=None, sleep_seconds=0.34):
        calls["pmids"] = list(pmids)
        calls["api_key"] = api_key
        calls["fetch_sleep"] = sleep_seconds
        return [Paper(title="Pathology paper", pmid="123", source="PubMed")]

    monkeypatch.setattr("med_digest.fetchers.http_json", fake_http_json)
    monkeypatch.setattr("med_digest.fetchers.fetch_pubmed_by_ids", fake_fetch_by_ids)

    papers = fetch_pubmed("pathology", days=7, retmax=2, api_key="secret", today=date(2026, 5, 30))

    params = parse_qs(urlparse(calls["search_url"]).query)
    assert params["api_key"] == ["secret"]
    assert "2026-05-23:2026-05-30[edat]" in params["term"][0]
    assert calls["search_sleep"] == pytest.approx(0.11)
    assert calls["fetch_sleep"] == pytest.approx(0.11)
    assert calls["api_key"] == "secret"
    assert calls["pmids"] == ["123", "456"]
    assert papers[0].pmid == "123"


def test_europepmc_live_fetch_uses_last_7_days_without_api_key(monkeypatch):
    calls = {}

    def fake_http_json(url, timeout=30, sleep_seconds=0.34):
        calls["url"] = url
        return {
            "resultList": {
                "result": [
                    {
                        "title": "General pathology update",
                        "abstractText": "Diagnostic pathology cohort.",
                        "journalTitle": "Pathology",
                        "pubYear": "2026",
                        "firstPublicationDate": "2026-05-29",
                        "doi": "10.1/example",
                    }
                ]
            }
        }

    monkeypatch.setattr("med_digest.fetchers.http_json", fake_http_json)

    papers = fetch_europepmc("pathology", days=7, page_size=3, today=date(2026, 5, 30))

    params = parse_qs(urlparse(calls["url"]).query)
    assert "FIRST_PDATE:[2026-05-23 TO 2026-05-30]" in params["query"][0]
    assert "api_key" not in params
    assert params["pageSize"] == ["3"]
    assert papers[0].doi == "10.1/example"


def test_preprint_fetcher_can_target_biorxiv_and_medrxiv(monkeypatch):
    urls = []

    def fake_http_json(url, timeout=30, sleep_seconds=0.34):
        urls.append(url)
        return {
            "collection": [
                {
                    "title": "Preprint pathology model",
                    "abstract": "A preprint.",
                    "authors": "A Author",
                    "date": "2026-05-29",
                    "doi": "10.1101/2026.05.29.1",
                }
            ]
        }

    monkeypatch.setattr("med_digest.fetchers.http_json", fake_http_json)

    medrxiv = fetch_medrxiv(days=7, server="medrxiv", today=date(2026, 5, 30))
    biorxiv = fetch_medrxiv(days=7, server="biorxiv", today=date(2026, 5, 30))

    assert "/medrxiv/2026-05-23/2026-05-30/" in urls[0]
    assert "/biorxiv/2026-05-23/2026-05-30/" in urls[1]
    assert medrxiv[0].is_preprint is True
    assert biorxiv[0].source == "biorxiv"


def test_live_cli_fails_visibly_when_api_fetch_fails(monkeypatch, capsys):
    def fake_fetch_live(*args, **kwargs):
        raise RuntimeError("PubMed unavailable")

    monkeypatch.setattr("med_digest.cli.fetch_live", fake_fetch_live)
    monkeypatch.setattr(sys, "argv", ["med-digest", "--live"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "ERROR: live fetch failed: PubMed unavailable" in capsys.readouterr().err
