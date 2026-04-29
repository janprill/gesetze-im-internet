from sgbpot.build_index import build_index
from sgbpot.compile_cards_spark import compile_cards
from sgbpot.ingest_xml import ingest_from_fixture
from sgbpot.rlm_env import SGBMemory
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_and_index(tmp_path):
    out = tmp_path / "mini-varstore"
    ingest_from_fixture(
        fixture=str(REPO_ROOT / "tests/fixtures/mini_sgb_x.xml"),
        out_dir=str(out),
        config_path="config/sgb_books.yaml",
        repo=str(REPO_ROOT),
    )
    build_index(str(out))
    compile_cards(str(out), books=["SGB_X"], dry_run=True)
    return out


def test_rlm_memory_access(tmp_path):
    varstore = _build_and_index(tmp_path)
    memory = SGBMemory(str(varstore), scope="SGB")
    assert "SGB_X" in memory.books()

    norm = memory.norm("SGB_X:§24")
    assert "Verwaltungsaktes" in norm.text()
    hits = memory.search("Verwaltungsakt", k=3)
    assert any(item["norm_id"] == "SGB_X:§24" for item in hits)


# ── P5: Scope-Prüfung in norm() ──────────────────────────────────────────────

def test_scope_sgb_raises_keyerror_for_sgg_norm(tmp_path):
    """SGBMemory(scope='SGG') soll KeyError werfen bei SGB_V:§44."""
    varstore = _build_and_index(tmp_path)
    sgg_mem = SGBMemory(str(varstore), scope="SGG")
    with pytest.raises(KeyError, match="out of scope"):
        sgg_mem.norm("SGB_X:§24")


def test_scope_none_allows_all(tmp_path):
    """Ohne Scope sind alle Normen erlaubt."""
    varstore = _build_and_index(tmp_path)
    mem = SGBMemory(str(varstore), scope=None)
    norm = mem.norm("SGB_X:§24")
    assert "Verwaltungsaktes" in norm.text()


def test_scope_sgb_allows_sgb_norms(tmp_path):
    """SGBMemory(scope='SGB') erlaubt SGB_X-Normen."""
    varstore = _build_and_index(tmp_path)
    mem = SGBMemory(str(varstore), scope="SGB")
    norm = mem.norm("SGB_X:§24")
    assert "Verwaltungsaktes" in norm.text()


# ── P6: Search-Deduplizierung + unit_type-Filter ─────────────────────────────

def test_search_deduplicates_by_norm_id(tmp_path):
    """Deduplizierte Ergebnisse haben weniger Einträge als Roh-Treffer."""
    varstore = _build_and_index(tmp_path)
    mem = SGBMemory(str(varstore))

    # Ohne Dedup würden wir duplicate norm_ids bekommen
    hits = mem.search("Verwaltungsakt", k=20)
    norm_ids = [h["norm_id"] for h in hits]
    # Jede norm_id soll maximal einmal vorkommen
    assert len(norm_ids) == len(set(norm_ids)), (
        f"Duplicate norm_ids in search results: {norm_ids}"
    )


def test_search_unit_type_paragraph_filter(tmp_path):
    """unit_type='paragraph' filtert auf Paragraph-Spans."""
    varstore = _build_and_index(tmp_path)
    mem = SGBMemory(str(varstore))

    hits = mem.search("Verwaltungsakt", k=20, unit_type="paragraph")
    for hit in hits:
        assert hit.get("unit_type") == "paragraph", (
            f"Expected paragraph, got {hit.get('unit_type')} for {hit.get('norm_id')}"
        )


def test_search_default_returns_all_unit_types(tmp_path):
    """Default: alle unit_types (Rückwärtskompatibilität)."""
    varstore = _build_and_index(tmp_path)
    mem = SGBMemory(str(varstore))

    hits = mem.search("Verwaltungsakt", k=20)
    unit_types = {h.get("unit_type") for h in hits}
    # Sollte mindestens paragraph und sentence enthalten
    assert "paragraph" in unit_types, f"No paragraph results: {unit_types}"
    # sentence kann auch vorkommen
    assert len(unit_types) >= 1
