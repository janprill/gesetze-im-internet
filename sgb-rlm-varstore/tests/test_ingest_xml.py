import json
from pathlib import Path

import pytest

from sgbpot.ingest_xml import ingest_from_fixture, _norm_unit_sentences


REPO_ROOT = Path(__file__).resolve().parents[1]


# ── P1: Satzsplitter – juristische Abkürzungen ───────────────────────────────

class TestSentenceSplitterLegalAbbreviations:
    """P1: Satzsplitter darf nicht an juristischen Abkürzungen splitten."""

    def test_kein_split_nach_abs(self) -> None:
        """§ 23 Abs. 1 genannten … → keine Trennung nach 'Abs.'"""
        result = _norm_unit_sentences("gemäß § 23 Abs. 1 genannten Voraussetzungen")
        assert len(result) == 1
        assert "Abs. 1" in result[0]

    def test_kein_split_nach_nr(self) -> None:
        result = _norm_unit_sentences("gemäß § 23 Abs. 1 Nr. 2 Buchst. a")
        assert len(result) == 1
        assert "Nr. 2" in result[0]

    def test_kein_split_nach_art(self) -> None:
        result = _norm_unit_sentences("nach Art. 3 Abs. 1 GG")
        assert len(result) == 1
        assert "Art. 3" in result[0]

    def test_kein_split_nach_buchst(self) -> None:
        result = _norm_unit_sentences("§ 1 Abs. 2 Buchst. a Satz 3")
        assert len(result) == 1
        assert "Buchst. a" in result[0]

    def test_kein_split_nach_lit(self) -> None:
        result = _norm_unit_sentences("Art. 2 lit. c der Verordnung")
        assert len(result) == 1

    def test_kein_split_nach_halbs(self) -> None:
        result = _norm_unit_sentences("§ 3 Abs. 1 Halbs. 1 bestimmt")
        assert len(result) == 1

    def test_kein_split_nach_alt(self) -> None:
        result = _norm_unit_sentences("gemäß § 44 Abs. 1 Alt. 2")
        assert len(result) == 1

    def test_kein_split_nach_var(self) -> None:
        result = _norm_unit_sentences("§ 45 Abs. 2 Var. 3")
        assert len(result) == 1

    def test_split_nach_normalem_satzende(self) -> None:
        """Normale Satzenden werden weiterhin gesplittet."""
        result = _norm_unit_sentences("Satz 1 gilt. Satz 2 gilt.")
        assert len(result) == 2
        assert result[0].endswith(".")
        assert result[1].endswith(".")

    def test_split_nach_normalem_satzende_mit_frage(self) -> None:
        result = _norm_unit_sentences("Ist das richtig? Nein.")
        assert len(result) == 2

    def test_split_nach_normalem_satzende_mit_ausruf(self) -> None:
        result = _norm_unit_sentences("Achtung! Dies ist wichtig.")
        assert len(result) == 2

    def test_ivm_abkuerzung_nicht_splitten(self) -> None:
        """i.V.m. § 44 – 'm.' soll nicht zu Satzende werden."""
        result = _norm_unit_sentences("gemäß § 44 i.V.m. § 48 SGB X")
        assert len(result) == 1

    def test_isd_abkuerzung_nicht_splitten(self) -> None:
        result = _norm_unit_sentences("i.S.d. § 31 SGB X")
        assert len(result) == 1

    def test_isv_abkuerzung_nicht_splitten(self) -> None:
        result = _norm_unit_sentences("i.S.v. § 44 SGB X")
        assert len(result) == 1

    def test_ev_abkuerzung_nicht_splitten(self) -> None:
        result = _norm_unit_sentences("der eingetragene Verein e.V. ist zuständig")
        assert len(result) == 1

    def test_af_nf_abkuerzungen_nicht_splitten(self) -> None:
        result = _norm_unit_sentences("in der a.F. galt anderes als in der n.F.")
        assert len(result) == 1

    def test_leerer_text(self) -> None:
        result = _norm_unit_sentences("")
        assert result == []

    def test_nur_abkuerzung(self) -> None:
        """Selbst wenn der ganze String eine Abkürzung ist, nicht crashen."""
        result = _norm_unit_sentences("Abs.")
        assert len(result) == 1

    def test_alle_abkuerzungen_der_liste(self) -> None:
        """Integration: Mehrere Abkürzungen in einem Satz."""
        text = (
            "Nach § 23 Abs. 1 Nr. 2 Buchst. a Halbs. 1 Alt. 2 Var. 3 i.V.m. "
            "§ 44 i.S.d. § 31 i.S.v. § 48 e.V. a.F. n.F. m.w.N."
        )
        result = _norm_unit_sentences(text)
        assert len(result) == 1


def test_ingest_mini_fixture_creates_expected_files(tmp_path):
    out = tmp_path / "mini-varstore"
    result = ingest_from_fixture(
        fixture=str(REPO_ROOT / "tests/fixtures/mini_sgb_x.xml"),
        out_dir=str(out),
        config_path="config/sgb_books.yaml",
        repo=str(REPO_ROOT),
    )

    assert Path(result["source"]).exists()
    assert Path(result["books"]).exists()
    assert Path(result["norms"]).exists()
    assert Path(result["spans"]).exists()

    norms = [json.loads(line) for line in Path(result["norms"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(n["norm_id"] == "SGB_X:§24" for n in norms)

    spans = [json.loads(line) for line in Path(result["spans"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(s["norm_id"] == "SGB_X:§24" for s in spans)
    assert any(s["span_id"] == "SGB_X:§24:Abs1:S1" for s in spans)
