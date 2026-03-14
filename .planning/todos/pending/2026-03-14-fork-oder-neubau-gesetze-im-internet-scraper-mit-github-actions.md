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

## Solution

Fork des Repos (QuantLaw/gesetze-im-internet) oder Neubau in Go oder Rust mit GitHub Actions Workflow statt Docker/Cron:
- GitHub Actions läuft kostenlos, zuverlässig und braucht keine eigene Infrastruktur
- Neubau in Go oder Rust für bessere Performance und einfachere Deployment-Story
- Täglicher Cron-Trigger via `schedule: cron` in GitHub Actions
- Scraper committed direkt in den `data` Branch via `GITHUB_TOKEN`
