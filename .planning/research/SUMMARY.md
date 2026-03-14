# Project Research Summary

**Project:** gesetze-im-internet GitHub Actions Migration
**Domain:** Resilient scheduled GitHub Actions scraper with git-branch data persistence
**Researched:** 2026-03-14
**Confidence:** HIGH

## Executive Summary

This project migrates a daily law-scraping pipeline from a Docker/cron setup with SSH key authentication to GitHub Actions with `GITHUB_TOKEN`. The core problem is not feature parity — it is eliminating the class of silent failures that caused a confirmed 33-day data gap (2026-02-09 to 2026-03-13). The Docker/SSH approach had no idempotency, no gap detection, and swallowed push errors silently. The GitHub Actions migration must close all three gaps simultaneously, or it recreates the same failure mode in a new environment.

The recommended architecture is a single workflow file that combines daily cron scheduling with gap detection and catch-up logic. On every run — whether triggered by cron or manually via `workflow_dispatch` — the workflow first checks which date tags are missing from the `data` branch, then scrapes each missing date sequentially, committing one tagged commit per date. This design means a missed cron run is automatically recovered the next day, with no operator intervention required. The `GITHUB_TOKEN` with explicit `contents: write` permission replaces all SSH key management, eliminating the root cause of the outage.

The primary risks are not technical complexity but operational traps: GitHub's 60-day inactivity auto-disable can recreate a "workflow silently stops running" failure unless a keepalive mechanism is added from day one; silent push failures (confirmed bug in existing `scrape.sh`) must be detected with explicit verification steps, not just `set -e`; and the gap detection mechanism must use `git ls-remote --tags` or the GitHub API rather than a full `fetch-depth: 0` clone, to prevent checkout time from growing to minutes as the `data` branch accumulates years of binary commits.

## Key Findings

### Recommended Stack

The stack is well-established with no ambiguous choices. Python 3.13 is the correct target — it is in active bugfix support until 2029 while 3.11 and 3.12 are security-only. The existing `requirements.txt` is unpinned, which means any `pip install` in CI can silently pick up a breaking dependency release. Migrating to `uv` with a committed `uv.lock` eliminates this immediately and also cuts CI dependency install time by up to 10x on fresh runners. The `astral-sh/setup-uv@v7` action handles Python version management, making `actions/setup-python` redundant.

For git authentication, `GITHUB_TOKEN` with `permissions: contents: write` is the definitive choice. PATs and SSH keys both require rotation and account coupling — exactly the failure mode being fixed. The `data` branch must remain unprotected for `GITHUB_TOKEN` to push without additional token generation steps.

**Core technologies:**
- Python 3.13: Runtime — only version in active bugfix phase (supported until Oct 2029)
- `uv` + `uv.lock`: Dependency management — replaces unpinned `requirements.txt`; reproducible, 10-100x faster than pip in CI
- `astral-sh/setup-uv@v7`: CI setup — official action from uv authors; handles Python version and caching
- `actions/checkout@v6`: Repo checkout — current stable major (v6.0.2, Jan 2025); use `fetch-depth: 1` for scraper checkout
- `GITHUB_TOKEN` with `contents: write`: Git push auth — auto-provisioned, zero maintenance, no rotation required
- `schedule` + `workflow_dispatch`: Triggers — cron at `15 4 * * *` UTC (offset avoids peak load) plus manual date input

### Expected Features

The features split cleanly into three tiers. The v1 MVP is specifically the set of features that prevents the 33-day gap from recurring and closes the existing one. Differentiators (v1.x) add observability and operator convenience but are not on the critical path.

**Must have (v1 — migration complete):**
- GitHub Actions cron workflow replacing Docker/cron — core infrastructure migration
- Idempotent runs with tag-based idempotency key — safe to re-run any date without duplicate commits
- Gap detection — compare expected daily date sequence against actual `data` branch tags
- Catch-up logic — scrape each missing date sequentially with one commit+tag per date
- Concurrency guard (`cancel-in-progress: false`) — prevents race conditions between scheduled and manual triggers
- TOC structure validation before download loop — fail fast if site structure changes rather than commit empty data
- Python 3.13 + pinned dependencies via `uv.lock` — reproducible, secure runtime

**Should have (v1.x — after 1-2 weeks stable):**
- `workflow_dispatch` with optional `target_date` input — ad-hoc backfill without YAML edits
- Structured run summary via `$GITHUB_STEP_SUMMARY` — audit-friendly markdown output per run
- ZIP integrity check — validate extracted content before committing
- Configurable parallelism via env var — replace hardcoded `Pool(2)` with `Pool(int(SCRAPER_WORKERS))`

**Defer (v2+):**
- Backfill date range input for `workflow_dispatch` — only needed for multi-week outage recovery; v1 catch-up handles the current 33-day gap automatically
- Keepalive workflow — only critical if scraper is intentionally paused for >45 days; v1 daily commits reset the 60-day timer

### Architecture Approach

The system uses the established "git scraping" pattern (Simon Willison, 2020): cron trigger, HTTP fetch of source data, commit changed files to a dedicated branch. This project extends the baseline pattern with gap detection and catch-up, which are implemented entirely through git tag inspection and sequential per-date commit loops — no external state, no database. The scraper (`scrape.py`) is kept git-unaware; all git operations happen in workflow YAML steps, making the scraper independently testable.

**Major components:**
1. Workflow YAML (`.github/workflows/scrape.yml`) — single file for cron + manual triggers, gap detection call, scraper invocation, git commit/tag/push steps
2. `detect_gaps.py` — queries `data` branch tags via `git ls-remote --tags` (not full clone), computes missing dates within a 60-day lookback window, outputs JSON list
3. `scrape.py` (modernized) — accepts `--date` CLI argument, fetches TOC XML, downloads ~150 ZIPs in parallel, writes `not_found.txt`, exits; no git operations
4. Data branch (`data`) — sole persistence layer; one commit + one date tag per scraped day; git history is the audit log

### Critical Pitfalls

1. **GITHUB_TOKEN defaults to read-only** — explicitly declare `permissions: contents: write` in workflow YAML; verify with a real push before calling the workflow done; existing `scrape.sh` already has silent push failure behavior that must not be replicated

2. **60-day inactivity auto-disables scheduled workflows** — if the scraper stops running (the failure mode being fixed), the workflow gets disabled silently after 60 days with no alert email; add `workflow_dispatch` as a secondary trigger from day one and monitor gap between last tag and today

3. **Silent push failure — "Done" logged, data lost** — `set -e` alone does not guarantee push failure propagates; after every `git push`, verify the remote tag exists with `git ls-remote --tags origin "$SCRAPE_DATE"`; GitHub's failure email is the alerting mechanism, so push failures must surface as workflow failures

4. **Catch-up creates duplicate commits for the same date** — without a concurrency group, a scheduled run and a manual run can both detect the same gap and race to commit the same date; use `concurrency: group: scraper-run, cancel-in-progress: false` and check tag existence before committing

5. **Full `data` branch checkout grows to minutes** — the `data` branch already has 1,917 commits of binary ZIP blobs; `fetch-depth: 0` for gap detection will reach multi-minute checkout within 1-2 years; use `git ls-remote --tags` after a shallow clone or the GitHub Tags API to list existing dates without blobs

## Implications for Roadmap

The build order is dictated by component dependencies, not feature priority. The scraper must accept a `--date` argument before gap detection is useful. Gap detection must work before catch-up logic can be wired into the workflow. The workflow is the integration point validated last. The existing 33-day backfill is an operational step run once after all components are verified.

### Phase 1: Environment and Scraper Modernization

**Rationale:** The scraper is the foundation. Nothing else can be built until `scrape.py` accepts a `--date` argument and runs on Python 3.13 with pinned dependencies. This phase has zero ambiguity — all choices are clear from research.
**Delivers:** A standalone, testable scraper binary that runs identically in CI and locally; reproducible dependency lockfile
**Addresses:** Python 3.7 EOL, unpinned `requirements.txt`, hardcoded `Pool(2)`, TOC validation missing, git operations coupled into scraper
**Avoids:** Non-deterministic build failures (Pitfall: unpinned deps); untestable scraper coupling (Architecture anti-pattern 4)
**Research flag:** None — standard patterns, well-documented. Skip `research-phase`.

### Phase 2: Workflow Skeleton with Core Auth

**Rationale:** Before gap detection or catch-up logic, the basic workflow must prove it can check out, run the scraper, and push to the `data` branch. `GITHUB_TOKEN` permission must be validated with a real push — this is the most common silent failure point.
**Delivers:** A working GitHub Actions workflow that runs daily and pushes one date's scraped ZIPs to the `data` branch with a date tag
**Uses:** `actions/checkout@v6`, `astral-sh/setup-uv@v7`, `GITHUB_TOKEN` with `contents: write`, manual `git commit + git tag + git push` pattern
**Implements:** Workflow YAML component; GITHUB_TOKEN authentication flow
**Avoids:** Silent push failure (Pitfall 2, Pitfall 6); SSH key anti-pattern (Architecture anti-pattern 1)
**Research flag:** None — well-documented patterns. Skip `research-phase`.

### Phase 3: Gap Detection and Idempotency

**Rationale:** Gap detection is what makes this migration meaningfully better than the old system. Idempotency is its prerequisite. These must be built together — gap detection without idempotent runs is dangerous, and idempotency without gap detection has no trigger.
**Delivers:** `detect_gaps.py` that queries existing tags via `git ls-remote --tags` (shallow, API-safe); idempotency check in commit step; catch-up loop in workflow
**Addresses:** Gap detection (v1 table stake), idempotent runs (v1 table stake), catch-up logic (v1 table stake), concurrency guard
**Avoids:** Full `data` branch clone slowdown (Pitfall 3); duplicate catch-up commits (Pitfall 4); self-referential gap detection that can't detect its own absence (Technical debt pattern)
**Research flag:** None — patterns are well-specified in research. Implementation details (lookback window = 60 days, JSON stdout interface) are decided. Skip `research-phase`.

### Phase 4: Operational Hardening and Backfill

**Rationale:** Once the workflow is proven to run cleanly, the existing 33-day gap must be closed. This phase also adds the keepalive mechanism (Pitfall 1) and verifies failure alerting (push failure must surface as workflow failure, not silent green).
**Delivers:** All 33 missing days backfilled in the `data` branch; keepalive mechanism active; push failure verification confirmed by deliberate test
**Addresses:** 60-day auto-disable (Pitfall 1), silent push failure (Pitfall 6), existing data gap
**Avoids:** Circular reasoning ("scraper runs daily so 60-day disable won't happen" is exactly the reasoning that fails when the scraper breaks)
**Research flag:** None — keepalive action is documented (`gautamkrishnar/keepalive-workflow@v2`). Skip `research-phase`.

### Phase 5: Reliability Improvements (v1.x)

**Rationale:** Once v1 has run successfully for 1-2 weeks without incident, add the differentiator features that improve observability and operator ergonomics. These are LOW implementation cost with HIGH diagnostic value.
**Delivers:** `workflow_dispatch` with optional `target_date` input; `$GITHUB_STEP_SUMMARY` run report; ZIP integrity validation; configurable parallelism via `SCRAPER_WORKERS` env var
**Addresses:** Operator ad-hoc backfill (v1.x), configurable parallelism (v1.x), ZIP corruption (v1.x)
**Research flag:** None — all patterns are standard GitHub Actions features. Skip `research-phase`.

### Phase Ordering Rationale

- Phases 1-2 are strictly sequential by dependency: scraper must exist before workflow can use it
- Phase 3 depends on Phase 2's working auth — gap detection is meaningless without a working push
- Phase 4 can only backfill after Phase 3's idempotency is in place — backfilling without idempotency would risk duplicate commits
- Phase 5 is explicitly deferred to avoid scope creep during the migration itself; these features add no reliability to v1
- The 33-day backfill is an operational step in Phase 4, not a code change — it is the first real-world test of the catch-up logic

### Research Flags

Phases with standard patterns (skip `research-phase` for all phases):
- **Phase 1:** Python 3.13 + uv patterns are fully documented with official sources
- **Phase 2:** GitHub Actions auth and checkout patterns verified against official docs
- **Phase 3:** `git ls-remote` and tag-based idempotency are established primitives
- **Phase 4:** Keepalive action is documented; backfill is operational, not architectural
- **Phase 5:** All features use standard GitHub Actions built-ins

No phase requires a `research-phase` call. All implementation decisions are resolved by the existing research.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core GitHub Actions syntax verified against official docs and release pages; uv documented via official Astral guides; all version pins verified |
| Features | HIGH | Table stakes derived directly from existing codebase analysis and project constraints; GitHub Actions behavior verified against official docs and community discussions |
| Architecture | HIGH | Patterns are well-documented (git scraping pattern, GITHUB_TOKEN flow, concurrency groups); component boundaries are clear and project-specific logic is simple |
| Pitfalls | HIGH | Critical pitfalls verified via official docs (GITHUB_TOKEN permissions, 60-day disable) and direct codebase analysis (silent push failure confirmed in `scrape.sh`) |

**Overall confidence:** HIGH

### Gaps to Address

- **GHA cron reliability SLA:** GitHub does not publish a formal SLA for scheduled workflow on-time delivery. Community evidence confirms delays and occasional drops, but exact frequency is unknown. Gap detection makes this gap irrelevant operationally — a dropped run is treated identically to any other missed day.

- **gesetze-im-internet.de rate limiting:** The site is scraped publicly, and the existing code adds a 0.25s sleep between downloads. No official rate-limit documentation was found. If the site introduces rate limiting, the parallelism increase in Phase 5 may need to be rolled back. Treat as low-risk for now.

- **Historical accuracy of catch-up ZIPs:** gesetze-im-internet.de serves current law versions only, not historical snapshots. Catch-up commits for the 33-day gap will contain today's content tagged with historical dates. This is explicitly accepted in PROJECT.md as a known limitation. Downstream consumers should be notified of this semantic caveat.

## Sources

### Primary (HIGH confidence)

- `https://github.com/actions/checkout/releases` — v6.0.2 verified as current stable
- `https://github.com/astral-sh/setup-uv/releases` — v7.5.0 verified as latest; `@v7` confirmed as major pin
- `https://docs.astral.sh/uv/guides/integration/github/` — official uv GitHub Actions integration guide
- `https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token` — GITHUB_TOKEN `contents: write` syntax
- `https://devguide.python.org/versions/` — Python version lifecycle
- `https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#permissions` — `contents: write` requirement for git push
- `https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs` — concurrency group syntax
- `https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs` — failure email behavior
- `https://simonwillison.net/2020/Oct/9/git-scraping/` — foundational git scraping pattern
- Codebase analysis: `scrape.sh`, `scrape.py`, `.planning/codebase/CONCERNS.md` — direct inspection of existing bugs

### Secondary (MEDIUM confidence)

- `https://github.com/orgs/community/discussions/156282` — GHA cron delay 15-60 min confirmed; not in official SLA docs
- `https://github.com/orgs/community/discussions/86087` — 60-day inactivity auto-disable confirmed by community and GitHub staff
- `https://github.com/marketplace/actions/keepalive-workflow` — `gautamkrishnar/keepalive-workflow@v2` implementation

---
*Research completed: 2026-03-14*
*Ready for roadmap: yes*
