# Requirements: gesetze-im-internet Scraper

**Defined:** 2026-03-14
**Core Value:** Lückenlose tägliche Scraping-History — kein einziger Tag darf fehlen

---

## v1 Requirements (abgeschlossen in Milestone v1.0)

### Infrastructure

- [x] **INFRA-01**: GitHub Actions workflow triggers daily scrape at 04:00 UTC via `schedule: cron`
- [x] **INFRA-02**: Workflow authenticates to GitHub via `GITHUB_TOKEN` with `contents: write` permission (no SSH keys)
- [x] **INFRA-03**: Workflow commits scraped ZIP files to `data` branch with dated tag on success
- [x] **INFRA-04**: Concurrent workflow runs are serialized via `concurrency` group (queued, not cancelled)

### Scraper Modernization

- [x] **SCRAPER-01**: Scraper runs on Python 3.13 with pinned dependencies via `uv.lock`
- [x] **SCRAPER-02**: Scraper accepts `--date YYYY-MM-DD` argument to scrape and commit for a specific date
- [x] **SCRAPER-03**: Scraper validates TOC structure (>100 items parsed) before starting downloads and fails fast if invalid
- [x] **SCRAPER-04**: Scraper preserves existing output format (ZIP files in `data/items/`, `not_found.txt`, `log.md`, dated git tags)

### Resilience (partial)

- [x] **RESIL-04**: GitHub automatically sends failure alert email when scheduled workflow job fails (built-in, no setup required)

---

## v2 Requirements (Milestone v2.0 — Automation)

**Defined:** 2026-03-15

### Sync

- [ ] **SYNC-01**: Die 2 fehlenden Tage (2026-03-14, 2026-03-15) werden per `git pull upstream data` aus dem QuantLaw-Upstream in den eigenen Fork übernommen
- [ ] **SYNC-02**: Die 33-Tage-Lücke (2026-02-10 bis 2026-03-13) wird per lokalem Backfill-Script geschlossen: einmal scrapen, 33 backdatierte Commits mit je einem dated Tag in den `data`-Branch pushen

### Self-hosted Runner

- [ ] **INFRA-05**: `scrape.yml` Workflow läuft auf `runs-on: self-hosted` statt `ubuntu-latest` (GitHub-hosted Azure Runner geblockt)
- [ ] **INFRA-06**: Self-hosted GitHub Actions Runner auf eigenem Server eingerichtet, bei GitHub registriert und online
- [ ] **INFRA-07**: Live-Verifikation: Ein `workflow_dispatch`-Run auf dem self-hosted Runner schließt erfolgreich ab und legt einen dated Tag im `data`-Branch an

### Resilience

- [ ] **RESIL-01**: `detect_gaps.py` erkennt fehlende Tage via `git ls-remote --tags` (max. 60 Tage Lookback) und gibt eine JSON-Liste der fehlenden Daten zurück
- [ ] **RESIL-02**: Workflow scrapt alle erkannten fehlenden Tage sequenziell nach, bevor er den aktuellen Tag scrapt
- [ ] **RESIL-03**: Runs sind idempotent — Wiederholung für einen bereits vorhandenen Tag wird per Tag-Check übersprungen (exit 0, kein Doppel-Commit)

### Operations

- [ ] **OPS-01**: Nach dem Backfill sind alle Tags von 2026-02-10 bis heute im `data`-Branch vorhanden — kein einziger Tag fehlt
- [ ] **OPS-02**: Ein absichtlich fehlgeschlagener Scrape (simulierter Netzwerkfehler) führt zum Workflow-Failure und löst GitHub's eingebautes E-Mail-Alerting aus — kein silent green

---

## Future Requirements (v3+)

### Operator Tooling

- **FUT-01**: Strukturierte Run-Zusammenfassung in `$GITHUB_STEP_SUMMARY` (Datum, Gesetze-Anzahl, not_found-Anzahl, Lücken erkannt/gefüllt)
- **FUT-02**: ZIP-Integritätsprüfung nach Extraktion — mindestens eine nicht-leere Datei muss vorhanden sein

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Inkrementelles Scraping | Keine ETag/Last-Modified-API; kompletter Download ~3 min; explizit ausgeschlossen |
| Externe Monitoring-Services (Healthchecks.io etc.) | GitHub failure email reicht; externe Abhängigkeit vermeiden |
| Datenbank für Scrape-State | Git-History des `data`-Branch ist der State-Store |
| Webhook-Alerts (Slack, PagerDuty) | Täglicher Job; E-Mail ist ausreichend |
| API-Endpoint zum Triggern | `workflow_dispatch` via GitHub API/CLI deckt alle Bedarfe ab |
| Keepalive-Workflow | Tägliche `data`-Branch-Commits setzen den 60-Tage-Timer zurück |

---

## Traceability

| Requirement | Milestone | Phase | Status |
|-------------|-----------|-------|--------|
| SCRAPER-01 | v1.0 | Phase 1 | ✓ Complete |
| SCRAPER-02 | v1.0 | Phase 1 | ✓ Complete |
| SCRAPER-03 | v1.0 | Phase 1 | ✓ Complete |
| SCRAPER-04 | v1.0 | Phase 1 | ✓ Complete |
| INFRA-01 | v1.0 | Phase 2 | ✓ Complete |
| INFRA-02 | v1.0 | Phase 2 | ✓ Complete |
| INFRA-03 | v1.0 | Phase 2 | ✓ Complete |
| INFRA-04 | v1.0 | Phase 2 | ✓ Complete |
| RESIL-04 | v1.0 | Phase 2 | ✓ Complete |
| SYNC-01 | v2.0 | Phase 5 | Pending |
| SYNC-02 | v2.0 | Phase 5 | Pending |
| INFRA-05 | v2.0 | Phase 6 | Pending |
| INFRA-06 | v2.0 | Phase 6 | Pending |
| INFRA-07 | v2.0 | Phase 6 | Pending |
| RESIL-01 | v2.0 | Phase 7 | Pending |
| RESIL-02 | v2.0 | Phase 7 | Pending |
| RESIL-03 | v2.0 | Phase 7 | Pending |
| OPS-01 | v2.0 | Phase 8 | Pending |
| OPS-02 | v2.0 | Phase 8 | Pending |

**Coverage:**
- v2 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-15 after v2.0 milestone start*
