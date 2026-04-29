# Follow-Up Prompt: sgb-rlm-varstore – Reparatur & Vervollständigung

## Auftrag

Setze die Arbeit am `sgb-rlm-varstore` fort. Der Proof-of-Technology ist weitgehend
vollständig: Alle 28 Tests grün, SGB-V- und SGG-Varstore gebaut und validiert,
BDD-Szenarien für GKV-Fälle vorhanden.

Es gibt aber **10 offene Probleme**, die vor produktiver Nutzung behoben werden müssen.
Arbeite sie in der angegebenen Reihenfolge ab. Jeder Fix braucht Tests.

## Kontext einlesen

Starte einen Ralph-Loop (`ralph_start`) und lies vor Arbeitsbeginn:

1. `sgb-rlm-varstore/WORKLOG.md` – vollständige Abweichungsdokumentation
2. `docs/codex-spark-implementation-prompt.md` – ursprünglicher Bauplan
3. `docs/sgb-rlm-varstore-implementation-plan.md` – Konzept mit Anmerkungen
4. `sgb-rlm-varstore/tests/test_poc_gkv_scenarios.py` – existierende BDD-Szenarien
5. `sgb-rlm-varstore/src/sgbpot/ingest_xml.py` – Ingest (enthält Satzsplitter)
6. `sgb-rlm-varstore/src/sgbpot/build_index.py` – FTS5-Index und Suche
7. `sgb-rlm-varstore/src/sgbpot/varstore.py` – RLM-Klassen

## Checkliste (Priorität absteigend)

### 🔴 P1: Satzsplitter juristisch korrigieren
**Problem:** `ingest_xml.py`, Funktion `_norm_unit_sentences()` splittet mit
`(?<=[\.\?\!])\s+`. Das zerbricht Sätze an juristischen Abkürzungen wie
`Abs.`, `Nr.`, `S.`, `Absatz`, `Art.`, `Buchst.`, `Nr.`, `lit.`, `Halbs.`,
`Alt.`, `Var.`, `i.V.m.`, `i.S.d.`, `i.S.v.`, `e.V.`, `m.W.v.`, `m.w.N.`,
`a.F.`, `n.F.`, etc.

**Beispiel aus §24 Abs. 1 SGB V:**
```
Aktuell: [S1] „(1) Versicherte haben unter den in § 23 Abs."
         [S2] „1 genannten Voraussetzungen …"         ← falsch!
Ziel:    [S1] „(1) Versicherte haben unter den in § 23 Abs. 1 genannten …"
```

**Anforderungen:**
- Ignoriere Satzzeichen nach bekannter Abkürzungsliste
- Splitte nur nach `. ` (Punkt+Leerzeichen), `! `, `? ` wenn das Wort vor
  dem Punkt KEINE bekannte Abkürzung ist
- Abkürzungsliste muss erweiterbar sein (Konfiguration oder Set)
- Test: `_norm_unit_sentences("gemäß § 23 Abs. 1")` → `["gemäß § 23 Abs. 1"]`
  (KEIN Split nach "1")
- Test: `_norm_unit_sentences("Satz 1 gilt. Satz 2 gilt.")` →
  `["Satz 1 gilt.", "Satz 2 gilt."]`
- Test: Alle bisherigen 28 Tests bleiben grün

### 🔴 P2: Kombinierten Varstore SGB V + SGB X + SGG bauen
**Problem:** GKV-Fälle brauchen SGB V (Leistungsrecht), SGB X (Verwaltungsverfahren,
Anhörung §24, Rücknahme §44/45/48) und SGG (sozialgerichtliches Verfahren).
Aktuell gibt es nur getrennte Varstores.

**Anforderungen:**
- `ingest` muss `--books SGB_V SGB_X SGG` sauber verarbeiten
- Ein combined varstore unter `/tmp/sgbpot-gkv` wird gebaut und validiert
- Test: Suche "Anhörung Verwaltungsakt" findet SGB_X:§24
- Test: Suche "Krankengeld" findet SGB_V:§44
- Test: Suche "Widerspruch" findet SGG:§78

### 🟡 P3: Topics semantisch gruppieren
**Problem:** Dry-Run erzeugt 670 Topics für 670 Cards (1:1). Topics sollen
thematisch gruppiert werden: Ein Topic "Mitwirkungspflichten" soll 7+ Normen
enthalten, nicht eine einzelne.

**Anforderungen:**
- Topics nach überlappenden `topic_tags`, `book_scope` und Heading-Ähnlichkeit
  zusammenführen
- Einmalige Normen (ohne thematische Verwandte) bleiben Einzeltopics
- Beschreibung wird aus den zusammengeführten Normen generiert
- Test: Nach Gruppierung gibt es weniger Topics als Cards
- Test: Ein Topic kann mehrere core_norms enthalten

### 🟡 P4: `--all-books` sauber in CLI integrieren
**Problem:** `compile-cards --books ALL` funktioniert per String-Vergleich,
ist undokumentiert und fragil.

**Anforderungen:**
- CLI-Flag `--all-books` (store_true) als Alternative zu `--books`
- Wenn `--all-books` gesetzt, werden alle Bücher ohne Filterung kompiliert
- `--books` und `--all-books` schließen sich gegenseitig aus
- In `sgb-rlm-varstore/README.md` dokumentieren

### 🟡 P5: `SGBMemory.norm()` Scope-Prüfung nachrüsten
**Problem:** `SGG.norm("SGB_V:§44")` funktioniert, obwohl SGG-Scope keine
SGB-Normen enthalten sollte.

**Anforderungen:**
- `norm()` prüft, ob die angefragte Norm zum Scope (SGB/SGG) passt
- Wirft `KeyError` bei Scope-Verletzung
- Ohne Scope (`scope=None`) weiterhin alle Normen erlaubt
- Test: `SGBMemory(scope="SGG").norm("SGB_V:§44")` → KeyError
- Test: `SGBMemory(scope=None).norm("SGB_V:§44")` → Erfolg

### 🟢 P6: Suche auf Paragraph-Ebene priorisieren
**Problem:** Suchergebnisse enthalten sowohl vollständige Paragraph-Spans
als auch fragmentierte Sentence-Spans. Das verdoppelt Ergebnisse und zeigt
Fragmente.

**Anforderungen:**
- `search()` kann optional `unit_type="paragraph"` filtern
- Default: weiterhin alle unit_types (Rückwärtskompatibilität)
- `search()` dedupliziert nach norm_id, bevorzugt paragraph-Spans
- Test: deduplizierte Ergebnisse haben weniger Einträge als Roh-Treffer

### 🟢 P7: LIKE-Fallback-Test schreiben
**Problem:** Alle Tests laufen mit FTS5. Der LIKE-Pfad ist ungetestet.

**Anforderungen:**
- Test mit `build_index` ohne FTS5 (SIMULATION)
- Oder: Index ohne FTS5 bauen und search testen
- Fallback-Test für `search()` mit LIKE

## Validierung

Nach jedem abgeschlossenen Fix:

1. `python -m pytest` – alle Tests grün (bestehende + neue)
2. `git diff --check` – keine Whitespace-Probleme
3. Falls Varstore-Struktur geändert: `python -m sgbpot.cli validate --varstore /tmp/sgbpot-poc-sgb-v`
4. `cd /work/gesetze-im-internet && go test ./...` – Go-Tests grün

## Abschluss

Nach Erledigung aller Punkte Abschlussbericht mit:

```text
Fixed:
- P1: Satzsplitter: …
- P2: Combined varstore: …

Validation:
- python -m pytest → N/N passed
- …

Open:
- …
```
