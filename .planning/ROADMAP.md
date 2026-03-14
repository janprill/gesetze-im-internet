# Roadmap: gesetze-im-internet Scraper

## Overview

This roadmap migrates the daily law-scraper from a broken Docker/cron setup to GitHub Actions. The work proceeds in strict dependency order: the scraper must accept a `--date` argument before the workflow can use it; the workflow must prove it can push before gap detection is wired in; idempotency must be in place before the 33-day backfill runs. Every phase delivers one verifiable capability. The result is a fully automated daily scraper that detects and heals its own gaps with no operator intervention.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Scraper Modernization** - Standalone, testable scraper on Python 3.13 with pinned deps and `--date` CLI argument
- [ ] **Phase 2: Workflow and Auth** - Working GitHub Actions workflow that runs daily, authenticates with `GITHUB_TOKEN`, and pushes one dated commit to the `data` branch
- [ ] **Phase 3: Gap Detection and Idempotency** - Workflow detects missing days and automatically scrapes them; repeated runs for the same date are safe
- [ ] **Phase 4: Operational Hardening and Backfill** - 33-day data gap closed; push failures surface as workflow failures; system validated in production

## Phase Details

### Phase 1: Scraper Modernization
**Goal**: The scraper runs reliably and identically in CI and locally, accepts a target date as input, validates the TOC before downloading, and has a reproducible dependency lockfile
**Depends on**: Nothing (first phase)
**Requirements**: SCRAPER-01, SCRAPER-02, SCRAPER-03, SCRAPER-04
**Success Criteria** (what must be TRUE):
  1. Running `uv run scrape.py --date 2026-03-14` succeeds locally and produces ZIP files in `data/items/` with the correct dated structure
  2. If the TOC XML returns fewer than 100 items, the scraper exits with a non-zero code before downloading anything
  3. `uv.lock` is committed and `uv sync --frozen` installs all dependencies without network errors on a fresh machine
  4. The scraper produces no git commits or pushes — all git operations are absent from `scrape.py`
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — uv migration: pyproject.toml + uv.lock, retire requirements.txt (SCRAPER-01)
- [ ] 01-02-PLAN.md — TDD: --date CLI arg + TOC validation guard in scrape.py (SCRAPER-02, SCRAPER-03, SCRAPER-04)
- [ ] 01-03-PLAN.md — Human smoke test: live integration verification (SCRAPER-04)

### Phase 2: Workflow and Auth
**Goal**: A GitHub Actions workflow runs on a daily cron schedule, authenticates via `GITHUB_TOKEN`, and pushes one commit with a dated tag to the `data` branch on every successful run; concurrent runs are serialized
**Depends on**: Phase 1
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, RESIL-04
**Success Criteria** (what must be TRUE):
  1. A workflow run triggered manually (`workflow_dispatch`) completes successfully and a new dated tag appears in the `data` branch
  2. `git ls-remote --tags origin` shows the expected date tag after the workflow completes
  3. The workflow YAML declares `permissions: contents: write` and no SSH keys or PATs are used
  4. Two simultaneous workflow triggers result in sequential execution (second run queues, not cancels) with no duplicate commits
**Plans**: TBD

### Phase 3: Gap Detection and Idempotency
**Goal**: Every workflow run — whether cron or manual — checks for missing days and scrapes them sequentially; running the workflow twice for the same date is safe and produces no duplicate commits
**Depends on**: Phase 2
**Requirements**: RESIL-01, RESIL-02, RESIL-03
**Success Criteria** (what must be TRUE):
  1. After skipping one day manually, the next workflow run detects the missing day and commits a tagged entry for it before committing today's date
  2. Running the workflow for a date that already has a tag exits with code 0 and creates no new commit or tag
  3. `detect_gaps.py` uses `git ls-remote --tags` (not a full clone) and outputs a JSON list of missing dates within a 60-day lookback window
**Plans**: TBD

### Phase 4: Operational Hardening and Backfill
**Goal**: The existing 33-day data gap (2026-02-09 to 2026-03-13) is closed using the catch-up logic built in Phase 3; push failures surface as workflow failures rather than silent successes; the system is validated to run correctly in production
**Depends on**: Phase 3
**Requirements**: (operational validation — no additional v1 code requirements)
**Success Criteria** (what must be TRUE):
  1. `git tag -l | grep "^202602" | wc -l` on the `data` branch returns 28 (all February 2026 days present)
  2. `git tag -l | grep "^20260[1-3]" | wc -l` confirms no gaps between 2026-02-09 and 2026-03-13
  3. A deliberate push failure (e.g., revoked token) causes the workflow to exit non-zero and triggers GitHub's failure email — no silent green run
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scraper Modernization | 1/3 | In Progress|  |
| 2. Workflow and Auth | 0/TBD | Not started | - |
| 3. Gap Detection and Idempotency | 0/TBD | Not started | - |
| 4. Operational Hardening and Backfill | 0/TBD | Not started | - |
