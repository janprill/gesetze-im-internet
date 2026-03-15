---
created: 2026-03-15T07:40:00.000Z
title: Fix missing HTTP timeout in scrape.py causes CI failure
area: tooling
files:
  - scrape.py
phase: 02-workflow-and-auth
blocks: 02-02
---

## Problem

Phase 02, Plan 02-02 (Live Workflow Verification) kann nicht abgeschlossen werden, weil
`scrape.py` kein `timeout=`-Argument bei HTTP-Requests setzt. Dadurch hängt der Scraper
unbegrenzt, bis GitHub Actions den Job abbricht.

Beobachtete Runs (2026-03-15):
- Run 23105498202 (07:03 UTC) → `failure` nach ~18 Min mit `urllib3.exceptions.ConnectTimeoutError` auf `www.gesetze-im-internet.de`
- Run 23105827176 (07:26 UTC) → `in_progress`, wird vermutlich gleich failen

Fehler-Root-Cause: `requests.get(url)` o.ä. ohne `timeout=` → urllib3 hängt unbegrenzt bei
Connection-Problemen auf Serverseite.

## Solution

In `scrape.py` alle HTTP-Requests mit einem expliziten `timeout` versehen (z.B. `timeout=30`).
Danach erneuten `workflow_dispatch`-Run triggern und Plan 02-02 abschließen.
