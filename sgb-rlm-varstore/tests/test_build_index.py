import json
from pathlib import Path

from sgbpot.build_index import build_index
from sgbpot.cli import build_parser
from sgbpot.ingest_xml import ingest_from_fixture
from sgbpot.varstore import SGBMemory


REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_mini_varstore(tmp_path):
    out = tmp_path / "mini-varstore"
    ingest_from_fixture(
        fixture=str(REPO_ROOT / "tests/fixtures/mini_sgb_x.xml"),
        out_dir=str(out),
        config_path="config/sgb_books.yaml",
        repo=str(REPO_ROOT),
    )
    return out


def test_build_index_and_search(tmp_path):
    varstore = _build_mini_varstore(tmp_path)
    db = build_index(str(varstore))
    assert db.exists()

    memory = SGBMemory(str(varstore))
    hits = memory.search("Anhörung Verwaltungsakt", k=5)
    assert any(item["norm_id"] == "SGB_X:§24" for item in hits)


# ── P4: --all-books CLI Flag ─────────────────────────────────────────────────

def test_all_books_flag_mutually_exclusive_with_books() -> None:
    """--all-books und --books schließen sich gegenseitig aus."""
    parser = build_parser()

    # --all-books alleine ist ok
    args = parser.parse_args(["compile-cards", "--varstore", "/tmp/test", "--all-books"])
    assert args.all_books is True
    assert args.books is None

    # --books alleine ist ok
    args = parser.parse_args(["compile-cards", "--varstore", "/tmp/test", "--books", "SGB_X"])
    assert args.all_books is False
    assert args.books == ["SGB_X"]


def test_all_books_and_books_conflict() -> None:
    """--all-books + --books führt zu argparse-Fehler."""
    import sys
    parser = build_parser()
    try:
        parser.parse_args(["compile-cards", "--varstore", "/tmp/test", "--all-books", "--books", "SGB_X"])
    except SystemExit:
        return  # Erwartet: argparse beendet mit Fehler
    pytest.fail("Expected argparse to reject --all-books + --books")


# ── P7: LIKE-Fallback-Test ──────────────────────────────────────────────────

def test_like_fallback_search(tmp_path):
    """Suche funktioniert auch ohne FTS5 (LIKE-Fallback)."""
    import sqlite3
    varstore = _build_mini_varstore(tmp_path)
    db_path = build_index(str(varstore))

    # Erzwinge LIKE-Pfad: Setze fts_enabled=0
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE search_meta SET value='0' WHERE key='fts_enabled'")
    conn.commit()
    conn.close()

    memory = SGBMemory(str(varstore))
    hits = memory.search("Anhörung", k=5)
    assert len(hits) > 0
    assert any(item["norm_id"] == "SGB_X:§24" for item in hits)
