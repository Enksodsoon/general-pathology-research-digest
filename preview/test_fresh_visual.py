from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fresh_visual_preview_v2 as fv


DIGEST = """# Daily General Pathology Research Digest
Date: 2026-09-07

## Top peer-reviewed pathology papers
### 1. Radiology considerations for the PREMIUM study: a multicenter randomized controlled trial of abbreviated MRI versus ultrasound for liver cancer screening in cirrhosis.
**Source:** PubMed
**Journal:** Abdominal radiology
**Study type:** Guideline / recommendation
**Score:** 21 = relevance 16 + evidence 5
**Link:** https://pubmed.ncbi.nlm.nih.gov/42701973/
**Takeaway:** This paper describes a trial protocol.

### 2. Assessment of antral G-cell hyperplasia on routine histologic sections.
**Source:** PubMed
**Journal:** Annals of diagnostic pathology
**Study type:** Journal Article
**Score:** 19 = relevance 17 + evidence 2
**Link:** https://pubmed.ncbi.nlm.nih.gov/42702513/
**Takeaway:** Proton pump inhibitor-associated gastric neuroendocrine tumors are recognized as a distinct category.
"""

G_CELL_ABSTRACT = """Proton pump inhibitor (PPI)-associated gastric neuroendocrine tumors (NETs) are recognized as a distinct clinicopathologic category. We evaluated antral G-cell hyperplasia as a potential tissue-level correlate of gastrin-axis activation. Archived gastric biopsies obtained over a 15-month period were reviewed, including 113 patients with gastroesophageal reflux disease/Barrett's esophagus receiving documented PPI/H2-blocker therapy and 21 controls without documented exposure. Antral G-cell hyperplasia was scored (0-2) on H&E-stained sections, and gastrin immunohistochemistry (IHC) was scored using a 3-tier scheme (0-2). High antral H&E scores (1-2) were more frequent in the GERD/BE group than in controls (66.4% vs 28.6%; p = 0.001). Interobserver agreement improved with binary scoring (κf = 0.694; 95% CI, 0.591-0.790). H&E and gastrin IHC scores showed a moderate positive correlation (Spearman's ρ = 0.473, p < 0.001). H&E scores 1-2 demonstrated greater discrimination for documented PPI/H2 exposure than gastrin IHC score 2 (AUC 0.689 vs 0.576). No enterochromaffin-like cell hyperplasia or NET was apparent in available body/fundus biopsies on H&E review alone. Antral G-cell hyperplasia can be assessed using a simple binary H&E scoring scheme with acceptable interobserver reproducibility, and may represent a useful research tool for future studies."""

PROTOCOL_ABSTRACT = """This paper describes the rationale and implementation of a multicenter randomized controlled trial. Patients will be randomized to abbreviated MRI or ultrasound. Primary outcomes will be assessed after follow-up."""


class FreshVisualTests(unittest.TestCase):
    def test_digest_parser_finds_today_pubmed_candidates(self):
        date_value, papers = fv.parse_digest(DIGEST)
        self.assertEqual(date_value, "2026-09-07")
        self.assertEqual([p["pmid"] for p in papers], ["42701973", "42702513"])
        self.assertEqual(papers[1]["journal"], "Annals of diagnostic pathology")

    def test_selector_prefers_result_rich_original_pathology_paper(self):
        _, papers = fv.parse_digest(DIGEST)
        abstracts = {"42701973": PROTOCOL_ABSTRACT, "42702513": G_CELL_ABSTRACT}
        chosen = fv.select_candidate(papers, abstracts)
        self.assertEqual(chosen["pmid"], "42702513")

    def test_highlights_keep_context_design_results_and_caution(self):
        h = fv.extract_highlights(G_CELL_ABSTRACT)
        self.assertIn("113", h["design"])
        self.assertIn("21", h["design"])
        self.assertIn("66.4%", h["result_primary"])
        self.assertIn("28.6%", h["result_primary"])
        self.assertIn("AUC 0.689", h["result_secondary"])
        self.assertIn("0.576", h["result_secondary"])
        self.assertIn("κ", h["agreement"])
        self.assertIn("research", h["caution"].lower())

    def test_renderer_produces_four_readable_fresh_panels(self):
        _, papers = fv.parse_digest(DIGEST)
        paper = papers[1]
        with tempfile.TemporaryDirectory() as td:
            paths = fv.render_panels(Path(td), "2026-09-07", paper, G_CELL_ABSTRACT)
            self.assertEqual(len(paths), 4)
            for path in paths:
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 10000)
            self.assertNotIn("42698384", "".join(p.name for p in paths))

    def test_caption_identifies_live_digest_and_source(self):
        _, papers = fv.parse_digest(DIGEST)
        caption = fv.build_caption("2026-09-07", papers[1], G_CELL_ABSTRACT)
        self.assertIn("LIVE 7 SEPTEMBER 2026 DIGEST", caption)
        self.assertIn("42702513", caption)
        self.assertIn("not practice-changing", caption.lower())


if __name__ == "__main__":
    unittest.main()
