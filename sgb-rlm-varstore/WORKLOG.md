# Worklog & Abweichungen vom Konzept

## Übersicht

Dieses Dokument fasst zusammen, was bei der Umsetzung von `sgb-rlm-varstore`
gegenüber dem Konzept (`docs/sgb-rlm-varstore-implementation-plan.md`) abweicht,
und erklärt, wie mit dem RLM-System gearbeitet wird.

---

## 1. Worklog – Was passiert ist

| Schritt | Datum | Status |
|---------|-------|--------|
| Projektgerüst angelegt (pyproject.toml, README, .gitignore) | – | ✅ |
| `config/sgb_books.yaml` mit SGB I–XII, XIV, SGG | – | ✅ |
| Normalisierung (`normalize.py`, `span_ids.py`) | – | ✅ |
| Tests für IDs (`test_span_ids.py`) | – | ✅ |
| XML-Ingest (`ingest_xml.py`) mit Fixture- und Branch-Modus | – | ✅ |
| Tests für Ingest (`test_ingest_xml.py`) | – | ✅ |
| SQLite-Index mit FTS5 (`build_index.py`) | – | ✅ |
| Tests für Suche (`test_build_index.py`) | – | ✅ |
| Varstore/RLM-Klassen (`varstore.py`) | – | ✅ |
| Globale RLM-Variablen (`rlm_env.py`) | – | ✅ |
| Kontextpacker (`packer.py`) | – | ✅ |
| Validator (`validate.py`) mit 10+ Hard Checks | – | ✅ |
| Test Validator (`test_validate.py`) | – | ✅ |
| Dry-Run-Compiler für Cards (`compile_cards_spark.py`) | – | ✅ |
| Dry-Run-Compiler für Topics (`compile_topics_spark.py`) | – | ✅ |
| Compiler-Prompts (4 Dateien in `config/compiler_prompts/`) | – | ✅ |
| Trace-Modul (`trace.py`) | – | ✅ |
| CLI mit 7 Befehlen (`cli.py`) | – | ✅ |
| 5 Beispiele (`examples/`) | – | ✅ |
| README geschrieben | – | ✅ |
| Scope-Filter (SGB/SGG) in `search()` | 2026-04-29 | ✅ |
| CLI-Fehlermeldungen verbessert | 2026-04-29 | ✅ |
| `--dry-run` default `False` | 2026-04-29 | ✅ |
| SGB-V-Vollvarstore gebaut (670/14706/670/647) | 2026-04-29 | ✅ |
| SHA-256-Wortlauttreue verifiziert (XML ⟷ Varstore) | 2026-04-29 | ✅ |
| Vollständige Akzeptanzkriterien getestet | 2026-04-29 | ✅ |

---

## 2. Abweichungen vom Konzept

Das Konzept (`docs/sgb-rlm-varstore-implementation-plan.md`) wurde großteils
exakt umgesetzt. Folgende Abweichungen gibt es:

### 2.1 Optional generierte Dateien (nicht erstellt)

Das Konzept listet in §4 unter `varstore/` folgende Dateien, die **nicht**
erzeugt werden:

| Geplant | Tatsächlich | Begründung |
|---------|-------------|------------|
| `varstore/manifest.json` | — | `source.json` übernimmt diese Rolle |
| `varstore/xrefs.jsonl` | — | Kein Xref-Extraktor implementiert (Proof) |
| `varstore/question_archetypes.jsonl` | — | Nicht vom Dry-Run-Compiler erzeugt |
| `varstore/review_needed.jsonl` | — | Wird erst bei echtem Modellbetrieb relevant |

Diese Dateien sind alle als "generiert, nicht manuell pflegen" markiert und
nicht Teil der Akzeptanzkriterien.

### 2.2 Test-Dateinamen

| Geplant | Tatsächlich |
|---------|-------------|
| `test_ingest_snapshot.py` | `test_ingest_xml.py` |
| `test_cards_have_evidence.py` | Inhalt in `test_validate.py` |
| `test_search.py` | Inhalt in `test_build_index.py` |
| `test_topics.py` | Kein separates File; Coverage durch Integrationstests |

Die Testabdeckung ist gleichwertig, die Benennung wurde pragmatisch
gewählt.

### 2.3 `SGBMemory.pack()` nicht implementiert

**Konzept §7**: `SGBMemory.pack(ids, include_cards=True) -> str`

**Tatsächlich**: Die Methode existiert nicht auf `SGBMemory`. Stattdessen
wird der Packer über `SGBMemory.packer.norms(ids, ...)` oder direkt über
`PACK.norms(ids, ...)` aufgerufen.

Äquivalenter Code:
```python
# Konzept (nicht implementiert):
mem.pack(["SGB_V:§24"])

# Tatsächlich (beide funktionieren):
PACK.norms(["SGB_V:§24"])
mem.packer.norms(["SGB_V:§24"])
```

### 2.4 `paragraph`-Feld ohne Leerzeichen

**Konzept §5.2/5.3**: `"paragraph": "§ 24"` (mit Leerzeichen)

**Tatsächlich**: `"paragraph": "§24"` (Leerzeichen entfernt durch
`normalize_paragraph_id()`)

Die Konsistenz ist intern gewahrt – alle Abfragen und Span-IDs verwenden
die normalisierte Form.

### 2.5 Dry-Run Cards sind "dünner" als im Konzept

**Konzept §5.4**: Cards mit befüllten `actors`, `conditions`, `legal_effects`

**Tatsächlich** (Dry-Run):
```json
{
  "one_sentence": "Navigationskarte zu SGB_V:§24: ...",
  "roles": [{"role": "Norm", "evidence": ["SGB_V:§24:Abs1"]}],
  "actors": [],
  "conditions": [],
  "legal_effects": [],
  "exceptions_or_limits": []
}
```

**Begründung**: Der Dry-Run-Compiler erzeugt minimale gültige Thin Cards
aus Heading und erstem Span. Semantisch befüllte Cards sind Aufgabe des
echten Spark-Modellmodus (§12.2 im Prompt). Der Validator prüft, dass
alle befüllten Felder Evidence haben, lässt aber leere Listen zu.

### 2.6 CLI-Flag `--data-ref` statt `--data-branch`

**Konzept §10**: `python -m sgbpot.cli ingest --data-branch data`

**Tatsächlich**: `python -m sgbpot.cli ingest --data-ref data`

Der Name wurde geändert, weil `data-ref` präziser ist (es kann ein
Branch, Tag oder Commit sein).

### 2.7 `--books ALL` nicht dokumentiert

Die Option `--books ALL` für `compile-cards` existiert in der Implementierung
(Check in `_write_book_cards`), ist aber nicht in der CLI-Hilfe oder README
dokumentiert. Der Mechanismus ist fragil (String-Vergleich) und sollte bei
echtem Modellbetrieb durch explizite Buchlisten ersetzt werden.

### 2.8 QA-Gate 12 (`topic_tags` leer) nicht explizit geprüft

Der Validator prüft nicht, ob `topic_tags` leere Strings enthält. Die
Dry-Run-Cards erzeugen nur nicht-leere Tags, daher besteht kein
unmittelbarer Handlungsbedarf.

### 2.9 `question_archetype_prompt.md` wird nicht aufgerufen

Die Prompt-Datei existiert in `config/compiler_prompts/`, wird aber von
keinem Compiler-Modul referenziert. Sie ist für die Zukunft vorgesehen.

---

## 3. PoC – BDD-Szenarien für GKV-Fälle (April 2026)

### 3.1 Was wurde gemacht

6 BDD-Szenarien mit 20 Tests (`tests/test_poc_gkv_scenarios.py`):

1. **Krankengeld-Voraussetzungen** – Suche `"Krankengeld Arbeitsunfähigkeit"` findet §44, §46; §49 bei höherem k.
2. **Anhörung vor belastendem Bescheid** – SGB V enthält keine generische Anhörungsnorm (die ist SGB X:§24).
3. **Kostenerstattung bei abgelehntem Antrag** – Suche `"Kostenerstattung selbstbeschaffte Leistung"` findet §13.
4. **Mutter-Kind-Maßnahmen** – Suche `"Mütter Vorsorge"` findet §24, §111a.
5. **Widerspruch und sozialgerichtliches Verfahren** – SGG-Suche findet Widerspruchs- und Klagenormen.
6. **Vollständige Beweiskette** – Von der Suchabfrage über Raw-Spans zur Memory Card mit SHA-256-Validierung.

### 3.2 Änderungen am Code durch den PoC

| Datei | Änderung |
|-------|----------|
| `src/sgbpot/build_index.py` | FTS5-Query-Escaping: Bindestriche → Leerzeichen, AND statt OR für präzise Suche, Fallback zu OR bei < limit/2 Treffern. `ORDER BY f.rank` über Subquery zur korrekten Relevanz-Rankings |
| `tests/test_poc_gkv_scenarios.py` | Neu: 20 BDD-Tests für 6 GKV-Szenarien |

### 3.3 PoC-Ergebnis

**Was das RLM heute kann:**

- ✅ Deterministische Rohtext-Pipeline (XML → JSONL → SQLite) ist wortlauttreu (SHA-256 verifiziert)
- ✅ FTS5-Suche findet Kernnormen zu GKV-Fragen zuverlässig
- ✅ Memory Cards mit Evidence-Bindung werden erzeugt und validiert
- ✅ Kontextpacker erzeugt auditierbare Textpakete für LLM-Subcalls
- ✅ SGB-V- und SGG-Varstore sind eigenständig und kombinierbar
- ✅ Beweiskette: Suche → Norm → Raw-Spans → Card → Evidence ist durchgängig validiert

**Was fehlt (für produktiven Einsatz):**

- ❌ Echter Modellmodus (Spark/LLM) für semantisch befüllte Cards und Topics
- ❌ SGB X als drittes Buch für vollständige Verwaltungsverfahrens-Perspektive
- ❌ Automatische Topic-Zusammenführung (aktuell 1 Topic pro Norm im Dry-Run)
- ❌ Keine Geltungshistorie oder Fassungsvergleiche
- ❌ Keine GUI/Web-Interface

---

## 3. Arbeiten mit dem RLM-System

### 3.1 Grundprinzip

```
XML (data-Branch)
    ↓ ingest
JSONL-Artefakte (source.json, books.jsonl, norms.jsonl, raw_spans.jsonl)
    ↓ index
SQLite (FTS5-Suchindex)
    ↓ compile-cards (dry-run oder mit Modell)
Cards (Navigation)
    ↓ compile-topics
Topics (Querschnittsthemen)
```

**Zwei Ebenen, strikt getrennt:**
- **Raw Spans** = deterministisch aus XML extrahierter Gesetzestext (die Wahrheit)
- **Memory Cards/Topics** = Navigationshilfen, die auf Raw Spans verweisen müssen

### 3.2 Einen Varstore bauen

```bash
# Minimal (nur Fixture)
cd sgb-rlm-varstore
python -m sgbpot.cli ingest --fixture tests/fixtures/mini_sgb_x.xml --out /tmp/mein-varstore
python -m sgbpot.cli index --varstore /tmp/mein-varstore
python -m sgbpot.cli compile-cards --varstore /tmp/mein-varstore --books SGB_X --dry-run
python -m sgbpot.cli compile-topics --varstore /tmp/mein-varstore --dry-run
python -m sgbpot.cli validate --varstore /tmp/mein-varstore

# SGB V aus data-Branch
cd sgb-rlm-varstore
python -m sgbpot.cli ingest --repo . --data-ref data --books SGB_V --out varstore
python -m sgbpot.cli index --varstore varstore
python -m sgbpot.cli compile-cards --varstore varstore --books SGB_V --dry-run
python -m sgbpot.cli compile-topics --varstore varstore --dry-run
python -m sgbpot.cli validate --varstore varstore

# Alle Bücher
python -m sgbpot.cli ingest --repo . --data-ref data --out /tmp/alle-bücher
# (dauert länger – 14 Bücher, ~3.500 Normen)
```

### 3.3 Python-API – Die RLM-Variablen

```python
from sgbpot.rlm_env import SGB, SGG, CARD, TOPIC, IDX, PACK, TRACE

# Bücher auflisten
SGB.books()                    # ['SGB_I', 'SGB_II', ..., 'SGB_XIV']
SGG.books()                    # ['SGG']

# Norm abfragen
n = SGB.norm("SGB_V:§24")
n.text()                       # Volltext (alle Absätze)
n.spans()                      # Liste aller Spans
n.card()                       # Memory Card (oder None)
n.heading                      # Überschrift
n.neighbors()                  # Vorherige/nächste Norm im selben Buch

# Suchen
SGB.search("Mütter Vorsorge", k=10)

# Topic abfragen
t = TOPIC["Medizinische Vorsorge für Mütter und Väter"]
t.core_norms()                 # Normen-IDs
t.cards()                      # Zugehörige Memory Cards
t.pack()                       # Kontextpaket generieren

# Index direkt nutzen
IDX.search("Anhörung", k=5)

# Kontextpaket für LLM-Subcalls
ctx = PACK.norms(
    ["SGB_V:§24", "SGB_V:§111a"],
    include_raw=True,
    include_cards=True,
    include_topics=False,
    max_chars=60000,
)
print(ctx)
# → Enthält Raw-Spans + Memory Cards als Text
```

### 3.4 CLI-Befehle

```bash
# ingest     – XML extrahieren
python -m sgbpot.cli ingest --fixture ... --out ...
python -m sgbpot.cli ingest --repo . --data-ref data --books SGB_V --out varstore

# index      – SQLite-FTS-Index bauen
python -m sgbpot.cli index --varstore varstore

# compile-cards – Cards generieren (dry-run oder mit Modell)
python -m sgbpot.cli compile-cards --varstore varstore --books SGB_V --dry-run

# compile-topics – Topics generieren
python -m sgbpot.cli compile-topics --varstore varstore --dry-run

# validate   – Alle Hard Checks laufen lassen
python -m sgbpot.cli validate --varstore varstore

# search     – Volltextsuche
python -m sgbpot.cli search --varstore varstore --query "Mütter" --k 5

# inspect    – Normdetails anzeigen
python -m sgbpot.cli inspect --varstore varstore --norm SGB_V:§24
```

### 3.5 Typischer Arbeitsablauf für ein RLM-Subcall

```python
from sgbpot.rlm_env import SGB, PACK

# 1. Relevante Normen finden
hits = SGB.search("Krankengeld bei Arbeitsunfähigkeit", k=5)
norm_ids = [h["norm_id"] for h in hits]  # ['SGB_V:§44', 'SGB_V:§46', ...]

# 2. Kontextpaket schnüren
kontext = PACK.norms(norm_ids, include_raw=True, include_cards=True)

# 3. Kontext an LLM übergeben (Beispiel)
prompt = f"""Beantworte die Frage basierend auf dem folgenden Kontext.

{kontext}

Frage: Welche Voraussetzungen muss ich für Krankengeld erfüllen?
"""
```

### 3.6 Wichtige Regeln

1. **Raw-Spans sind die Wahrheit** – Cards/Topics dürfen nur navigieren,
   nicht interpretieren. Jede inhaltliche Aussage in Cards braucht Evidence
   (Span-ID).

2. **Keine halluzinierten IDs** – Der Validator prüft, dass jede Evidence-ID
   in `raw_spans.jsonl` existiert.

3. **`one_sentence` nie leer** – Wird vom Validator hart geprüft.

4. **Expliziter Datenstand** – `source.json` protokolliert den exakten
   Commit des `data`-Branch, aus dem gebaut wurde.

5. **Reproduzierbar** – Gleicher Commit + gleicher Code = identische
   Raw-Spans (dank SHA-256-Hashes und deterministischem Ingest).

### 3.7 Ausblick: Echter Modellmodus

Sobald ein LLM-API-Key verfügbar ist, kann der Modellmodus aktiviert werden:

```bash
python -m sgbpot.cli compile-cards \
  --varstore varstore \
  --model gpt-4o \
  --prompt-version norm-card-v0.1
```

Der Adapter ist in `compile_cards_spark.py` vorbereitet und erwartet eine
Implementierung, die:
- Spans + Prompt an das Modell sendet
- Die JSON-Antwort parsed
- Evidence-IDs validiert
- Bei Fehlern nach `review_needed.jsonl` schreibt
