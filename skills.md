# Skills — Daily General Pathology Research Digest Automation

## 1. Fetching skill

Fetch from reliable APIs using rate limits and retries.

Sources:
- PubMed / NCBI E-utilities for peer-reviewed biomedical literature.
- Europe PMC for broader metadata and open-access links.
- medRxiv/bioRxiv for preprints only.

Requirements:
- Use 7-day rolling windows.
- Support NCBI API key through environment variable `NCBI_API_KEY`.
- Respect unauthenticated NCBI limit by sleeping at least 0.34 seconds between requests.
- Cache raw responses when possible.

## 2. Query-building skill

The automation should favor broad pathology surveillance, not old project-specific topics.

Preferred live query groups:
1. General pathology research
2. Surgical pathology updates
3. Molecular pathology / IHC / biomarkers
4. Digital / computational pathology
5. Cytopathology / small biopsy
6. Laboratory medicine / transfusion
7. Guidelines / reviews / high-level evidence
8. GP-useful general medical updates

NSCLC/miRNA/renal biopsy/glomerular disease terms are allowed only as a low-priority watchlist.

## 3. Normalization skill

Convert source-specific records into a common Paper model:
- title
- abstract
- authors
- journal
- date/year
- DOI
- PMID
- PMCID
- source
- URL
- publication type
- preprint status

## 4. Deduplication skill

Deduplicate by overlapping identifiers, not just one preferred key:
1. PMID
2. DOI
3. PMCID
4. normalized title

Keep duplicate counts for QA.

## 5. Scoring skill

Score each paper using:
- general pathology relevance
- surgical pathology relevance
- molecular/IHC/biomarker relevance
- digital/computational pathology relevance
- cytopathology/small biopsy relevance
- laboratory medicine relevance
- pathology QA/workflow/education relevance
- pathology-linked novel treatment signal
- GP/practical clinical relevance
- evidence quality
- negative noise penalty

Do not let legacy project topics dominate the score.

## 6. Summarization skill

Generate cautious abstract-level summaries.

Required fields:
- one-line takeaway
- study type
- main limitation
- pathology relevance
- GP relevance if applicable
- confidence level

Do not imply clinical practice change from a single abstract.

## 7. Rendering skill

Write:
- `digests/YYYY-MM-DD.md`
- `digests/latest.md`
- `data/papers.csv`

The digest must separate peer-reviewed papers and preprints.

## 8. QA skill

Before committing:
- run unit tests
- verify digest is not empty
- verify preprints are labeled separately
- verify duplicate count is reported
- verify CSV log is updated
- verify no unsafe clinical overclaiming phrases are present
- verify general pathology profiles outrank legacy NSCLC/renal profiles unless the legacy paper has strong broad relevance
