# Roadmap: gesetze-im-internet Scraper

## Milestones

- ✅ **v1.0 Fundament** - Phases 1-4 (partial — Phase 1 complete, Phase 2 partially complete; remainder subsumed into v2.0)
- 🚧 **v2.0 Automation** - Phases 5-8 (in progress)

## Phases

<details>
<summary>✅ v1.0 Fundament (Phases 1-4) - Partial / Subsumed into v2.0 on 2026-03-15</summary>

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
- [x] 01-01-PLAN.md — uv migration: pyproject.toml + uv.lock, retire requirements.txt (SCRAPER-01)
- [x] 01-02-PLAN.md — TDD: --date CLI arg + TOC validation guard in scrape.py (SCRAPER-02, SCRAPER-03, SCRAPER-04)
- [x] 01-03-PLAN.md — Human smoke test: live integration verification (SCRAPER-04)

### Phase 2: Workflow and Auth
**Goal**: A GitHub Actions workflow runs on a daily cron schedule, authenticates via `GITHUB_TOKEN`, and pushes one commit with a dated tag to the `data` branch on every successful run; concurrent runs are serialized
**Depends on**: Phase 1
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, RESIL-04
**Success Criteria** (what must be TRUE):
  1. A workflow run triggered manually (`workflow_dispatch`) completes successfully and a new dated tag appears in the `data` branch
  2. `git ls-remote --tags origin` shows the expected date tag after the workflow completes
  3. The workflow YAML declares `permissions: contents: write` and no SSH keys or PATs are used
  4. Two simultaneous workflow triggers result in sequential execution (second run queues, not cancels) with no duplicate commits
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Create scrape.yml workflow + YAML static tests (INFRA-01, INFRA-02, INFRA-03, INFRA-04, RESIL-04)
- [ ] 02-02-PLAN.md — Live workflow_dispatch verification checkpoint (INFRA-03, RESIL-04) — BLOCKED by Azure IP ban

### Phase 3: Gap Detection and Idempotency
**Goal**: Every workflow run checks for missing days and scrapes them sequentially; running the workflow twice for the same date is safe
**Depends on**: Phase 2
**Requirements**: RESIL-01, RESIL-02, RESIL-03
**Plans**: TBD (subsumed into v2.0 Phase 7)

### Phase 4: Operational Hardening and Backfill
**Goal**: 33-day data gap closed; push failures surface as workflow failures; system validated in production
**Depends on**: Phase 3
**Requirements**: (operational validation)
**Plans**: TBD (subsumed into v2.0 Phase 8)

</details>

---

### v2.0 Automation (In Progress)

**Milestone Goal:** Datenlücken schließen (Upstream-Sync + lokaler Backfill), Workflow auf self-hosted Runner migrieren, Gap Detection und Idempotenz implementieren, Vollbetrieb bestätigen.

#### Phase 5: Data Sync
**Goal**: The `data` branch is fully current — the 2-day upstream gap is pulled from QuantLaw, and all 33 missing days (2026-02-10 to 2026-03-13) are committed as backdated entries with dated tags
**Depends on**: Phase 1 (scraper accepts `--date`; local backfill runs scraper locally)
**Requirements**: SYNC-01, SYNC-02
**Success Criteria** (what must be TRUE):
  1. `git ls-remote --tags upstream data` confirms 2026-03-14 and 2026-03-15 tags exist in the upstream remote; after `git pull upstream data`, those tags appear in the local fork
  2. A backfill script runs the scraper once locally and creates exactly 33 backdated commits, one per date from 2026-02-10 to 2026-03-13, each with a dated tag in the `data` branch
  3. `git tag -l | sort | uniq` on the `data` branch shows no gap between 2026-02-10 and today — every date has exactly one tag
  4. The upstream sync and backfill are performed with the existing output format intact (ZIP files in `data/items/`, `not_found.txt`, `log.md`)
**Plans**: TBD

#### Phase 6: Self-hosted Runner
**Goal**: The `scrape.yml` workflow runs on a self-hosted runner (bypassing the Azure IP ban), the runner is registered and online, and a live `workflow_dispatch` run completes successfully and produces a new dated tag
**Depends on**: Phase 5 (data branch must be current before live runner creates new commits on top of it)
**Requirements**: INFRA-05, INFRA-06, INFRA-07
**Success Criteria** (what must be TRUE):
  1. `scrape.yml` declares `runs-on: self-hosted` and the runner is visible as "Online" in the GitHub repository's Settings > Actions > Runners page
  2. A `workflow_dispatch` run completes without error — the runner can reach `www.gesetze-im-internet.de` and downloads at least 100 ZIP files
  3. After the run, `git ls-remote --tags origin` shows a new dated tag for today's date in the `data` branch
**Plans**: TBD

#### Phase 7: Gap Detection and Idempotency
**Goal**: Every workflow run automatically detects and fills missing days before scraping today; repeated runs for an already-scraped day exit cleanly with no duplicate commits
**Depends on**: Phase 6 (needs live workflow on self-hosted runner to test end-to-end behavior)
**Requirements**: RESIL-01, RESIL-02, RESIL-03
**Success Criteria** (what must be TRUE):
  1. `detect_gaps.py` uses `git ls-remote --tags` (no full clone) and outputs a valid JSON list of missing dates within a 60-day lookback window; running it against a branch with a deliberate gap returns that date in the list
  2. After manually skipping one day, the next workflow run detects the missing day via `detect_gaps.py`, scrapes and commits it sequentially, then scrapes today's date — both dated tags appear in `git ls-remote --tags origin`
  3. Triggering the workflow for a date that already has a tag exits with code 0 and creates no new commit or tag — `git log --oneline -1` on the `data` branch is unchanged
**Plans**: TBD

#### Phase 8: Operational Validation
**Goal**: Every day since 2026-02-10 has a tag in the `data` branch, and a deliberate workflow failure triggers GitHub's built-in email alert with no silent green run
**Depends on**: Phase 7 (gap detection and idempotency must be in place before validating end-to-end production behavior)
**Requirements**: OPS-01, OPS-02
**Success Criteria** (what must be TRUE):
  1. `git tag -l | grep -E '^2026(02|03)' | sort | wc -l` on the `data` branch returns the expected count covering every day from 2026-02-10 through today with no gap
  2. A simulated network failure (e.g., blocking the target domain at the OS level during a test run) causes the workflow job to exit non-zero and the run appears as "Failure" in the GitHub Actions UI — not "Success"
  3. GitHub sends a failure notification email to the repository owner after the failed run (confirmed by checking inbox) — no silent green pass
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7 → 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Scraper Modernization | v1.0 | 3/3 | Complete | 2026-03-14 |
| 2. Workflow and Auth | v1.0 | 1/2 | In progress | - |
| 3. Gap Detection and Idempotency | v1.0 | 0/TBD | Deferred to v2.0 Phase 7 | - |
| 4. Operational Hardening and Backfill | v1.0 | 0/TBD | Deferred to v2.0 Phase 8 | - |
| 5. Data Sync | v2.0 | 0/TBD | Not started | - |
| 6. Self-hosted Runner | v2.0 | 0/TBD | Not started | - |
| 7. Gap Detection and Idempotency | v2.0 | 0/TBD | Not started | - |
| 8. Operational Validation | v2.0 | 0/TBD | Not started | - |
