from med_digest.fetchers import parse_pubmed_xml


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
