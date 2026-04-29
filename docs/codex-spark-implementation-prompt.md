# Umsetzungsprompt für `GPT-5.3-Codex-Spark`

Kopiere den folgenden Prompt vollständig in Codex-Spark. Er ist absichtlich sehr explizit formuliert, damit ein sehr schnelles, aber weniger planungsstarkes Modell ihn zuverlässig abarbeiten kann.

---

## PROMPT START

Du bist `GPT-5.3-Codex-Spark` und arbeitest als Coding-Agent in diesem Repository auf dem Branch `rlm`.

Deine Aufgabe: Implementiere den ProofOfTechnology `sgb-rlm-varstore` so, dass SGB-Bücher und das SGG aus dem `data`-Branch als lokale RLM-Variablen verfügbar werden.

Wichtig: Du bist schnell, aber sollst nicht kreativ werden. Arbeite exakt nach diesem Plan. Baue zuerst eine kleine, testbare Version. Keine Architektur-Experimente.

## 0. Absolute Regeln

Halte diese Regeln immer ein:

1. Arbeite nur auf Branch `rlm`.
2. Lies zuerst `docs/sgb-rlm-varstore-implementation-plan.md`.
3. Implementiere keine Dolt-, Datalog-, Graph-, RDF-, Vector-DB- oder UI-Lösung.
4. Nutze JSONL als kanonische Speicherung.
5. Nutze SQLite FTS nur als Suchindex.
6. Nutze Python-Lazy-Objekte für die RLM-Variablen.
7. Raw-Spans sind die Wahrheit. Modellgenerierte Cards/Topics sind nur Navigation.
8. Jede Card-/Topic-Aussage mit Inhalt braucht Evidence-Span-IDs.
9. Erfinde keine Normen, keine Paragraphen und keine Span-IDs.
10. Wenn etwas unklar ist, wähle die einfachere Lösung und dokumentiere die Annahme in `sgb-rlm-varstore/README.md`.
11. Commite keine großen generierten `varstore/`-Artefakte, außer kleine Test-Fixtures.
12. Schreibe Tests für jeden Kernbaustein.
13. Nach jedem größeren Schritt: Tests laufen lassen und Fehler sofort beheben.

## 1. Zielzustand

Nach deiner Umsetzung sollen diese Beispiele funktionieren:

```python
from sgbpot.rlm_env import SGB, SGG, CARD, TOPIC, IDX, PACK

SGB.books()
SGB.norm("SGB_X:§24").text()
SGB.norm("SGB_X:§24").spans()
SGB.search("Anhörung Verwaltungsakt Beteiligte", k=10)
PACK.norms(["SGB_X:§24", "SGB_I:§60"], include_cards=True)
```

Der vollständige Produktionslauf mit Spark-Cards darf später erfolgen. Für diese Implementierung reicht:

- deterministischer Ingest,
- SQLite-Index,
- RLM-API,
- Kontextpacker,
- Validator,
- Promptdateien,
- austauschbarer Spark-Adapter,
- kleine Fixture-/Dry-Run-Cards,
- Tests.

## 2. Lege diese Struktur an

Erstelle genau dieses Verzeichnis:

```text
sgb-rlm-varstore/
  pyproject.toml
  README.md
  .gitignore

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

  examples/
    ask_mitwirkung.py
    ask_anhoerung.py
    ask_verwaltungsakt.py
    ask_bescheid_aufhebung.py
    ask_krankengeld.py

  tests/
    fixtures/
      mini_sgb_x.xml
      mini_varstore/
    test_span_ids.py
    test_ingest_xml.py
    test_build_index.py
    test_validate.py
    test_rlm_env.py
    test_packer.py
```

In `sgb-rlm-varstore/.gitignore` ignoriere generierte Builddaten:

```gitignore
varstore/
*.sqlite
__pycache__/
.pytest_cache/
```

## 3. Python-Projekt

`sgb-rlm-varstore/pyproject.toml`:

- Python: `>=3.11`
- Package: `sgbpot`
- Abhängigkeiten möglichst klein halten.
- Verwende bevorzugt Standardbibliothek.
- Zulässig: `pytest`, optional `pyyaml` falls nötig.
- Wenn du YAML vermeiden willst, darf `sgb_books.yaml` sehr simpel geparst werden oder du legst zusätzlich JSON an. Aber die YAML-Datei muss existieren.

## 4. Konfiguration `sgb_books.yaml`

Lege eine einfache Konfiguration an mit diesen IDs:

```yaml
books:
  - book_id: SGB_I
    aliases: ["SGB 1", "SGB I"]
    data_paths: ["data/items/sgb_1"]
  - book_id: SGB_II
    aliases: ["SGB 2", "SGB II"]
    data_paths: ["data/items/sgb_2"]
  - book_id: SGB_III
    aliases: ["SGB 3", "SGB III"]
    data_paths: ["data/items/sgb_3"]
  - book_id: SGB_IV
    aliases: ["SGB 4", "SGB IV"]
    data_paths: ["data/items/sgb_4"]
  - book_id: SGB_V
    aliases: ["SGB 5", "SGB V"]
    data_paths: ["data/items/sgb_5"]
  - book_id: SGB_VI
    aliases: ["SGB 6", "SGB VI"]
    data_paths: ["data/items/sgb_6"]
  - book_id: SGB_VII
    aliases: ["SGB 7", "SGB VII"]
    data_paths: ["data/items/sgb_7"]
  - book_id: SGB_VIII
    aliases: ["SGB 8", "SGB VIII"]
    data_paths: ["data/items/sgb_8"]
  - book_id: SGB_IX
    aliases: ["SGB 9", "SGB IX"]
    data_paths: ["data/items/sgb_9_2018"]
  - book_id: SGB_X
    aliases: ["SGB 10", "SGB X"]
    data_paths: ["data/items/sgb_10"]
  - book_id: SGB_XI
    aliases: ["SGB 11", "SGB XI"]
    data_paths: ["data/items/sgb_11"]
  - book_id: SGB_XII
    aliases: ["SGB 12", "SGB XII"]
    data_paths: ["data/items/sgb_12"]
  - book_id: SGB_XIV
    aliases: ["SGB 14", "SGB XIV"]
    data_paths: ["data/items/sgb_14"]
  - book_id: SGG
    aliases: ["SGG", "Sozialgerichtsgesetz"]
    data_paths: ["data/items/sgg"]
```

Dokumentiere: SGB XIII ist bewusst nicht enthalten.

## 5. XML-Ingest

Implementiere `ingest_xml.py` deterministisch.

### 5.1 Daten lesen

Der Ingest soll zwei Modi unterstützen:

1. Dateien aus einem normalen Verzeichnis lesen, z. B. Fixtures.
2. Dateien aus einem Git-Branch lesen, z. B. `data`.

Für den Git-Branch verwende einfache Git-Kommandos:

```bash
git rev-parse data
git ls-tree -r --name-only data <prefix>
git show data:<path>
```

Implementiere dafür kleine Hilfsfunktionen in Python mit `subprocess.run(..., check=True, text=True, capture_output=True)`.

### 5.2 XML-Struktur

Die GiI-XML-Dateien enthalten wiederholte `<norm>`-Elemente. Ein Beispiel sieht so aus:

```xml
<norm builddate="..." doknr="...">
  <metadaten>
    <jurabk>SGB 10</jurabk>
    <jurabk>SGB X</jurabk>
    <enbez>§ 24</enbez>
    <titel format="XML">Anhörung Beteiligter</titel>
  </metadaten>
  <textdaten>
    <text format="XML">
      <Content>
        <P>(1) Text...</P>
        <P>(2) Text...</P>
      </Content>
    </text>
  </textdaten>
</norm>
```

Wichtig: Manche XML-Dateien haben mehrere `<norm>`-Elemente ohne gemeinsamen Root. Um sie zu parsen, wickle den Inhalt vor dem Parsen in `<root>...</root>`.

### 5.3 Normen extrahieren

Für jedes `<norm>`:

- `paragraph` = Text aus `<enbez>`.
- Überspringe Einträge ohne `paragraph`, wenn sie nur Gliederung sind.
- `heading` = Text aus `<titel>`, falls vorhanden, sonst leer.
- `book_id` = aus Config-Pfad oder Alias.
- `norm_id` = `book_id + ":" + paragraph_ohne_zusatzspaces`, Beispiel `SGB_X:§24`.

Normalisiere Paragraphen:

- `§ 24` -> `§24`
- `§ 24a` -> `§24a`
- `Art. 1` bleibt `Art.1`, falls es vorkommt.

### 5.4 Spans extrahieren

Für den ersten Wurf reicht diese Span-Strategie:

- Pro `<P>` ein Absatzspan.
- Zusätzlich einfache Satzspans aus jedem Absatz erzeugen.
- Satzsplit simpel halten: Split nach `. `, `? `, `! `; keine perfekte deutsche NLP bauen.
- Wenn Satzsplit unsicher ist, trotzdem Absatzspan behalten.

Span-IDs:

```text
SGB_X:§24:Abs1
SGB_X:§24:Abs1:S1
SGB_X:§24:Abs1:S2
SGB_X:§24:Abs2
SGB_X:§24:Abs2:S1
```

Text normalisieren:

- Whitespace kollabieren.
- XML-Text über `itertext()` gewinnen.
- Keine juristischen Inhalte umschreiben.

Schreibe:

```text
source.json
books.jsonl
norms.jsonl
raw_spans.jsonl
```

## 6. Hashes und IDs

Implementiere in `normalize.py`:

```python
def normalize_ws(text: str) -> str: ...
def sha256_text(text: str) -> str: ...  # return "sha256:<hex>"
```

Implementiere in `span_ids.py`:

```python
def normalize_paragraph_id(paragraph: str) -> str: ...
def norm_id(book_id: str, paragraph: str) -> str: ...
def paragraph_span_id(norm_id: str, abs_no: int) -> str: ...
def sentence_span_id(norm_id: str, abs_no: int, sent_no: int) -> str: ...
```

Schreibe dafür Tests.

## 7. Schemas

Implementiere `schemas.py` mit `dataclasses` oder einfachen Validator-Funktionen. Keine komplexe Framework-Magie nötig.

Mindestobjekte:

- `BookRecord`
- `NormRecord`
- `SpanRecord`
- `CardRecord`
- `TopicRecord`

Du darfst JSON-Dicts verwenden, aber die Validatoren müssen klare Fehlermeldungen liefern.

## 8. SQLite-Index

Implementiere `build_index.py`.

Erzeuge Tabellen:

```sql
books(book_id TEXT PRIMARY KEY, title TEXT, source_commit TEXT);
norms(norm_id TEXT PRIMARY KEY, book_id TEXT, paragraph TEXT, heading TEXT, text_hash TEXT);
spans(span_id TEXT PRIMARY KEY, norm_id TEXT, book_id TEXT, path_json TEXT, unit_type TEXT, text TEXT);
cards(norm_id TEXT PRIMARY KEY, heading TEXT, one_sentence TEXT, roles_json TEXT, topics_json TEXT);
topics(topic_id TEXT PRIMARY KEY, label TEXT, description TEXT, core_norms_json TEXT);
```

Erzeuge FTS5-Tabellen, wenn FTS5 verfügbar ist:

```sql
spans_fts(span_id, norm_id, book_id, heading, text);
cards_fts(norm_id, heading, one_sentence, topic_tags, likely_questions);
topics_fts(topic_id, label, description, likely_questions);
```

Wenn FTS5 nicht verfügbar ist, implementiere langsame `LIKE`-Fallback-Suche. Tests müssen auch ohne FTS5 laufen.

## 9. Varstore und RLM-API

Implementiere `varstore.py`, `rlm_env.py`, `packer.py`.

### 9.1 Klassen

```python
class SGBMemory:
    def __init__(self, varstore_path: str = "varstore", scope: str | None = None): ...
    def books(self) -> list[str]: ...
    def norm(self, norm_id: str) -> "NormVar": ...
    def search(self, query: str, k: int = 20) -> list[dict]: ...
    def topic(self, label: str) -> "TopicVar": ...
    def pack(self, ids: list[str], include_cards: bool = True) -> str: ...

class NormVar:
    def text(self) -> str: ...
    def spans(self) -> list[dict]: ...
    def card(self) -> dict | None: ...
    def neighbors(self) -> list[str]: ...

class TopicVar:
    def core_norms(self) -> list[str]: ...
    def related_norms(self) -> list[str]: ...
    def cards(self) -> list[dict]: ...
    def pack(self) -> str: ...
```

### 9.2 Globale Variablen

In `rlm_env.py`:

```python
SGB = SGBMemory("varstore", scope="SGB")
SGG = SGBMemory("varstore", scope="SGG")
CARD = SGB.cards
TOPIC = SGB.topics
IDX = SGB.index
PACK = SGB.packer
TRACE = SGB.trace
```

Wenn `varstore/` nicht existiert, soll Import nicht crashen. Stattdessen lazy laden und bei Nutzung eine klare Fehlermeldung ausgeben:

```text
Varstore not found. Run: python -m sgbpot.cli ingest ...
```

## 10. Kontextpacker

Implementiere `PACK.norms(...)` so:

Input:

```python
PACK.norms(["SGB_X:§24"], include_raw=True, include_cards=True, include_topics=False, max_chars=60000)
```

Output als String:

```text
# Kontextpaket
source_commit: <sha>

## SGB_X:§24 — Anhörung Beteiligter

### Raw Spans
[SGB_X:§24:Abs1] ...
[SGB_X:§24:Abs1:S1] ...

### Memory Card
one_sentence: ...
roles:
- ... [Evidence: ...]
```

Regeln:

- Raw-Spans zuerst.
- Card danach.
- Wenn `max_chars` erreicht wird, kürze zuerst Card-Details, nicht Raw-Spans.
- Gib nie erfundene Evidence aus.

## 11. Validator

Implementiere `validate.py` und CLI-Befehl `validate`.

Hard Checks:

1. Jede JSONL-Zeile parsebar.
2. `source_commit` existiert.
3. Jede `span_id` eindeutig.
4. Jede Norm referenziert vorhandene Spans.
5. Jeder `text_hash` passt zum Text.
6. Jede Card referenziert existierende Norm.
7. Jede Evidence-ID in Cards existiert.
8. Jede Rolle/Rechtsfolge/Voraussetzung mit Inhalt hat Evidence.
9. `one_sentence` nicht leer.
10. Topics referenzieren nur vorhandene Normen.

Bei Fehlern:

- Exit-Code `1`.
- Klare Liste der Fehler.

Bei Erfolg:

- Exit-Code `0`.
- Ausgabe: `validation passed`.

## 12. Spark-Compiler-Adapter

Implementiere `compile_cards_spark.py` und `compile_topics_spark.py` so, dass sie ohne echten API-Zugang testbar sind.

### 12.1 Dry-Run-Modus

Pflicht:

```bash
python -m sgbpot.cli compile-cards --varstore varstore --books SGB_X --dry-run
```

Dry-Run erzeugt einfache gültige Thin Cards deterministisch aus Heading und ersten Spans. Beispiel:

```json
{
  "card_id": "CARD:SGB_X:§24",
  "card_type": "thin",
  "norm_id": "SGB_X:§24",
  "book_id": "SGB_X",
  "heading": "Anhörung Beteiligter",
  "one_sentence": "Navigationskarte zu SGB_X:§24: Anhörung Beteiligter.",
  "roles": [{"role": "Norm", "evidence": ["SGB_X:§24:Abs1"]}],
  "actors": [],
  "legal_effects": [],
  "conditions": [],
  "exceptions_or_limits": [],
  "topic_tags": ["Anhörung Beteiligter"],
  "likely_questions": ["Welche Bedeutung hat SGB_X:§24?"],
  "xref_candidates": [],
  "compiler": {"model": "dry-run", "prompt_version": "norm-card-v0.1", "created_at": "..."}
}
```

### 12.2 Echter Modellmodus

Baue nur den Adapter und Promptaufruf als klare Schnittstelle. Wenn kein API-Key/Client vorhanden ist, gib eine klare Fehlermeldung aus. Nicht blockieren.

Artefakte müssen den tatsächlichen Modellnamen speichern.

## 13. Compiler-Prompts

Fülle die Dateien in `config/compiler_prompts/` mit kurzen, harten Prompts.

Alle Prompts müssen diese Regeln enthalten:

```text
Nutze ausschließlich bereitgestellte Spans.
Erfinde keine Normen, Absätze oder Span-IDs.
Jede Rolle, Voraussetzung, Rechtsfolge, Ausnahme und Frage braucht Evidence.
Wenn der Text etwas nicht trägt, lass es weg.
Keine Rechtsberatung.
Keine finale Auslegung.
Nur valides JSON nach Schema ausgeben.
```

## 14. CLI

Implementiere `cli.py` mit `argparse`.

Pflichtbefehle:

```bash
python -m sgbpot.cli ingest --repo . --data-ref data --out varstore
python -m sgbpot.cli index --varstore varstore
python -m sgbpot.cli compile-cards --varstore varstore --books SGB_X --dry-run
python -m sgbpot.cli compile-topics --varstore varstore --dry-run
python -m sgbpot.cli validate --varstore varstore
python -m sgbpot.cli inspect --varstore varstore --norm SGB_X:§24
python -m sgbpot.cli search --varstore varstore --query "Anhörung Verwaltungsakt" --k 5
```

CLI soll klare Fehlermeldungen ausgeben und mit Exit-Code `1` abbrechen, wenn Eingaben fehlen.

## 15. Tests

Schreibe Tests mit kleinen Fixtures. Tests dürfen nicht vom echten `data`-Branch abhängen.

Pflichttests:

1. `test_span_ids.py`
   - `§ 24` -> `§24`
   - `SGB_X`, `§ 24` -> `SGB_X:§24`
   - Satzspan-ID korrekt.

2. `test_ingest_xml.py`
   - `mini_sgb_x.xml` mit zwei Normen einlesen.
   - `raw_spans.jsonl` entsteht.
   - `norms.jsonl` entsteht.
   - `SGB_X:§24` existiert.

3. `test_build_index.py`
   - Index aus Fixture-Varstore bauen.
   - Suche nach `Anhörung Verwaltungsakt` findet `SGB_X:§24`.

4. `test_validate.py`
   - Gültiger Mini-Varstore besteht.
   - Card mit falscher Evidence fällt durch.

5. `test_rlm_env.py`
   - `SGBMemory(...).norm("SGB_X:§24").text()` liefert Text.
   - `.search(...)` liefert Treffer.

6. `test_packer.py`
   - `PACK.norms(["SGB_X:§24"])` enthält Raw-Span-ID und Heading.

## 16. Mini-Fixture

Lege `tests/fixtures/mini_sgb_x.xml` mit mindestens diesen zwei Normen an:

```xml
<norm builddate="fixture" doknr="fixture-24">
  <metadaten>
    <jurabk>SGB X</jurabk>
    <enbez>§ 24</enbez>
    <titel format="XML">Anhörung Beteiligter</titel>
  </metadaten>
  <textdaten><text format="XML"><Content>
    <P>(1) Vor Erlass eines Verwaltungsaktes, der in Rechte eines Beteiligten eingreift, ist diesem Gelegenheit zu geben, sich zu den für die Entscheidung erheblichen Tatsachen zu äußern.</P>
    <P>(2) Von der Anhörung kann unter den gesetzlich bestimmten Voraussetzungen abgesehen werden.</P>
  </Content></text></textdaten>
</norm>
<norm builddate="fixture" doknr="fixture-31">
  <metadaten>
    <jurabk>SGB X</jurabk>
    <enbez>§ 31</enbez>
    <titel format="XML">Begriff des Verwaltungsaktes</titel>
  </metadaten>
  <textdaten><text format="XML"><Content>
    <P>Verwaltungsakt ist jede Verfügung, Entscheidung oder andere hoheitliche Maßnahme, die eine Behörde zur Regelung eines Einzelfalles auf dem Gebiet des öffentlichen Rechts trifft und die auf unmittelbare Rechtswirkung nach außen gerichtet ist.</P>
  </Content></text></textdaten>
</norm>
```

## 17. Beispiele

Beispiele sollen nur zeigen, wie die API benutzt wird. Sie müssen bei fehlendem Varstore freundlich abbrechen.

Beispiel `ask_anhoerung.py`:

```python
from sgbpot.varstore import SGBMemory

sgb = SGBMemory("varstore")
hits = sgb.search("Anhörung Verwaltungsakt", k=5)
print(hits)
print(sgb.pack(["SGB_X:§24"], include_cards=True))
```

## 18. README für `sgb-rlm-varstore`

Schreibe eine kurze README mit:

- Zweck.
- Nicht-Ziele.
- Datenquelle `data`-Branch.
- Quickstart mit Fixture.
- Quickstart mit echtem `data`-Branch.
- Validierung.
- Hinweis: keine Rechtsberatung.
- Hinweis: Raw-Spans sind Belegquelle.

## 19. Akzeptanzkriterien

Am Ende müssen diese Befehle funktionieren:

```bash
cd sgb-rlm-varstore
python -m pytest
python -m sgbpot.cli ingest --fixture tests/fixtures/mini_sgb_x.xml --out /tmp/sgbpot-mini-varstore
python -m sgbpot.cli index --varstore /tmp/sgbpot-mini-varstore
python -m sgbpot.cli compile-cards --varstore /tmp/sgbpot-mini-varstore --books SGB_X --dry-run
python -m sgbpot.cli compile-topics --varstore /tmp/sgbpot-mini-varstore --dry-run
python -m sgbpot.cli validate --varstore /tmp/sgbpot-mini-varstore
python -m sgbpot.cli search --varstore /tmp/sgbpot-mini-varstore --query "Anhörung Verwaltungsakt" --k 5
python -m sgbpot.cli inspect --varstore /tmp/sgbpot-mini-varstore --norm SGB_X:§24
```

Danach aus Repo-Root:

```bash
git diff --check
go test ./...
```

Wenn Python/Pytest in der Umgebung nicht installiert ist, dokumentiere das klar in deiner Abschlussmeldung. Aber schreibe den Code so, dass die Befehle in einer normalen Python-3.11-Umgebung laufen.

## 20. Arbeitsreihenfolge

Arbeite genau in dieser Reihenfolge:

1. Status prüfen: `git status -sb`.
2. Konzept lesen: `docs/sgb-rlm-varstore-implementation-plan.md`.
3. Dateien und Verzeichnisse anlegen.
4. Normalisierung und ID-Funktionen implementieren.
5. Tests für IDs schreiben.
6. XML-Ingest für Fixture implementieren.
7. Tests für Ingest schreiben.
8. SQLite-Index implementieren.
9. Tests für Suche schreiben.
10. Varstore/RLM-Klassen implementieren.
11. Packer implementieren.
12. Validator implementieren.
13. Dry-Run-Compiler implementieren.
14. Prompts schreiben.
15. CLI verbinden.
16. Beispiele schreiben.
17. README schreiben.
18. Alle Tests ausführen.
19. Fehler beheben.
20. Abschlussmeldung mit Dateien, Befehlen und offenen Grenzen.

## 21. Was du nicht tun sollst

Nicht tun:

- Keine vollständigen SGB-Cards mit echtem Modell erzeugen.
- Keine großen generierten Artefakte committen.
- Keine Vektor-DB hinzufügen.
- Keine Web-App bauen.
- Keine juristische Antwortmaschine bauen.
- Keine perfekte deutsche Satzsegmentierung bauen.
- Keine Geltungshistorie bauen.
- Keine Normen ausdenken, wenn Discovery etwas nicht findet.
- Keine stillen Fehler: immer klar fehlschlagen oder `review_needed.jsonl` schreiben.

## 22. Abschlussformat

Antworte am Ende genau mit diesen Abschnitten:

```text
Implemented:
- ...

Validation:
- command: ...
  result: ...

Known limits:
- ...

Next safe step:
- ...
```

Wenn du nicht fertig wirst, stoppe nach dem letzten grünen Schritt und erkläre exakt, welcher nächste Schritt auszuführen ist.

## PROMPT END
