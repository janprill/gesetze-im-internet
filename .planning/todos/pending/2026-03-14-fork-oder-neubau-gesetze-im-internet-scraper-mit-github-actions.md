---
created: 2026-03-14T16:45:20.074Z
title: Fork oder Neubau gesetze-im-internet Scraper mit GitHub Actions
area: tooling
files:
  - scrape.py
  - scrape.sh
  - requirements.txt
  - docker-compose.yml
---

## Problem

Der bestehende Scraper (Python, Docker + Cron auf selbst gehostetem Server) ist seit dem 09.02.2026 ausgefallen. Dadurch fehlen ~33 Tage Scraping-History im `data` Branch — diese Lücken sind unwiederbringlich, da gesetze-im-internet.de keine historischen Versionen anbietet. Ein selbst gehosteter Docker-Container ist fehleranfällig und wird nicht automatisch neu gestartet wenn der Server ausfällt.

## Bestandsaufnahme (2026-03-15)

**Das Repo ist bereits ein Fork von QuantLaw:**
- `origin` → `git@github.com:janprill/gesetze-im-internet.git` (unser Repo)
- `upstream` → `git@github.com:QuantLaw/gesetze-im-internet.git` (QuantLaw-Original)

Die Frage "Fork oder Neubau" ist damit beantwortet: **Fork bereits vorhanden.** Die Arbeit beginnt auf dem bestehenden Fork.

## Solution

Fork des Repos (QuantLaw/gesetze-im-internet) ist bereits als `janprill/gesetze-im-internet` eingerichtet. Nächste Schritte:
- GitHub Actions Workflow statt Docker/Cron einrichten
- Täglicher Cron-Trigger via `schedule: cron` in GitHub Actions
- Scraper committed direkt in den `data` Branch via `GITHUB_TOKEN`
- Entscheidung: bestehenden Python-Scraper behalten oder in Go/Rust neu schreiben
