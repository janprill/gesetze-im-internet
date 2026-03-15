# gesetze-im-internet — Projekt-Idee und Richtung

## Stand (2026-03-15)

Der Scraper lief seit 2026-02-09 nicht mehr (Docker-Container auf selbst gehostetem Server abgestürzt).
34 Tage fehlen im `data`-Branch (2026-02-10 bis heute). Ziel ist ein vollautomatischer,
lückenloser Tages-Scraper ohne manuelle Eingriffe.

---

## Branching

```
main        Quellcode: scrape.py, Workflow, Tests, Konfiguration
data        Scrape-Ergebnisse: täglich ein Commit mit ZIP-Dateien, getaggt mit YYYY-MM-DD
```

- `main` ist der einzige Code-Branch (umbenannt von `master`, 2026-03-15)
- `data` ist ein orphan-Branch — enthält nur Scrape-Daten, keine Quelldateien
- Kein Feature-Branching, kein PR-Workflow: alles läuft direkt auf `main`

---

## Kernziel

**Kein einziger Tag darf fehlen.** Die Scraping-History soll lückenlos sein.

---

## Architektur

### Laufzeitplattform

**Self-hosted GitHub Actions Runner** auf eigenem Server.

Hintergrund: `www.gesetze-im-internet.de` blockiert GitHub-hosted Runner
(Microsoft Azure Datacenter-IPs). Der Scraper läuft deshalb auf einem eigenen Server
mit nicht-geblockter IP. GitHub Actions bleibt Orchestrator (Cron, UI, Alerting,
GITHUB_TOKEN-Auth) — nur der Runner ist self-hosted.

### Scraping-Logik

- **Täglich 04:00 UTC** via `schedule: cron` in GitHub Actions
- **Lücken-Detektion**: Beim Start prüfen, welche Tage fehlen (letzter Tag im `data`-Branch vs. heute)
- **Nachhollogik**: Fehlende Tage werden sequenziell rückwirkend nachgeholt
- **Idempotenz**: Bereits vorhandene Tage werden übersprungen (tag-basiert)
- **Retry bei Fehlern**: 30s Timeout + 5 Retries mit exponential backoff (backoff_factor=10)
- **Alerting**: Job-Failure → GitHub-interne E-Mail (kein zusätzlicher Code nötig)

### Technologie

- Python 3.13 + uv (pinned via `uv.lock`)
- `requests` mit `Retry`-Adapter (bereits implementiert)
- `scrape.py` mit `--date YYYY-MM-DD` CLI-Argument (bereits implementiert)
- GitHub Actions mit `GITHUB_TOKEN` (kein SSH-Key, kein PAT)

---

## Milestone-Übersicht

### Milestone 1 (v1.0) — Fundament ✓/◆

Abgeschlossen/laufend:
- ✓ Scraper modernisiert (Python 3.13, uv, --date arg, TOC-Validierung)
- ✓ GitHub Actions Workflow YAML erstellt (scrape.yml)
- ✓ HTTP-Timeout-Fix in scrape.py
- ✓ master → main umbenannt

### Milestone 2 (v2.0) — Backfill, Self-hosted Runner, Automation

Nächste Arbeiten:
1. **Lokaler Backfill**: 34 fehlende Tage (2026-02-10 bis 2026-03-15) lokal scrapen,
   in `data`-Branch committen und pushen
2. **Self-hosted Runner**: GitHub Actions Runner auf eigenem Server einrichten,
   Workflow auf `runs-on: self-hosted` umstellen
3. **Phase 2 Live-Verifikation**: workflow_dispatch auf self-hosted Runner durchführen,
   INFRA-03 (dated tag in data branch) live bestätigen
4. **Gap Detection**: `detect_gaps.py` — erkennt fehlende Tage via `git ls-remote --tags`,
   gibt JSON-Liste zurück; max. 60 Tage Lookback
5. **Idempotenz**: Skip-Logik für bereits vorhandene Tags
6. **Vollautomatischer Betrieb**: Kein einziger Tag fehlt mehr

---

## Was explizit NICHT gebaut wird

- Kein Webfrontend
- Keine Datenbank
- Kein API-Endpoint
- Kein inkrementelles Scraping (jeder Run lädt alle ~150 Gesetze)
- Kein weiterer Cloud-Provider (GitHub Actions self-hosted reicht)

---

## Erfolg sieht so aus

- Täglich um ~04:00 UTC läuft ein GitHub Actions Job auf dem eigenen Server
- Kein Tag fehlt in der History
- Bei Ausfall kommt eine Alert-E-Mail
- Nach einem Ausfall holt der nächste Run automatisch die fehlenden Tage nach
- Das `data`-Branch-Log ist lückenlos von heute bis in die Vergangenheit
