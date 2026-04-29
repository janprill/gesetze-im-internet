import json
from pathlib import Path

from sgbpot.compile_cards_spark import compile_cards
from sgbpot.ingest_xml import ingest_from_fixture
from sgbpot.validate import validate


REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_varstore_with_cards(tmp_path):
    out = tmp_path / "mini-varstore"
    ingest_from_fixture(
        fixture=str(REPO_ROOT / "tests/fixtures/mini_sgb_x.xml"),
        out_dir=str(out),
        config_path="config/sgb_books.yaml",
        repo=str(REPO_ROOT),
    )
    compile_cards(str(out), books=["SGB_X"], dry_run=True)
    return out


def test_validate_passes_for_minivastore(tmp_path):
    varstore = _build_varstore_with_cards(tmp_path)
    ok, messages = validate(str(varstore))
    assert ok
    assert messages == ["validation passed"]


def test_validate_fails_on_invalid_evidence(tmp_path):
    varstore = _build_varstore_with_cards(tmp_path)
    cards_file = sorted((varstore / "cards").glob("*.jsonl"))[0]
    rows = [json.loads(line) for line in cards_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[0]["roles"][0]["evidence"] = ["SGB_X:§99:Abs1:S1"]
    cards_file.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    ok, messages = validate(str(varstore))
    assert not ok
    assert any("unknown evidence" in line.lower() for line in messages)
