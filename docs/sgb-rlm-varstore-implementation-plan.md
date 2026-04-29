# Umsetzungskonzept: `sgb-rlm-varstore`

Status: Konzept für Branch `rlm` (mit Anmerkungen aus der Umsetzung)
Zielmodell für Umsetzung durch: `GPT-5.3-Codex-Spark`  
Datenbasis: Branch `data` dieses Repositories, gepinnt auf einen konkreten Commit  
Scope: Sozialgesetzbücher SGB I bis SGB XIV, soweit vorhanden, plus SGG als Verfahrens-/Prozessrechts-Kontext

> **Anmerkung (Umsetzung):** Der Proof wurde vollständig umgesetzt. Abweichungen
> sind in den Abschnitten markiert und in `sgb-rlm-varstore/WORKLOG.md`
> dokumentiert.

## 1. Executive Summary

Der ProofOfTechnology baut keine juristische Wissensdatenbank, sondern eine lokale RLM-Variablenschicht über den XML-Daten des `data`-Branches.

Kernentscheidung:

```text
JSONL speichert kanonische Artefakte.
SQLite FTS findet relevante Normen, Karten und Topics.
Python Lazy Objects exponieren RLM-Variablen.
Spark kompiliert kleine, evidenzgebundene Normkarten und Topic-Maps.
Raw-Spans bleiben die einzige Wahrheitsquelle.
```

Das spätere RLM bekommt nicht den Volltext aller SGB-Bücher in den Prompt, sondern ein kleines Manifest und Variablen wie:

```python
SGB
SGG
CARD
TOPIC
IDX
PACK
TRACE
```

Beispiel:

```python
SGB.norm("SGB_X:§24").text()
SGB.norm("SGB_X:§24").card()
SGB.search("Anhörung Verwaltungsakt Beteiligte", k=10)
TOPIC["Mitwirkungspflichten"].core_norms()
PACK.norms(["SGB_X:§24", "SGB_I:§60"], include_cards=True)
```

## 2. Nicht-Ziele

Im ersten Wurf ausdrücklich nicht bauen:

- keine Dolt-Integration
- keine Datalog-, Graph- oder Vektor-Datenbank
- keine bitemporale Rechtsgeschichte
- keine Anspruchsprüfungsmaschine
- keine automatisierte Rechtsberatung
- keine UI
- keine produktive Lizenz-/Mandantenarchitektur
- keine Modellinterpretation ohne Rohtextanker

## 3. Reproduzierbare Datenbasis

Die Umsetzung nutzt den `data`-Branch dieses Repositories. Ein Build muss immer einen fixen Commit pinnen:

```bash
git rev-parse data
```

Der beim Konzept-Review sichtbare lokale Datenstand war:

```text
3c8a7da839fe7d666c17ddd152dbc821d0790f66
```

Dieser Wert ist kein dauerhaft vorgeschriebener Stand, sondern ein Beispiel. Die Implementierung muss den tatsächlich verwendeten Commit in jedes Artefakt schreiben.

Relevante Datenpfade im `data`-Branch:

```text
data/items/sgb_1/...
data/items/sgb_2/...
data/items/sgb_3/...
data/items/sgb_4/...
data/items/sgb_5/...
data/items/sgb_6/...
data/items/sgb_7/...
data/items/sgb_8/...
data/items/sgb_9_2018/...
data/items/sgb_10/...
data/items/sgb_11/...
data/items/sgb_12/...
data/items/sgb_14/...
data/items/sgg/...
```

SGB XIII existiert nach aktuellem Rechtsstand nicht als eigenes Buch; die Discovery darf daher nicht hart `I..XIV` erzwingen, sondern muss vorhandene Bücher aus `config/sgb_books.yaml` und dem Datenbranch validieren.

Wichtige Due-Diligence-Annahme: Archivierungs-Commits sind Datenstände des Archivs, nicht zwingend juristische Inkrafttretenszeitpunkte. Der Proof ignoriert Geltungshistorie und baut genau einen Snapshot.

## 4. Zielstruktur

Die Implementierung soll als isoliertes Proof-Verzeichnis entstehen:

```text
sgb-rlm-varstore/
  pyproject.toml
  README.md

  config/
    sgb_books.yaml
    compiler_prompts/
      norm_card_prompt.md
      deep_card_prompt.md
      topic_prompt.md
      question_archetype_prompt.md

  src/
    sgbpot/
      __init__.py
      cli.py
      ingest_xml.py
      normalize.py
      span_ids.py
      build_index.py
      compile_cards_spark.py
      compile_topics_spark.py
      validate.py
      rlm_env.py
      varstore.py
      packer.py
      schemas.py
      trace.py

  varstore/              # generiert, nicht manuell pflegen
    manifest.json
    source.json
    books.jsonl
    norms.jsonl
    raw_spans.jsonl
    xrefs.jsonl
    cards/
      SGB_I.jsonl
      SGB_II.jsonl
      SGB_III.jsonl
      SGB_IV.jsonl
      SGB_V.jsonl
      SGB_VI.jsonl
      SGB_VII.jsonl
      SGB_VIII.jsonl
      SGB_IX.jsonl
      SGB_X.jsonl
      SGB_XI.jsonl
      SGB_XII.jsonl
      SGB_XIV.jsonl
      SGG.jsonl
    topics.jsonl
    question_archetypes.jsonl
    review_needed.jsonl
    index.sqlite

  examples/
    ask_mitwirkung.py
    ask_anhoerung.py
    ask_verwaltungsakt.py
    ask_bescheid_aufhebung.py
    ask_krankengeld.py

  tests/
    test_span_ids.py
    test_ingest_snapshot.py
    test_cards_have_evidence.py
    test_search.py
    test_topics.py
    test_rlm_env.py
```

`varstore/` ist Build-Output. Große generierte Artefakte sollen erst committed werden, wenn eine separate Entscheidung dazu getroffen wurde. Für den ersten PR reichen Code, Prompts, Schemas, Tests und kleine Fixtures.

## 5. Datenmodell: Raw zuerst, Memory danach

Es gibt zwei strikt getrennte Ebenen:

1. **Raw-Spans**: deterministisch aus XML extrahierter, normalisierter Gesetzestext mit stabilen IDs.
2. **Memory-Cards/Topics**: von Spark erzeugte Navigationshilfen mit Pflicht-Evidence auf Raw-Spans.

Regel:

```text
Memory darf navigieren.
Raw muss belegen.
```

### 5.1 `source.json`

```json
{
  "source_repo": "this-repository",
  "source_branch": "data",
  "source_commit": "<git-sha>",
  "built_at": "<iso-8601>",
  "scope": ["SGB_I", "SGB_II", "SGB_III", "SGB_IV", "SGB_V", "SGB_VI", "SGB_VII", "SGB_VIII", "SGB_IX", "SGB_X", "SGB_XI", "SGB_XII", "SGB_XIV", "SGG"]
}
```

### 5.2 `raw_spans.jsonl`

Pflichtfelder:

```json
{
  "span_id": "SGB_X:§24:Abs1:S1",
  "book_id": "SGB_X",
  "norm_id": "SGB_X:§24",
  "paragraph": "§24",   # normalisiert (kein Leerzeichen), abw. vom Konzept "§ 24"
  "heading": "Anhörung Beteiligter",
  "unit_type": "sentence",
  "path": ["Abs. 1", "Satz 1"],
  "ordinal": 1,
  "text": "Vor Erlass eines Verwaltungsaktes ...",
  "text_hash": "sha256:<hex>",
  "source_commit": "<git-sha>"
}
```

Minimal zulässige `unit_type`-Werte:

```text
norm
paragraph
sentence
number
letter
heading
```

### 5.3 `norms.jsonl`

```json
{
  "norm_id": "SGB_X:§24",
  "book_id": "SGB_X",
  "paragraph": "§24",   # normalisiert (kein Leerzeichen), abw. vom Konzept "§ 24"
  "heading": "Anhörung Beteiligter",
  "span_ids": ["SGB_X:§24:Abs1:S1", "SGB_X:§24:Abs2:S1"],
  "norm_text_hash": "sha256:<hex>",
  "source_commit": "<git-sha>"
}
```

### 5.4 `cards/*.jsonl`

Thin Card für jede Norm:

```json
{
  "card_id": "CARD:SGB_X:§24",
  "card_type": "thin",
  "norm_id": "SGB_X:§24",
  "book_id": "SGB_X",
  "heading": "Anhörung Beteiligter",
  "one_sentence": "Regelt die Anhörung Beteiligter vor belastenden Verwaltungsakten.",
  "roles": [{"role": "Verfahrensnorm", "evidence": ["SGB_X:§24:Abs1:S1"]}],
  "actors": [{"actor": "Beteiligter", "evidence": ["SGB_X:§24:Abs1:S1"]}],
  "legal_effects": [{"text": "Vor bestimmten belastenden Verwaltungsakten ist Gelegenheit zur Äußerung zu geben.", "evidence": ["SGB_X:§24:Abs1:S1"]}],
  "conditions": [{"text": "Erlass eines Verwaltungsakts, der in Rechte eines Beteiligten eingreift.", "evidence": ["SGB_X:§24:Abs1:S1"]}],
  "exceptions_or_limits": [{"text": "Ausnahmen sind in der Norm gesondert zu prüfen.", "evidence": ["SGB_X:§24:Abs2:S1"]}],
  "topic_tags": ["Anhörung", "Verwaltungsverfahren", "Verwaltungsakt"],
  "likely_questions": ["Wann muss vor einem Bescheid angehört werden?"],
  "xref_candidates": [{"raw_ref": "Verwaltungsakt", "target_hint": "SGB_X:§31", "confidence": 0.7}],
  "compiler": {
    "model": "gpt-5.3-codex-spark",
    "prompt_version": "norm-card-v0.1",
    "created_at": "<iso-8601>"
  }
}
```

Deep Cards sind nur für Kernnormen zulässig und müssen `card_type: "deep"` tragen. Sie dürfen zusätzliche Felder enthalten, aber keine Pflicht zur flächendeckenden Erstellung auslösen.

### 5.5 `topics.jsonl`

```json
{
  "topic_id": "TOPIC:Mitwirkungspflichten",
  "label": "Mitwirkungspflichten",
  "description": "Normen und Fragen zur Mitwirkung von Leistungsberechtigten und zu Folgen fehlender Mitwirkung.",
  "core_norms": ["SGB_I:§60", "SGB_I:§61", "SGB_I:§62", "SGB_I:§63", "SGB_I:§64", "SGB_I:§65", "SGB_I:§66"],
  "related_norms": ["SGB_X:§20", "SGB_X:§21", "SGB_X:§24"],
  "book_scope": ["SGB_I", "SGB_X"],
  "likely_questions": ["Welche Unterlagen muss ich vorlegen?"],
  "pitfalls": ["Mitwirkungspflichten sind von ihren Grenzen zu trennen."],
  "evidence": ["SGB_I:§60:Abs1:S1", "SGB_I:§65:Abs1:S1", "SGB_I:§66:Abs1:S1"],
  "compiler": {
    "model": "gpt-5.3-codex-spark",
    "prompt_version": "topic-v0.1",
    "created_at": "<iso-8601>"
  }
}
```

## 6. SQLite-Index

SQLite ist nur Index, nicht kanonische Quelle.

Tabellen:

```sql
books(book_id TEXT PRIMARY KEY, title TEXT, source_commit TEXT);
norms(norm_id TEXT PRIMARY KEY, book_id TEXT, paragraph TEXT, heading TEXT, text_hash TEXT);
spans(span_id TEXT PRIMARY KEY, norm_id TEXT, book_id TEXT, path_json TEXT, unit_type TEXT, text TEXT);
cards(norm_id TEXT PRIMARY KEY, heading TEXT, one_sentence TEXT, roles_json TEXT, topics_json TEXT);
topics(topic_id TEXT PRIMARY KEY, label TEXT, description TEXT, core_norms_json TEXT);
```

FTS:

```sql
spans_fts(span_id, norm_id, book_id, heading, text);
cards_fts(norm_id, heading, one_sentence, topic_tags, likely_questions);
topics_fts(topic_id, label, description, likely_questions);
```

## 7. RLM-Variablen-API

```python
class SGBMemory:
    def books(self) -> list[str]: ...
    def norm(self, norm_id: str) -> "NormVar": ...
    def search(self, query: str, k: int = 20) -> list[dict]: ...
    def topic(self, label: str) -> "TopicVar": ...
    # def pack(...) – NICHT implementiert; stattdessen self.packer.norms(...)

class NormVar:
    def text(self) -> str: ...
    def spans(self) -> list[dict]: ...
    def card(self) -> dict: ...
    def neighbors(self) -> list[str]: ...

class TopicVar:
    def core_norms(self) -> list[str]: ...
    def related_norms(self) -> list[str]: ...
    def cards(self) -> list[dict]: ...
    def pack(self) -> str: ...
```

`rlm_env.py` exponiert:

```python
SGB = SGBMemory("varstore", scope="SGB")
SGG = SGBMemory("varstore", scope="SGG")
CARD = SGB.cards
TOPIC = SGB.topics
IDX = SGB.index
PACK = SGB.packer
TRACE = SGB.trace
```

## 8. Kontextpacker

Der Packer erzeugt auditierbare Textpakete für Subcalls:

```python
ctx = PACK.norms(
    ["SGB_I:§60", "SGB_I:§65", "SGB_I:§66"],
    include_raw=True,
    include_cards=True,
    include_topics=True,
    max_chars=60000,
)
```

Output-Form:

```text
# Kontextpaket: Mitwirkungspflichten

## SGB I § 60 — Angabe von Tatsachen

### Raw Spans
[SGB_I:§60:Abs1:S1] ...

### Memory Card
one_sentence: ...
roles:
- ... [Evidence: SGB_I:§60:Abs1:S1]
```

Pack-Regeln:

- Raw-Spans vor Memory-Cards.
- Jede Memory-Aussage mit Evidence anzeigen.
- Bei `max_chars` lieber Karten kürzen als Raw-Spans entfernen.
- Ausgabe enthält `source_commit` und Pack-Parameter.

## 9. Spark-Compiler-Vertrag

Spark darf nur strukturierte kleine Artefakte erzeugen. Keine Gutachten.

### 9.1 Batch-Regel

```text
Default: eine Norm rein, eine JSON-Karte raus.
Nur bei sehr kurzen Normen: 5 bis 10 Normen pro Batch.
Lange Normen: chunked compilation mit finaler Merge-Validierung.
```

### 9.2 Prompt-Invarianten

Jeder Compiler-Prompt muss enthalten:

```text
- Nutze ausschließlich bereitgestellte Spans.
- Erfinde keine Normen, Absätze oder Span-IDs.
- Jede Rolle, Voraussetzung, Rechtsfolge, Ausnahme und Frage braucht Evidence.
- Wenn der Text etwas nicht trägt, lass es weg.
- Keine Rechtsberatung.
- Keine finale Auslegung.
- Nur valides JSON nach Schema ausgeben.
```

### 9.3 Retry-Regeln

- Nicht parsebares JSON: einmal Reparaturprompt mit Fehlermeldung.
- Ungültige Evidence: einmal Reparaturprompt mit erlaubten Span-IDs.
- Danach nach `review_needed.jsonl`, nicht stillschweigend übernehmen.

### 9.4 Modellverfügbarkeit

Die Implementierung muss den Modellnamen konfigurierbar halten. Wenn `gpt-5.3-codex-spark` im konkreten Lauf nicht verfügbar ist, darf der Compiler trockenlaufen oder mit einem kompatiblen JSON-LLM ersetzt werden. Artefakte müssen den real verwendeten Modellnamen protokollieren.

## 10. Pipeline und CLI

Minimaler Ablauf:

```bash
python -m sgbpot.cli ingest \
  --repo . \
  --data-ref data \          # abweichend: Flag heißt --data-ref, nicht --data-branch
  --out sgb-rlm-varstore/varstore

python -m sgbpot.cli index \
  --varstore sgb-rlm-varstore/varstore

python -m sgbpot.cli compile-cards \
  --varstore sgb-rlm-varstore/varstore \
  --model gpt-5.3-codex-spark \
  --books SGB_I SGB_X SGB_V

python -m sgbpot.cli compile-topics \
  --varstore sgb-rlm-varstore/varstore \
  --model gpt-5.3-codex-spark

python -m sgbpot.cli validate \
  --varstore sgb-rlm-varstore/varstore

python sgb-rlm-varstore/examples/ask_mitwirkung.py
```

Für vollständigen Umfang:

```bash
python -m sgbpot.cli compile-cards \
  --varstore sgb-rlm-varstore/varstore \
  --model gpt-5.3-codex-spark \
  --books ALL
```

## 11. Umsetzungsschritte für Spark

Spark soll in kleinen, reviewbaren Schritten arbeiten:

1. Projektgerüst unter `sgb-rlm-varstore/` anlegen.
2. `config/sgb_books.yaml` mit SGB I-XII, SGB XIV und SGG erstellen; SGB XIII als bewusst abwesend dokumentieren.
3. XML-Discovery gegen `data`-Branch implementieren.
4. Deterministischen Ingest bauen: `books.jsonl`, `norms.jsonl`, `raw_spans.jsonl`, `source.json`.
5. Stabile ID- und Hash-Funktionen testen.
6. SQLite-Index und FTS bauen.
7. Lazy-Varstore und RLM-API implementieren.
8. Kontextpacker implementieren.
9. JSON-Schemas/Pydantic-Modelle für Cards und Topics implementieren.
10. Compiler-Prompts schreiben.
11. Spark-Client als austauschbaren Adapter bauen.
12. `compile-cards` zunächst auf 20 Fixture-Normen begrenzen.
13. Validatoren hart schalten.
14. Topic-Compiler aus validierten Thin Cards erstellen.
15. Fünf Demo-Fragen mit Grounding ausgeben.
16. Vollständigen Lauf erst nach grünen Fixtures und Review starten.

## 12. Validierung und QA-Gates

Hard Gates:

1. JSONL-Zeilen sind parsebar.
2. `source_commit` ist überall identisch und nicht leer.
3. Jede `norm_id` referenziert ein vorhandenes Buch.
4. Jede `span_id` ist eindeutig.
5. Jeder `text_hash` entspricht dem normalisierten Text.
6. Jede Card referenziert eine existierende Norm.
7. Jede Evidence-ID existiert.
8. Jede Rolle hat Evidence.
9. Jede Rechtsfolge hat Evidence.
10. Jede Voraussetzung hat Evidence.
11. `one_sentence` ist nicht leer.
12. `topic_tags` enthalten keine leeren Strings.
13. Topics referenzieren nur vorhandene Normen.
14. Rohtext wird durch Modellschritte nie verändert.
15. Demoantworten enthalten Span-IDs für alle wesentlichen Rechtsaussagen.

Soft Gates / Review:

- `xref_candidates.target_hint` mit niedriger Confidence nach `review_needed.jsonl`.
- Unerwartete Normzahl pro Buch reporten.
- Sehr lange Normen chunked und separat prüfen.
- Stichprobe je Buch: Rohtext gegen XML-Extraktion vergleichen.

## 13. Abnahmetests

Technische Mindestabnahme:

```text
coverage_raw >= 0.98 für konfigurierte vorhandene Normen
coverage_cards >= 0.95 nach vollständigem Card-Lauf
evidence_validity = 1.00
search_success: Top-10 enthält erwartete Kernnormen für Testfragen
topic_success: definierte Topics enthalten erwartete Kernnormen
answer_grounding: Demoantworten nennen Span-IDs
```

Fünf Pflichtfragen:

1. Welche Mitwirkungspflichten bestehen bei einem Sozialleistungsantrag?
2. Wann ist eine Anhörung vor einem belastenden Bescheid erforderlich?
3. Was ist ein Verwaltungsakt?
4. Welche Normen sind bei Rücknahme/Aufhebung eines Bescheids relevant?
5. Welche Normen sind bei Krankengeld relevant?

Erwartete Kernnormen als Test-Orakel:

```text
Mitwirkung: SGB_I:§60 bis SGB_I:§66, plus SGB_X:§20, §21, §24
Anhörung: SGB_X:§24
Verwaltungsakt: SGB_X:§31
Rücknahme/Aufhebung: SGB_X:§44, §45, §48, §50
Krankengeld: SGB_V:§44 ff. und angrenzende Normen nach Suchtreffer/Stichprobe
Sozialgerichtlicher Kontext: SGG-Normen nur als Verfahrenskontext, nicht als SGB-Buch
```

## 14. Traceability

Jeder Build erzeugt eine maschinenlesbare Trace:

```json
{
  "run_id": "<uuid>",
  "source_commit": "<git-sha>",
  "command": "compile-cards",
  "model": "gpt-5.3-codex-spark",
  "prompt_version": "norm-card-v0.1",
  "input_hash": "sha256:<hex>",
  "output_hash": "sha256:<hex>",
  "validation_status": "passed"
}
```

Keine generierte Memory-Aussage darf ohne Rückweg zu `raw_spans.jsonl` akzeptiert werden.

## 15. Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
| --- | --- |
| Modell halluziniert Span-IDs | harte Evidence-Validierung, Retry, sonst `review_needed.jsonl` |
| Modell schreibt juristische Auslegung statt Navigation | Prompts und Schema begrenzen Output; Deep Cards nur Kernnormen |
| SGB-Datenpfade ändern sich | Discovery über `config/sgb_books.yaml` plus `toc.xml`/Abkürzung, nicht nur Pfadnamen |
| Archivcommit != Rechtsgeltung | Snapshot klar kennzeichnen, keine Geltungshistorie behaupten |
| Große Artefakte blähen Repo | `varstore/` als Build-Output behandeln; Commit-Policy separat entscheiden |
| Spark nicht verfügbar | Modelladapter konfigurierbar; Dry-Run/Fixture-Compiler möglich |
| Rohtext-Normalisierung verändert Sinn | Hashes, Stichproben, keine Modellmodifikation von Raw-Spans |

## 16. Definition of Done für den Proof

Der Proof gilt als fertig, wenn:

- Ingest für SGB-Bücher und SGG aus einem gepinnten `data`-Commit läuft.
- `SGB.norm("SGB_X:§24").text()` funktioniert.
- SQLite-FTS relevante Normen findet.
- Spark mindestens 20 Fixture-Normen zu gültigen Thin Cards kompiliert.
- Alle Evidence-IDs validiert sind.
- Topics für Mitwirkung, Anhörung, Verwaltungsakt, Rücknahme/Aufhebung und Krankengeld existieren.
- `PACK.norms(...)` auditierbare Kontextpakete erzeugt.
- Fünf Demoantworten Rohtextanker nennen.
- `python -m sgbpot.cli validate` grün ist.

## 17. Arbeitsprinzip für Folgeumsetzung

Für die Umsetzung gilt:

```text
Erst deterministische Rohtextpipeline.
Dann Suchindex.
Dann RLM-API.
Dann kleine Spark-Fixtures.
Dann Validatoren härten.
Dann Topics.
Dann Skalierung auf alle Bücher.
```

Jede Abweichung, die Interpretation, Datenbankkomplexität oder UI vorzieht, ist für den ersten Wurf abzulehnen.
