from __future__ import annotations

from typing import Any, Dict, Iterable, List
from .models import Paper


def normalize_pubmed_record(record: Dict[str, Any]) -> Paper:
    ids = record.get("articleids", []) or []
    doi = _find_id(ids, "doi")
    pmcid = _find_id(ids, "pmc") or _find_id(ids, "pmcid")
    pmid = str(record.get("uid") or record.get("pmid") or "")
    pubtypes = record.get("pubtype", []) or []
    authors = [a.get("name", "") for a in record.get("authors", []) if isinstance(a, dict)]
    return Paper(
        title=clean_text(record.get("title", "")),
        abstract=clean_text(record.get("abstract", "")),
        authors=authors,
        journal=clean_text(record.get("fulljournalname") or record.get("source") or ""),
        year=str(record.get("pubdate", ""))[:4],
        date=str(record.get("pubdate", "")),
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        source="PubMed",
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        publication_type=", ".join(pubtypes),
        is_preprint=False,
        raw=record,
    )


def normalize_europepmc_record(record: Dict[str, Any]) -> Paper:
    pmid = str(record.get("pmid") or "")
    doi = str(record.get("doi") or "")
    pmcid = str(record.get("pmcid") or "")
    authors = _split_authors(record.get("authorString", ""))
    source = "Europe PMC"
    return Paper(
        title=clean_text(record.get("title", "")),
        abstract=clean_text(record.get("abstractText", "")),
        authors=authors,
        journal=clean_text(record.get("journalTitle") or record.get("source") or ""),
        year=str(record.get("pubYear") or ""),
        date=str(record.get("firstPublicationDate") or record.get("pubYear") or ""),
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        source=source,
        url=f"https://europepmc.org/article/MED/{pmid}" if pmid else (f"https://doi.org/{doi}" if doi else ""),
        publication_type=clean_text(record.get("pubType") or ""),
        is_preprint=False,
        raw=record,
    )


def normalize_preprint_record(record: Dict[str, Any], server: str = "medrxiv") -> Paper:
    doi = str(record.get("doi") or "")
    return Paper(
        title=clean_text(record.get("title", "")),
        abstract=clean_text(record.get("abstract", "")),
        authors=_split_authors(record.get("authors", "")),
        journal=server,
        year=str(record.get("date", ""))[:4],
        date=str(record.get("date", "")),
        doi=doi,
        source=server,
        url=f"https://doi.org/{doi}" if doi else "",
        publication_type="Preprint",
        category=record.get("category", ""),
        is_preprint=True,
        raw=record,
    )


def clean_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\n", " ").replace("\t", " ")
    return " ".join(text.split())


def _find_id(ids: Iterable[Dict[str, Any]], idtype: str) -> str:
    for item in ids:
        if str(item.get("idtype", "")).lower() == idtype.lower():
            return str(item.get("value", ""))
    return ""


def _split_authors(author_string: str) -> List[str]:
    text = clean_text(author_string)
    if not text:
        return []
    if ";" in text:
        return [a.strip() for a in text.split(";") if a.strip()]
    if "," in text and len(text.split(",")) <= 8:
        return [a.strip() for a in text.split(",") if a.strip()]
    return [text]
