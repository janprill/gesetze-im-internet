# gesetze-im-internet Scraper

## What This Is

Ein automatischer Scraper, der täglich alle deutschen Gesetze von gesetze-im-internet.de herunterlädt und als ZIP-Dateien im `data`-Branch versioniert. Die Ausführung soll von einem selbst gehosteten Docker/Cron-Setup auf GitHub Actions migriert werden, damit kein einziger Scraping-Tag mehr ausgelassen wird.

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
| GitHub Actions statt Docker/Cron | Keine eigene Infrastruktur, kostenlos, automatisches Alerting, reliable | — Pending |
| Python 3.11+ modernisieren vs. Go/Rust-Neubau | Python hat weniger Migrationsaufwand; Go/Rust einfacheres Deployment. Bevorzugt: geringster Wartungsaufwand | — Pending |
| Lücken-Nachhollogik | Einmal verpasste Tage können nicht von außen nachgeholt werden — Scraper muss es selbst erkennen | — Pending |

---
*Last updated: 2026-03-14 after initialization*
