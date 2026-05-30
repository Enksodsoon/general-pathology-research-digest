from pathlib import Path
from med_digest.cli import build_query_groups, load_fixture
from med_digest.pipeline import run_pipeline
from med_digest.scoring import dedupe_papers, load_config, score_and_rank

ROOT = Path(__file__).resolve().parents[1]


def test_dedupes_by_doi():
    papers = load_fixture(ROOT / "fixtures" / "sample_papers.json")
    unique, duplicates = dedupe_papers(papers)
    assert len(unique) == 7
    assert len(duplicates) == 1


def test_general_pathology_topics_rank_above_legacy_project_topics():
    papers = load_fixture(ROOT / "fixtures" / "sample_papers.json")
    config = load_config(ROOT / "config" / "topics.json")
    unique, _ = dedupe_papers(papers)
    scored = score_and_rank(unique, config)
    digest_titles = [p.title for p in scored if p.decision == "digest"]
    assert any("endometrial carcinoma" in t for t in digest_titles)
    assert any("mitotic count" in t for t in digest_titles)
    assert any("soft tissue tumors" in t for t in digest_titles)

    legacy = next(p for p in scored if "MicroRNA signature" in p.title)
    digital = next(p for p in scored if "mitotic count" in p.title)
    assert "legacy_project_watch_low_priority" in legacy.matched_profiles
    assert digital.total_score > legacy.total_score


def test_gp_update_still_surfaces_but_is_secondary():
    papers = load_fixture(ROOT / "fixtures" / "sample_papers.json")
    config = load_config(ROOT / "config" / "topics.json")
    unique, _ = dedupe_papers(papers)
    scored = score_and_rank(unique, config)
    gp = next(p for p in scored if "acute cough" in p.title)
    pathology = next(p for p in scored if "endometrial carcinoma" in p.title)
    assert "general_medical_gp_updates" in gp.matched_profiles
    assert gp.decision == "digest"
    assert pathology.total_score >= gp.total_score


def test_preprint_is_separate():
    papers = load_fixture(ROOT / "fixtures" / "sample_papers.json")
    config = load_config(ROOT / "config" / "topics.json")
    unique, _ = dedupe_papers(papers)
    scored = score_and_rank(unique, config)
    preprint = next(p for p in scored if p.is_preprint)
    assert preprint.decision == "preprint_watch"
    assert preprint.evidence_score < preprint.relevance_score


def test_query_groups_use_general_pathology_not_old_focus():
    config = load_config(ROOT / "config" / "topics.json")
    groups = build_query_groups(config)
    assert "general_pathology" in groups
    assert "molecular_digital_pathology" in groups
    joined = " ".join(groups.values()).lower()
    assert "non-small cell lung cancer" not in joined
    assert "glomerulonephritis" not in joined
    assert "histopathology" in joined or "surgical pathology" in joined


def test_full_pipeline_writes_outputs(tmp_path):
    papers = load_fixture(ROOT / "fixtures" / "sample_papers.json")
    markdown, scored, duplicates = run_pipeline(
        papers,
        ROOT / "config" / "topics.json",
        ROOT / "config" / "settings.json",
        tmp_path / "digests",
        tmp_path / "data",
        today="2026-05-30"
    )
    assert "Top peer-reviewed pathology papers" in markdown
    assert "Preprints — not peer reviewed" in markdown
    assert "endometrial carcinoma" in markdown
    assert "MicroRNA signature" in markdown  # legacy topic should appear only in watchlist, not top pathology section
    assert (tmp_path / "digests" / "latest.md").exists()
    assert (tmp_path / "digests" / "2026-05-30.md").exists()
    assert (tmp_path / "data" / "papers.csv").exists()
    assert len(duplicates) == 1

    run_pipeline(
        papers,
        ROOT / "config" / "topics.json",
        ROOT / "config" / "settings.json",
        tmp_path / "digests",
        tmp_path / "data",
        today="2026-05-30"
    )
    csv_lines = (tmp_path / "data" / "papers.csv").read_text(encoding="utf-8").splitlines()
    assert len(csv_lines) == len(scored) + 1
