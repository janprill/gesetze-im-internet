# sgb-rlm-varstore

Dieser Proof stellt die Inhalte von SGB I bis SGB XIV (ausgenommen SGB XIII) und SGG
als lokale Varstore-Daten für ein RLM-ähnliches Interface bereit.

## Zweck

- Deterministischer XML-Ingest aus dem `data`-Branch.
- Erzeugung von kanonischen JSONL-Artefakten (`source.json`, `books.jsonl`, `norms.jsonl`, `raw_spans.jsonl`).
- SQLite-Index (mit optionalem FTS5).
- RLM-Variablen (`SGB`, `SGG`, `CARD`, `TOPIC`, `IDX`, `PACK`, `TRACE`).
- Kleine, evidenzgebundene Testartefakte im **Dry-Run**.

## Nicht-Ziele

- Keine bitemporale Rechtsgeschichte.
- Keine Rechtsberatung oder Rechtsauslegung.
- Keine Web-App oder produktive Datenbankarchitektur.
- Keine Modellgenerierung ohne Evidenzbindung auf Raw-Spans.

## Datenquelle

Die Volltexte werden aus dem lokalen `data`-Branch gelesen.
Der tatsächlich verwendete Commit wird in `source.json` gespeichert.

## Quickstart (Fixture)

```bash
cd sgb-rlm-varstore
python -m sgbpot.cli ingest --fixture tests/fixtures/mini_sgb_x.xml --out /tmp/sgbpot-mini-varstore
python -m sgbpot.cli index --varstore /tmp/sgbpot-mini-varstore
python -m sgbpot.cli compile-cards --varstore /tmp/sgbpot-mini-varstore --books SGB_X --dry-run
python -m sgbpot.cli compile-topics --varstore /tmp/sgbpot-mini-varstore --dry-run
python -m sgbpot.cli validate --varstore /tmp/sgbpot-mini-varstore
python -m sgbpot.cli search --varstore /tmp/sgbpot-mini-varstore --query "Anhörung Verwaltungsakt" --k 5
python -m sgbpot.cli inspect --varstore /tmp/sgbpot-mini-varstore --norm SGB_X:§24
```

## Quickstart (echter `data`-Branch)

```bash
cd sgb-rlm-varstore
python -m sgbpot.cli ingest --repo . --data-ref data --out varstore
python -m sgbpot.cli index --varstore varstore
python -m sgbpot.cli compile-cards --varstore varstore --books SGB_X --dry-run
python -m sgbpot.cli compile-topics --varstore varstore --dry-run
python -m sgbpot.cli validate --varstore varstore
```

## Alle Bücher kompilieren

Mit `--all-books` werden alle verfügbaren Bücher ohne Filterung kompiliert.
`--all-books` und `--books` schließen sich gegenseitig aus.

```bash
python -m sgbpot.cli compile-cards --varstore varstore --all-books --dry-run
```

## Kombinierter Varstore (mehrere Bücher)

```bash
# GKV-Anwendungsfall: SGB V (Leistungsrecht) + SGB X (Verwaltungsverfahren) + SGG (Prozessrecht)
python -m sgbpot.cli ingest --repo . --data-ref data --books SGB_V SGB_X SGG --out /tmp/sgbpot-gkv
python -m sgbpot.cli index --varstore /tmp/sgbpot-gkv
python -m sgbpot.cli compile-cards --varstore /tmp/sgbpot-gkv --books SGB_V SGB_X SGG --dry-run
python -m sgbpot.cli compile-topics --varstore /tmp/sgbpot-gkv --dry-run
python -m sgbpot.cli validate --varstore /tmp/sgbpot-gkv
```

## Topic-Gruppierung

Topics werden semantisch gruppiert (nicht 1:1 zu Cards). Die Gruppierung erfolgt
nach überlappenden `topic_tags`, gleichem `book_scope` und Heading-Ähnlichkeit.
Einzelnormen ohne thematische Verwandte bleiben Einzeltopics.

## Scope-Prüfung

`SGBMemory(scope="SGB")` erlaubt nur SGB_*-Bücher.
`SGGMemory(scope="SGG")` erlaubt nur SGG-Bücher.
`scope=None` erlaubt alle Bücher.

## Suche

`search()` dedupliziert Treffer nach `norm_id` und bevorzugt Paragraph-Spans.
Optional kann mit `unit_type="paragraph"` auf Paragraph-Treffer gefiltert werden.

## Vollständige SGB-V-Varstore (Startpunkt)

```bash
cd sgb-rlm-varstore
python -m sgbpot.cli ingest --repo . --data-ref data --books SGB_V --out varstore
python -m sgbpot.cli index --varstore varstore
python -m sgbpot.cli compile-cards --varstore varstore --books SGB_V --dry-run
python -m sgbpot.cli compile-topics --varstore varstore --dry-run
python -m sgbpot.cli validate --varstore varstore
```

Für eine vollständigere Erhebung (alle Bücher) den `--books`-Filter weglassen.
## Hinweise

- `one_sentence` und alle inhaltlichen Card-Felder müssen auf vorhandene Raw-Spans verweisen.
- Raw-Spans sind die Wortlautquelle.
- Keine Rechtsberatung.

## Validierung

```bash
python -m sgbpot.cli validate --varstore <varstore-path>
```

Gibt `validation passed` aus, wenn alle harten Checks erfolgreich sind.
