# Milestones

## v1.0 — Fundament (2026-03-14 bis 2026-03-15)

**Ziel:** Scraper modernisieren, GitHub Actions Workflow aufbauen, Fundament für vollautomatischen Betrieb legen.

**Status:** Partial — Phase 1 vollständig, Phase 2 teilweise. Phasen 3-4 werden in v2.0 fortgeführt.

**Was geliefert wurde:**
- Phase 1 ✓: Scraper modernisiert (Python 3.13, uv, `--date` arg, TOC-Validierung, 30s HTTP-Timeout, Tests)
- Phase 2 Plan 01 ✓: `scrape.yml` GitHub Actions Workflow + statische YAML-Tests (6 Tests, alle grün)
- `master → main` Umbenennung (2026-03-15)

**Was nicht geliefert wurde:**
- Phase 2 Live-Verifikation: Geblockt durch Azure-IP-Blocking von `www.gesetze-im-internet.de`
- Phase 3 (Gap Detection + Idempotenz): Nie gestartet
- Phase 4 (Operational Hardening): Nie gestartet

**Gelernte Erkenntnisse:**
- GitHub-hosted Runner (Microsoft Azure IPs) werden von `www.gesetze-im-internet.de` geblockt → Self-hosted Runner erforderlich
- QuantLaw (upstream) hat den Scraper am 2026-03-14/15 wieder angeworfen, jedoch ohne Nachhollogik für die 33-Tage-Lücke

**Phases:** 1–4 (Nummern reserviert; v2.0 startet bei Phase 5)

---
*Abgeschlossen: 2026-03-15*
