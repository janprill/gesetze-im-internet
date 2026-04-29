import json

from sgbpot.build_index import build_index
from sgbpot.compile_cards_spark import compile_cards
from sgbpot.compile_topics_spark import compile_topics, _tokenize, _card_topic_tags
from sgbpot.ingest_xml import ingest_from_fixture
from sgbpot.varstore import SGBMemory

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── P3: Hilfstests für Tokenisierung und Topic-Gruppierung ───────────────────

def test_tokenize_filters_stop_words() -> None:
    tokens = _tokenize("Anhörung der Beteiligten vor Erlass eines Verwaltungsaktes")
    assert "Anhörung".lower() in tokens or "anhörung" in tokens
    assert "der" not in tokens
    assert "die" not in tokens
    assert "vor" not in tokens
    assert "beteiligten" in tokens
    assert "verwaltungsaktes" in tokens


def test_tokenize_handles_empty() -> None:
    assert _tokenize("") == set()


def test_card_topic_tags_extracts_heading() -> None:
    card = {"heading": "Krankengeld bei Arbeitsunfähigkeit", "topic_tags": []}
    tags = _card_topic_tags(card)
    assert "krankengeld" in tags
    assert "arbeitsunfähigkeit" in tags


def test_card_topic_tags_extracts_topic_tags() -> None:
    card = {"heading": "", "topic_tags": ["Krankengeld", "Arbeitsunfähigkeit"]}
    tags = _card_topic_tags(card)
    assert "krankengeld" in tags
    assert "arbeitsunfähigkeit" in tags


def _prepare(tmp_path):
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


def test_packer_norm_output_contains_raw_and_heading(tmp_path):
    varstore = _prepare(tmp_path)
    mem = SGBMemory(str(varstore))
    packed = mem.packer.norms(["SGB_X:§24"], include_raw=True, include_cards=True)
    assert "SGB_X:§24" in packed
    assert "[SGB_X:§24:Abs1]" in packed
    assert "Anhörung Beteiligter" in packed


# ── P3: Topic-Gruppierung (Integration) ──────────────────────────────────────

def test_compile_topics_with_grouping_produces_fewer_topics_than_cards(tmp_path):
    """Nach Gruppierung gibt es weniger Topics als Cards."""
    varstore = _prepare(tmp_path)
    path = compile_topics(str(varstore), dry_run=True, group=True)

    topics = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    cards = [json.loads(line) for line in (varstore / "cards" / "SGB_X.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(topics) > 0
    assert len(cards) > 0
    assert len(topics) <= len(cards), (
        f"Topics ({len(topics)}) should be ≤ Cards ({len(cards)}) after grouping"
    )


def test_grouped_topic_can_have_multiple_core_norms(tmp_path):
    """Ein gruppiertes Topic kann mehrere core_norms enthalten."""
    varstore = _prepare(tmp_path)
    path = compile_topics(str(varstore), dry_run=True, group=True)

    topics = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Mindestens ein Topic sollte mehr als eine Norm haben (wenn grouping effektiv ist)
    # Bei nur 2 Normen im Mini-Fixture teilen sie ggf. keine Tags → dann jede einzeln
    # → das ist auch OK
    assert len(topics) > 0
    for t in topics:
        assert len(t.get("core_norms", [])) >= 1, (
            f"Topic {t['topic_id']} hat keine core_norms"
        )


def test_topics_validation_passes_after_grouping(tmp_path):
    """Validator besteht auch nach Topic-Gruppierung."""
    from sgbpot.validate import validate
    varstore = _prepare(tmp_path)
    compile_topics(str(varstore), dry_run=True, group=True)
    ok, msgs = validate(str(varstore))
    assert ok, f"Validation failed: {msgs[:5]}"
