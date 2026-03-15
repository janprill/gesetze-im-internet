# gesetze-im-internet Scraper

## Current Milestone: v2.0 — Automation

**Ziel:** Datenlücken schließen (Upstream-Sync + lokaler Backfill), Workflow auf self-hosted Runner migrieren, Gap Detection und Idempotenz implementieren.

**Target requirements:** SYNC-01, SYNC-02, INFRA-05, INFRA-06, INFRA-07, RESIL-01, RESIL-02, RESIL-03, OPS-01, OPS-02

---

## What This Is

Ein automatischer Scraper, der täglich alle deutschen Gesetze von gesetze-im-internet.de herunterlädt und als ZIP-Dateien im `data`-Branch versioniert. Läuft auf GitHub Actions mit self-hosted Runner (Azure-IPs werden von der Zielseite geblockt). Erkennt und füllt automatisch Datenlücken.

## Core Value

Lückenlose tägliche Scraping-History — kein einziger Tag darf fehlen, denn verpasste Tage sind unwiederbringlich (gesetze-im-internet.de bietet keine historischen Versionen).

## Requirements

### Validated

- ✓ Tägliches Scraping von ~150 deutschen Gesetzen von gesetze-im-internet.de — existing
- ✓ XML TOC-Parsing (gii-toc.xml) zur Entdeckung aller Download-Links — existing
- ✓ Parallele ZIP-Downloads mit HTTP-Retry und Exponential Backoff — existing
- ✓ Git-basierte Datenpersistenz (täglich datierter Commit im `data`-Branch) — existing
- ✓ Tracking fehlender/entfernter Gesetze (not_found.txt) — existing

### Active

- [ ] GitHub Actions Workflow ersetzt Docker/Cron auf eigenem Server
- [ ] Täglicher Cron-Trigger (04:00 UTC) via `schedule: cron`
- [ ] Authentifizierung via `GITHUB_TOKEN` (kein SSH-Key-Management mehr)
- [ ] Lücken-Detektion: Prüfen ob Tage im `data`-Branch fehlen
- [ ] Nachhollogik: Fehlende Tage rückwirkend nachscrapen
- [ ] Idempotente Runs: Mehrfaches Ausführen für denselben Tag ist sicher
- [ ] Modernisierung: Python 3.11+ mit gepinnten Dependencies (oder Go/Rust-Neubau)

### Out of Scope

- Webfrontend — kein User-Interface geplant
- Datenbank — Git-Branch bleibt die Persistenzschicht
- API-Endpoint — kein programmatischer Zugriff nötig
- Inkrementelles Scraping — jeder Run lädt alle ~150 Gesetze vollständig

## Context

Der Scraper ist seit 09.02.2026 ausgefallen (ca. 33 Tage Datenlücke). Ursache: Selbst gehosteter Docker-Container ohne automatischen Neustart bei Serverausfall, kein Monitoring, kein Alerting. Die bestehende Python-Implementierung funktioniert grundsätzlich, hat aber:
- Python 3.7 (EOL seit 2023-06-27)
- Ungepinnte Dependencies
- Race condition in Multiprocessing Pool
- Fragile HTML-basierte 404-Erkennung
- Keine Tests

GitHub Actions löst das Infrastrukturproblem komplett: kostenlos für Public Repos, von GitHub gewartet, E-Mail-Alert bei Job-Failure built-in.

## Constraints

- **Compatibility**: Output-Format (ZIP-Dateien in `data`-Branch, täglich committet mit Datum-Tag) muss erhalten bleiben — bestehende Konsumenten erwarten dieses Format
- **Source**: Scraping-Quelle bleibt gesetze-im-internet.de — keine alternativen Quellen
- **Auth**: GitHub Actions `GITHUB_TOKEN` für Push in `data`-Branch

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| GitHub Actions statt Docker/Cron | Keine eigene Infrastruktur, kostenlos, automatisches Alerting, reliable | ✓ Good |
| Python 3.13 + uv modernisieren | Geringster Migrationsaufwand, reproduzierbares Lockfile, Python-Ökosystem bekannt | ✓ Good |
| Self-hosted Runner statt GitHub-hosted | GitHub-hosted (Azure) IPs von www.gesetze-im-internet.de geblockt | ✓ Good |
| Lücken-Nachhollogik | Einmal verpasste Tage können nicht von außen nachgeholt werden — Scraper muss es selbst erkennen | — Pending |
| Backfill: 1 Scrape → 33 Commits | Inhalt identisch für alle fehlenden Tage (Site hat keine Historien-API); effizienter als 33 separate Scrapes | — Pending |

---
*Last updated: 2026-03-15 after v2.0 milestone start*
