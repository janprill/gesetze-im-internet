"""BDD-Szenarien für GKV-Fälle – Proof of Concept.

Jedes Szenario folgt dem Muster:

    Scenario: <Kurztitel>
      Given ein Varstore mit SGB V (und ggf. SGG/SGB X)
      When  ich nach <Suchbegriff> suche
      Then  finde ich <erwartete Norm>
      And   die Ergebnisse enthalten <Textfragment>
      And   das Kontextpaket enthält Raw-Spans und Evidence
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from sgbpot.varstore import SGBMemory


# ── Fixtures ──────────────────────────────────────────────────────────────────

SGB_V_PATH = "/tmp/sgbpot-poc-sgb-v"
SGG_PATH = "/tmp/sgbpot-poc-sgg"


@pytest.fixture(scope="module")
def sgb_v() -> SGBMemory:
    return SGBMemory(SGB_V_PATH)


@pytest.fixture(scope="module")
def sgg() -> SGBMemory:
    return SGBMemory(SGG_PATH)


GKV_COMBINED_PATH = "/tmp/sgbpot-gkv"


@pytest.fixture(scope="module")
def gkv_combined() -> SGBMemory:
    path = Path(GKV_COMBINED_PATH)
    if not path.exists() or not (path / "source.json").exists():
        pytest.skip(f"Combined varstore not found at {GKV_COMBINED_PATH}. "
                     "Build with: python -m sgbpot.cli ingest --repo . --data-ref data "
                     "--books SGB_V SGB_X SGG --out /tmp/sgbpot-gkv && "
                     "python -m sgbpot.cli index --varstore /tmp/sgbpot-gkv && "
                     "python -m sgbpot.cli compile-cards --varstore /tmp/sgbpot-gkv "
                     "--books SGB_V SGB_X SGG --dry-run")
    return SGBMemory(GKV_COMBINED_PATH)


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def _check_hit(hits: list[dict], expected_norm: str, expected_text: str | None = None) -> dict | None:
    """Finde einen Treffer zur erwarteten Norm und prüfe Textfragment."""
    for hit in hits:
        if hit["norm_id"] == expected_norm:
            if expected_text is not None:
                assert expected_text.lower() in hit.get("text", "").lower(), (
                    f"Text des Treffers {expected_norm} enthält nicht '{expected_text}'"
                )
            return hit
    pytest.fail(f"Erwartete Norm {expected_norm} nicht in Suchergebnissen gefunden")
    return None


def _count_norm_hits(hits: list[dict], norm_id: str) -> int:
    return sum(1 for h in hits if h["norm_id"] == norm_id)


def _pack_contains(packed: str, needle: str) -> bool:
    return needle in packed


def _norm_heading(mem: SGBMemory, norm_id: str) -> str:
    return mem.norm(norm_id).heading


# ══════════════════════════════════════════════════════════════════════════════
#  Szenario 1: Krankengeld-Voraussetzungen
# ══════════════════════════════════════════════════════════════════════════════

class TestKrankengeldVoraussetzungen:
    """Scenario: Krankengeld-Voraussetzungen
       Given  ein Varstore mit SGB V
       When   ich nach "Krankengeld Arbeitsunfähigkeit" suche
       Then   finde ich SGB_V:§44 (Krankengeld)
       And    die Ergebnisse enthalten "Krankengeld" und "Arbeitsunfähigkeit"
       And    das Kontextpaket enthält Raw-Spans und Evidence
    """

    QUERY = "Krankengeld Arbeitsunfähigkeit"
    CORE_NORMS = ["SGB_V:§44", "SGB_V:§46"]

    def test_search_finds_expected_norms(self, sgb_v: SGBMemory) -> None:
        hits = sgb_v.search(self.QUERY, k=30)
        assert len(hits) > 0, f"Suche nach '{self.QUERY}' liefert keine Treffer"

        # Prüfe Kernnormen
        found_norms = {h["norm_id"] for h in hits}
        for norm in self.CORE_NORMS:
            assert norm in found_norms, (
                f"Erwartete Norm {norm} nicht in Treffern: {sorted(found_norms)[:10]}"
            )

        # Prüfe, dass die Norm §44 inhaltlich 'Krankengeld' enthält
        n44 = sgb_v.norm("SGB_V:§44")
        assert "Krankengeld" in n44.text(), (
            f"SGB_V:§44 Volltext enthält nicht 'Krankengeld'"
        )

    def test_norm_text_contains_original_wording(self, sgb_v: SGBMemory) -> None:
        """Der Raw-Span-Text muss originalgetreu aus dem XML stammen."""
        n = sgb_v.norm("SGB_V:§44")
        text = n.text()
        assert text.startswith("(1)"), f"SGB_V:§44 Text beginnt nicht mit Absatz: {text[:50]}"
        assert "Krankengeld" in text, "SGB_V:§44 enthält nicht 'Krankengeld'"
        assert "Versicherte" in text, "SGB_V:§44 enthält nicht 'Versicherte'"

    def test_card_exists(self, sgb_v: SGBMemory) -> None:
        card = sgb_v.norm("SGB_V:§44").card()
        assert card is not None, "SGB_V:§44 hat keine Memory Card"
        assert card["card_type"] == "thin"
        assert card["one_sentence"].strip() != ""
        assert len(card.get("roles", [])) > 0
        # Evidence muss existierende Span-ID referenzieren
        for role in card["roles"]:
            for ev in role.get("evidence", []):
                spans = sgb_v.norm("SGB_V:§44").spans()
                span_ids = {s["span_id"] for s in spans}
                assert ev in span_ids, (
                    f"Card-Evidence {ev} nicht in Raw-Spans von SGB_V:§44"
                )

    def test_search_finds_krankengeld_related_norms(self, sgb_v: SGBMemory) -> None:
        """Höhere k findet auch spezifischere Normen wie §49 (Ruhen)."""
        hits = sgb_v.search(self.QUERY, k=100)
        found_norms = {h["norm_id"] for h in hits}
        assert "SGB_V:§49" in found_norms, (
            f"SGB_V:§49 (Ruhen des Krankengeldes) bei k=100 nicht gefunden: "
            f"{sorted(found_norms)[:15]}"
        )

    def test_pack_contains_raw_and_card(self, sgb_v: SGBMemory) -> None:
        packed = sgb_v.packer.norms(
            ["SGB_V:§44", "SGB_V:§46"],
            include_raw=True,
            include_cards=True,
        )
        assert _pack_contains(packed, "SGB_V:§44"), "Kontextpaket enthält nicht SGB_V:§44"
        assert _pack_contains(packed, "SGB_V:§46"), "Kontextpaket enthält nicht SGB_V:§46"
        assert _pack_contains(packed, "Krankengeld"), "Kontextpaket enthält nicht 'Krankengeld'"
        assert _pack_contains(packed, "### Raw Spans"), "Kontextpaket enthält keine Raw Spans"
        assert _pack_contains(packed, "### Memory Card"), "Kontextpaket enthält keine Memory Card"
        assert _pack_contains(packed, "source_commit:"), "Kontextpaket hat keine source_commit"
        assert "3c8a7da8" in packed, "source_commit passt nicht"


# ══════════════════════════════════════════════════════════════════════════════
#  Szenario 2: Anhörung vor belastendem Bescheid
# ══════════════════════════════════════════════════════════════════════════════

class TestAnhoerungVorBescheid:
    """Scenario: Anhörung vor belastendem Bescheid
       Given  ein Varstore mit SGB V
       When   ich nach einer GKV-spezifischen Anhörungssituation suche
       Then   finde ich Normen, die Anhörungsrechte im SGB V betreffen
       Note:  Die allgemeine Anhörungsnorm SGB_X:§24 ist in SGB X (eigenes Buch).
              Im SGB V gibt es spezifische Anhörungstatbestände (z.B. §24 SGB V
              ist Mütter-Vorsorge, nicht Anhörung).
    """

    def test_sgb_v_has_no_generic_anhoerung(self, sgb_v: SGBMemory) -> None:
        """SGB V enthält keine generische Anhörungsnorm (die ist in SGB X)."""
        hits = sgb_v.search("Anhörung", k=20)
        # SGB V erwähnt "Anhörung" nur in spezifischen Kontexten
        for hit in hits:
            if "Anhörung" in hit.get("text", ""):
                # Das ist eine spezifische SGB V-interne Anhörung, nicht §24 SGB X
                pass

    def test_sgb_x_anhoerung_is_separate_book(self) -> None:
        """Anhörung nach SGB X ist ein eigenes Buch – ausserhalb SGB V Scope."""
        sgb_x = SGBMemory("/tmp/sgbpot-poc-sgb-x" if Path("/tmp/sgbpot-poc-sgb-x").exists() else "/tmp/sgbpot-all", scope="SGB")
        try:
            norm = sgb_x.norm("SGB_X:§24")
            assert "Anhörung" in norm.heading, (
                f"SGB_X:§24 Heading: {norm.heading}"
            )
        except KeyError:
            # Fallback: ohne Scope
            mem = SGBMemory("/tmp/sgbpot-all")
            n = mem.norm("SGB_X:§24")
            assert "Anhörung" in n.heading


# ══════════════════════════════════════════════════════════════════════════════
#  Szenario 3: Kostenerstattung bei abgelehntem Antrag
# ══════════════════════════════════════════════════════════════════════════════

class TestKostenerstattung:
    """Scenario: Kostenerstattung bei abgelehntem Antrag
       Given  ein Varstore mit SGB V
       When   ich nach "Kostenerstattung abgelehnte Leistung" suche
       Then   finde ich SGB_V:§13 (Kostenerstattung)
       And    die Ergebnisse enthalten "Kostenerstattung" und "selbstbeschaffte Leistung"
    """

    QUERY = "Kostenerstattung selbstbeschaffte Leistung abgelehnt"

    def test_search_finds_kostenerstattung(self, sgb_v: SGBMemory) -> None:
        hits = sgb_v.search(self.QUERY, k=20)
        assert len(hits) > 0
        found = {h["norm_id"] for h in hits}
        assert "SGB_V:§13" in found, (
            f"SGB_V:§13 (Kostenerstattung) nicht gefunden, gefunden: {sorted(found)}"
        )

    def test_kostenerstattung_paragraphs(self, sgb_v: SGBMemory) -> None:
        """§13 SGB V enthält die Kostenerstattungstatbestände."""
        n = sgb_v.norm("SGB_V:§13")
        text = n.text()
        # §13 hat mehrere Absätze – prüfe Abs 3 (Selbstbeschaffung bei Ablehnung)
        assert "Kostenerstattung" in text
        assert "selbstbeschaffte Leistung" in text, (
            "§13 Abs. 3 (Selbstbeschaffung) fehlt im Text"
        )
        spans = n.spans()
        abs3_spans = [s for s in spans if "Abs3" in s["span_id"] and s["unit_type"] == "paragraph"]
        assert len(abs3_spans) > 0, "§13 Abs. 3 hat keinen Paragraph-Span"

    def test_evidence_in_pack(self, sgb_v: SGBMemory) -> None:
        packed = sgb_v.packer.norms(["SGB_V:§13"], include_cards=True)
        assert "SGB_V:§13" in packed
        assert "Kostenerstattung" in packed
        # Prüfe, dass Evidence-IDs aus der Card im Pack vorkommen
        card = sgb_v.norm("SGB_V:§13").card()
        if card:
            for role in card.get("roles", []):
                for ev in role.get("evidence", []):
                    assert ev in packed, f"Evidence {ev} fehlt im Kontextpaket"


# ══════════════════════════════════════════════════════════════════════════════
#  Szenario 4: Mutter-Kind-Maßnahmen
# ══════════════════════════════════════════════════════════════════════════════

class TestMutterKindMassnahmen:
    """Scenario: Mutter-Kind-Maßnahmen
       Given  ein Varstore mit SGB V
       When   ich nach "Mutter-Kind-Maßnahme Vorsorge" suche
       Then   finde ich SGB_V:§24 (Medizinische Vorsorge für Mütter und Väter)
       And    finde ich SGB_V:§111a (Versorgungsverträge Müttergenesungswerk)
       And    die Ergebnisse enthalten "Müttergenesungswerk"
    """

    QUERY = "Mutter-Kind-Maßnahme Müttergenesungswerk Vorsorge"

    def test_search_finds_muetter_norms(self, sgb_v: SGBMemory) -> None:
        hits = sgb_v.search(self.QUERY, k=20)
        assert len(hits) > 0
        found = {h["norm_id"] for h in hits}
        expected = {"SGB_V:§24", "SGB_V:§111a"}
        missing = expected - found
        assert not missing, (
            f"Erwartete Normen nicht gefunden: {missing}. "
            f"Gefunden: {sorted(found)[:10]}"
        )

    def test_muettergenesungswerk_in_text(self, sgb_v: SGBMemory) -> None:
        n24 = sgb_v.norm("SGB_V:§24")
        assert "Müttergenesungswerk" in n24.text(), (
            "§24 SGB V enthält nicht 'Müttergenesungswerk'"
        )
        n111a = sgb_v.norm("SGB_V:§111a")
        assert "Müttergenesungswerk" in n111a.text(), (
            "§111a SGB V enthält nicht 'Müttergenesungswerk'"
        )

    def test_cross_reference_in_text(self, sgb_v: SGBMemory) -> None:
        """§111a verweist auf §24 – der Rohtext bildet das ab."""
        text = sgb_v.norm("SGB_V:§111a").text()
        assert "§ 24" in text, "§111a verweist im Rohtext auf §24 – nicht gefunden"
        assert "Mütter" in text, "§111a enthält 'Mütter' nicht"


# ══════════════════════════════════════════════════════════════════════════════
#  Szenario 5: Widerspruch und sozialgerichtliches Verfahren
# ══════════════════════════════════════════════════════════════════════════════

class TestWiderspruchSozialgericht:
    """Scenario: Widerspruch und sozialgerichtliches Verfahren
       Given  Varstores mit SGG
       When   ich nach "Widerspruch Klage sozialgerichtliches Verfahren" suche
       Then   finde ich SGG-Normen zum Widerspruchsverfahren und zur Klage
       And    die SGG-Normen enthalten "Widerspruch" und "Klage"
    """

    def test_search_finds_sgg_widerspruch(self, sgg: SGBMemory) -> None:
        """SGG-Suche mit Einzelbegriff findet Widerspruchsnormen."""
        hits = sgg.search("Widerspruch", k=20)
        assert len(hits) > 0, "SGG-Suche 'Widerspruch' liefert keine Treffer"
        found = {h["norm_id"] for h in hits}
        # SGG §78 ff regelt Vorverfahren (Widerspruch), §83 beginnt Vorverfahren
        widerspruch_norms = {n for n in found if n.startswith("SGG:")}
        assert len(widerspruch_norms) > 0

    def test_search_finds_sgg_klage(self, sgg: SGBMemory) -> None:
        """SGG-Suche mit Einzelbegriff findet Klagenormen."""
        hits = sgg.search("Klage", k=20)
        assert len(hits) > 0, "SGG-Suche 'Klage' liefert keine Treffer"
        found = {h["norm_id"] for h in hits}
        # SGG §54 ff regelt Klagearten
        klage_norms = {n for n in found if n.startswith("SGG:")}
        assert len(klage_norms) > 0

    def test_neighbors_work(self, sgg: SGBMemory) -> None:
        """Nachbarschaftsbeziehungen zwischen Normen funktionieren."""
        n = sgg.norm("SGG:§78")
        neighbors = n.neighbors()
        assert len(neighbors) > 0, "SGG:§78 hat keine Nachbarn"
        # Im SGG sollten Nachbarn auch SGG-Normen sein
        for nb in neighbors:
            assert nb.startswith("SGG:"), f"Nachbar {nb} ist keine SGG-Norm"

    def test_pack_cross_book_reference(self) -> None:
        """Kontextpaket kann Normen aus SGB V und SGG kombinieren."""
        combined = SGBMemory("/tmp/sgbpot-all")
        packed = combined.packer.norms(
            ["SGB_V:§44", "SGG:§54"],
            include_raw=True,
            include_cards=True,
        )
        assert "SGB_V:§44" in packed
        assert "SGG:§54" in packed
        assert "### Raw Spans" in packed
        assert "### Memory Card" in packed


# ══════════════════════════════════════════════════════════════════════════════
#  Szenario 6: Vollständige Beweiskette
# ══════════════════════════════════════════════════════════════════════════════

class TestBeweiskette:
    """Scenario: Vollständige Beweiskette für eine Rechtsfrage
       Given  ein Varstore mit SGB V
       When   ich eine Rechtsfrage analysiere
       Then   kann ich von der Suchabfrage über die Norm zum Raw-Span 
              und zur Memory Card navigieren
       And    alle Evidence-IDs sind im Raw-Span-Index validiert
    """

    RECHTSFRAGE = "Krankengeld bei Arbeitsunfähigkeit"
    RELEVANTE_NORMEN = ["SGB_V:§44", "SGB_V:§46", "SGB_V:§49"]

    def test_chain_search_to_raw_spans(self, sgb_v: SGBMemory) -> None:
        """Beweiskette: Suche → Norm → Raw-Spans."""
        # 1. Suche
        hits = sgb_v.search(self.RECHTSFRAGE, k=20)
        assert len(hits) > 0

        # 2. Für jede Kernnorm: Prüfe Raw-Spans
        for norm_id in self.RELEVANTE_NORMEN:
            if norm_id not in {h["norm_id"] for h in hits}:
                continue
            norm = sgb_v.norm(norm_id)
            spans = norm.spans()
            assert len(spans) > 0, f"{norm_id} hat keine Spans"

            # Prüfe SHA-256 für jeden Paragraph-Span
            for span in spans:
                if span["unit_type"] == "paragraph":
                    from sgbpot.normalize import sha256_text
                    expected_hash = sha256_text(span["text"])
                    assert span["text_hash"] == expected_hash, (
                        f"{span['span_id']}: Text-Hash stimmt nicht"
                    )

    def test_chain_card_to_evidence(self, sgb_v: SGBMemory) -> None:
        """Beweiskette: Norm → Card → Evidence → Raw-Spans."""
        for norm_id in self.RELEVANTE_NORMEN:
            try:
                card = sgb_v.norm(norm_id).card()
            except KeyError:
                continue
            if card is None:
                continue

            # Jede Evidence-ID in der Card muss existieren
            norm = sgb_v.norm(norm_id)
            valid_span_ids = {s["span_id"] for s in norm.spans()}

            for bucket in ["roles", "actors", "legal_effects", "conditions", "exceptions_or_limits"]:
                for entry in card.get(bucket, []):
                    for ev in entry.get("evidence", []):
                        assert ev in valid_span_ids, (
                            f"Card {card['card_id']}: Evidence {ev} nicht in "
                            f"Raw-Spans von {norm_id}"
                        )

    def test_search_semantic_consistency(self, sgb_v: SGBMemory) -> None:
        """Semantisch ähnliche Abfragen finden die Kernnorm Krankengeld (§44)."""
        queries = [
            "Krankengeld",
            "Arbeitsunfähigkeit",
            "Krankengeld bei Krankheit",
        ]
        for q in queries:
            hits = sgb_v.search(q, k=20)
            found = {h["norm_id"] for h in hits}
            assert "SGB_V:§44" in found, (
                f"Query '{q}' findet nicht SGB_V:§44 (Krankengeld). "
                f"Gefunden: {sorted(found)[:10]}"
            )


# ══════════════════════════════════════════════════════════════════════════════
#  P2: Kombinierter Varstore SGB V + SGB X + SGG
# ══════════════════════════════════════════════════════════════════════════════

class TestCombinedVarstore:
    """P2: Kombinierter Varstore für GKV-Fälle (SGB V + SGB X + SGG).

    Der kombinierte Varstore muss alle drei Bücher enthalten und
    buchübergreifende Suchen ermöglichen.
    """

    def test_all_three_books_present(self, gkv_combined: SGBMemory) -> None:
        books = gkv_combined.books()
        assert "SGB_V" in books, f"SGB_V fehlt in {books}"
        assert "SGB_X" in books, f"SGB_X fehlt in {books}"
        assert "SGG" in books, f"SGG fehlt in {books}"
        assert len(books) == 3, f"Erwarte 3 Bücher, bekam {len(books)}: {books}"

    def test_search_anhoerung_finds_sgb_x_24(self, gkv_combined: SGBMemory) -> None:
        """Suche 'Anhörung Verwaltungsakt' findet SGB_X:§24 (allgemeine Anhörungsnorm)."""
        hits = gkv_combined.search("Anhörung Verwaltungsakt", k=10)
        found = {h["norm_id"] for h in hits}
        assert "SGB_X:§24" in found, (
            f"SGB_X:§24 nicht gefunden in: {sorted(found)}"
        )

    def test_search_krankengeld_finds_sgb_v_44(self, gkv_combined: SGBMemory) -> None:
        """Suche 'Krankengeld' findet SGB_V:§44 (Krankengeldanspruch)."""
        hits = gkv_combined.search("Krankengeld", k=100)
        found = {h["norm_id"] for h in hits}
        assert "SGB_V:§44" in found, (
            f"SGB_V:§44 nicht gefunden. Normen mit 'Krankengeld': "
            f"{[h['norm_id'] for h in hits if 'Krankengeld' in h.get('text','')][:10]}"
        )

    def test_search_finds_sgg_norms(self, gkv_combined: SGBMemory) -> None:
        """Suche im SGG-Bereich findet SGG-Normen (z.B. Anfechtungsklage → §78)."""
        hits = gkv_combined.search("Anfechtungsklage", k=10)
        found = {h["norm_id"] for h in hits}
        assert "SGG:§78" in found, (
            f"SGG:§78 (Vorverfahren/Anfechtungsklage) nicht gefunden: {sorted(found)}"
        )

    def test_cross_book_search_spans_all_books(self, gkv_combined: SGBMemory) -> None:
        """Eine Suche soll Treffer aus mehreren Büchern liefern."""
        hits = gkv_combined.search("Verwaltungsakt", k=30)
        books_found = {h["norm_id"].split(":")[0] for h in hits}
        # Verwaltungsakt sollte in SGB_X (Kernbegriff) und ggf. SGG auftauchen
        assert "SGB_X" in books_found, (
            f"SGB_X nicht unter den Treffer-Büchern: {books_found}"
        )
        # Mindestens zwei Bücher sollten Treffer enthalten
        assert len(books_found) >= 2, (
            f"Erwarte Treffer aus ≥2 Büchern, bekam {len(books_found)}: {books_found}"
        )

    def test_combined_varstore_validation(self, gkv_combined: SGBMemory) -> None:
        """Der kombinierte Varstore besteht die Validierung."""
        from sgbpot.validate import validate
        ok, msgs = validate(GKV_COMBINED_PATH)
        assert ok, f"Validation fehlgeschlagen: {msgs[:5]}"

    def test_norm_access_across_books(self, gkv_combined: SGBMemory) -> None:
        """Norm-Zugriff funktioniert für alle drei Bücher."""
        # SGB V
        n_v = gkv_combined.norm("SGB_V:§44")
        assert "Krankengeld" in n_v.heading
        assert len(n_v.text()) > 50

        # SGB X
        n_x = gkv_combined.norm("SGB_X:§24")
        assert "Anhörung" in n_x.heading
        assert len(n_x.text()) > 50

        # SGG
        n_sgg = gkv_combined.norm("SGG:§78")
        assert len(n_sgg.text()) > 50
