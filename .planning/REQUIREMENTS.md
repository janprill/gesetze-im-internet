# Requirements: gesetze-im-internet Scraper

**Defined:** 2026-03-14
**Core Value:** Lückenlose tägliche Scraping-History — kein einziger Tag darf fehlen

## v1 Requirements

Requirements for the GitHub Actions migration. Each maps to roadmap phases.

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

### Resilience

- [ ] **RESIL-01**: Workflow detects missing days by comparing expected daily date sequence against existing date tags in `data` branch
- [ ] **RESIL-02**: Workflow automatically re-scrapes all detected missing days in sequence (catch-up logic fills 33-day gap on first deployment)
- [ ] **RESIL-03**: Runs are idempotent — re-running for an already-scraped date skips silently with exit 0, no duplicate commits
- [x] **RESIL-04**: GitHub automatically sends failure alert email when scheduled workflow job fails (built-in, no setup required)

## v2 Requirements

Deferred — add after v1 has run stably for 1-2 weeks in production.

### Operator Tooling

- **OPS-01**: `workflow_dispatch` trigger with optional `target_date` input for ad-hoc manual re-scrape of a specific date
- **OPS-02**: Structured run summary written to `$GITHUB_STEP_SUMMARY` (date scraped, laws count, not_found count, gaps detected/filled)

### Reliability Improvements

- **REL-01**: ZIP integrity check after extraction — verify at least one non-empty file exists, flag corrupted archives in `not_found.txt`
- **REL-02**: Configurable worker parallelism via `SCRAPER_WORKERS` env var (default: 4, replacing hardcoded `Pool(2)`)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Incremental scraping (only download changed laws) | gesetze-im-internet.de provides no ETag/Last-Modified/changelog; full scrape is only ~3 min; PROJECT.md explicit exclusion |
| External monitoring services (Healthchecks.io, Uptime Robot) | Built-in GitHub failure email is sufficient; adds external dependency to manage |
| Database for scrape state | Git history of `data` branch is the state store; a DB adds infrastructure cost and complexity |
| Real-time webhook alerts (Slack, PagerDuty) | Daily job; email alert is equivalent to "real-time" in practice |
| Rollback mechanism | Manual `git revert` on `data` branch is sufficient; automated rollback needs a "bad data" definition |
| Checkpoint/resume for partial scrapes | Full scrape is ~3 min; restart from scratch is simpler and idempotency makes it safe |
| API endpoint to trigger scrape | `workflow_dispatch` via GitHub API/CLI covers all on-demand trigger needs |
| Backfill date-range input | One-time 33-day gap is covered by automatic catch-up logic; range input is future convenience only |
| Keepalive workflow | Daily `data` branch commits reset the 60-day timer; keepalive only needed if scraper is intentionally paused |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCRAPER-01 | Phase 1 | Complete |
| SCRAPER-02 | Phase 1 | Complete |
| SCRAPER-03 | Phase 1 | Complete |
| SCRAPER-04 | Phase 1 | Complete |
| INFRA-01 | Phase 2 | Complete |
| INFRA-02 | Phase 2 | Complete |
| INFRA-03 | Phase 2 | Complete |
| INFRA-04 | Phase 2 | Complete |
| RESIL-01 | Phase 3 | Pending |
| RESIL-02 | Phase 3 | Pending |
| RESIL-03 | Phase 3 | Pending |
| RESIL-04 | Phase 2 | Complete |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-14 after roadmap creation*
