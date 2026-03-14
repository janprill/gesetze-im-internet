# Feature Research

**Domain:** Resilient scheduled GitHub Actions web scraper with gap detection
**Researched:** 2026-03-14
**Confidence:** HIGH (GitHub Actions behavior verified via official docs and community discussions; scraping patterns verified via git-scraping practitioner sources)

---

## Feature Landscape

### Table Stakes (Migration Fails Without These)

These are the minimum requirements for the migration to be declared successful. The current Docker/Cron setup already provides some; the migration must preserve all of them and add the ones that caused the 33-day outage.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Daily cron trigger at 04:00 UTC | Current behavior that consumers rely on | LOW | `schedule: cron: '0 4 * * *'` in workflow YAML. GitHub cron is best-effort: typically runs within 15-30 min of scheduled time, occasionally delayed up to 1h under load. |
| Commit scraped ZIPs to `data` branch on success | Existing consumers depend on this exact output format (ZIP files, dated commits, date tags) | LOW | Must preserve branch name, tag format, and directory structure. `GITHUB_TOKEN` replaces SSH key. |
| HTTP retry with exponential backoff per download | Already implemented; removing it would cause regressions on transient network errors | LOW | Existing `requests_retry_session()` logic is sound. Keep: 5 retries, backoff factor, 5xx targeting. |
| `not_found.txt` tracking for removed laws | Existing downstream behavior; consumers may diff this file | LOW | Preserve file format exactly. This is the existing workaround for gesetze-im-internet.de returning HTTP 200 with 404 HTML bodies. |
| Idempotent runs — safe to re-run for any date | Without idempotency, gap catch-up and manual re-runs corrupt data or produce duplicate commits | MEDIUM | Check whether a dated tag already exists in the data branch before writing. If tag present and data complete, skip and exit 0. Requires deterministic output (same ZIPs, same not_found.txt content for same source state). |
| Gap detection — identify missing days in data branch | Core new requirement; the 33-day outage went undetected because there was no check | MEDIUM | At workflow start, list all date tags in `data` branch. Compare against expected daily sequence from a known start date to yesterday. Emit list of missing dates. |
| Catch-up logic — re-scrape missing days | Once gaps are detected, the workflow must fill them without manual intervention | MEDIUM | Scrape each missing date by re-running the scraper with the target date's tag. Note: gesetze-im-internet.de serves current state only, not historical state. Re-scraping a past date gets today's law versions, not that day's — this is a known limitation, but still better than a permanent gap. Each catch-up run must commit with the correct historical date tag. |
| Failure alerting — notify on job failure | The 33-day outage happened because failure was silent. GitHub Actions sends email to workflow creator on failure by default. | LOW | Built-in: GitHub sends email to the user who last modified the cron expression when a scheduled workflow fails. No additional setup needed. Verify notification preferences are enabled in GitHub account settings. |
| Pinned dependency versions | Unpinned deps (`beautifulsoup4`, `lxml`, `requests`) cause non-deterministic builds; already flagged in CONCERNS.md | LOW | Pin all packages to exact versions in `requirements.txt`. Add `uv` or `pip-compile` for lock file generation. |
| Python 3.11+ | Python 3.7 is EOL since 2023-06-27, no security patches | LOW | GitHub Actions `ubuntu-latest` runners have Python 3.11+ available by default via `actions/setup-python`. |
| Prevent duplicate concurrent runs | If a catch-up triggers while the daily run is still going, they can conflict on git push | LOW | Use GitHub Actions `concurrency` group: `group: scrape-pipeline`, `cancel-in-progress: false` (queue, do not cancel). |

### Differentiators (Improve Reliability, Not Required for Launch)

Features that raise the reliability ceiling beyond "same as before but on GitHub Actions."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Keepalive workflow | GitHub disables scheduled workflows after 60 days of repository inactivity. The `data` branch receives daily commits, so the 60-day timer resets constantly — but only if the scraper keeps running. A bootstrap keepalive prevents a cold-start problem if the scraper is ever paused. | LOW | Use `gautamkrishnar/keepalive-workflow@v2`. Fires weekly, uses GitHub API (not dummy commits) to reset the timer. Only needed if scraper is intentionally paused for >45 days. |
| `workflow_dispatch` with optional date input | Allows manual re-run for a specific date via the GitHub UI or API without editing workflow files. Critical for operator-triggered backfill after extended outages. | LOW | Add `inputs.target_date` (string, default: today's date in YYYY-MM-DD). Workflow uses this input when present; falls back to `$(date +%Y-%m-%d)` for cron runs. |
| Structured run summary (GitHub Actions job summary) | Makes it easy to audit what a run did without parsing logs. Shows: date scraped, laws downloaded, laws in not_found.txt, gap dates detected, gap dates filled. | LOW | Use `$GITHUB_STEP_SUMMARY` to write markdown table. No external services needed. |
| Backfill range input for `workflow_dispatch` | Allows filling a date range (e.g., `start_date=2026-02-09, end_date=2026-03-13`) in a single manual trigger rather than running 33 sequential manual triggers | MEDIUM | Add `inputs.start_date` and `inputs.end_date`. Script iterates the date range and runs scrape+commit for each date. Respect GitHub Actions 6-hour job timeout (scraping 33 days takes ~3-5 min/day = ~2h, safely within limit). |
| ZIP integrity check after download | Silent corruption currently goes undetected (CONCERNS.md: "zip is corrupted but valid ZIP structure, content is corrupted but extraction succeeds silently") | LOW | After extraction, verify at least one file exists in the extracted directory and file sizes are non-zero. Flag corrupted items in `not_found.txt` with a distinguishing prefix. |
| Configurable parallelism via environment variable | Pool size is hardcoded at 2 (CONCERNS.md). GitHub Actions runners have 2 CPU cores by default (ubuntu-latest). 4-8 concurrent downloads would cut run time from ~3 min to ~45 sec with no memory risk. | LOW | Replace `Pool(2)` with `Pool(int(os.environ.get('SCRAPER_WORKERS', 4)))`. Set `SCRAPER_WORKERS: 4` in workflow `env`. |
| TOC structure validation before download loop | Parser silently fails if gesetze-im-internet.de changes TOC XML structure (CONCERNS.md: "Assumes item.link.get_text() always exists") | LOW | Assert minimum expected item count after parsing (e.g., >100). Fail fast with a descriptive error rather than committing an empty data set. |

### Anti-Features (Explicitly Out of Scope)

Features that seem useful for this project but would add cost without commensurate benefit.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Incremental scraping (only download changed laws) | Would reduce bandwidth and runtime from ~3 min to seconds on quiet days | gesetze-im-internet.de does not provide ETag, Last-Modified headers, or a changelog feed. Implementing incremental detection requires storing hashes of all 150 ZIPs and fetching all headers anyway — net savings are negligible. PROJECT.md explicitly marks this out of scope. | Keep full scrape per day. ~3 min runtime is well within GitHub Actions limits and the value does not justify the complexity. |
| External monitoring / health-check service | Uptime Robot / Healthchecks.io pings provide independent verification that the cron ran | Adds an external dependency and account to manage. GitHub's built-in failure email is sufficient for a daily scraper where the data branch itself is the observable state. | Use built-in GitHub failure email + inspect data branch manually on suspicious silence. |
| Database for tracking scrape state | Enables richer queries: "which laws changed on which date?" | Adds infrastructure (hosted DB), cost, auth secrets, and network dependency. Git history of the data branch already provides this: `git log --oneline data` and `git diff` answer all audit questions. | Keep git as the only state store. |
| Real-time webhook alerts (Slack, PagerDuty) | Faster failure notification than email | Requires external service credentials in GitHub secrets, integration setup, and ongoing maintenance. For a once-daily job, email within minutes is equivalent to "real-time" in practice. | GitHub's built-in failure email is sufficient. |
| Rollback mechanism (revert bad commits) | Scrape could push corrupted data | A full re-scrape is ~3 min. Automated rollback adds complexity (what is "bad"? how does it detect badness?) without a clear trigger condition. Manual `git revert` on the data branch is sufficient for the rare case. | Document the manual rollback procedure (`git push data :refs/tags/<date>`, `git push data data~1:refs/heads/data`). |
| Checkpoint/resume for partial scrapes | If scraper crashes mid-run, resume from where it stopped | Adds significant state management complexity. The full scrape takes ~3 min; crashing and restarting from scratch costs at most ~3 min extra. GitHub Actions job timeout is 6h. No checkpoint needed at this scale. | On crash, the workflow retries the entire job (idempotency makes this safe). |
| On-demand API endpoint to trigger scrape | Trigger scrape without GitHub UI access | Requires a server/serverless function outside GitHub Actions. `workflow_dispatch` via the GitHub API covers all legitimate on-demand trigger needs with zero additional infrastructure. | Use `gh workflow run scrape.yml` CLI or GitHub REST API `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches`. |

---

## Feature Dependencies

```
[Gap Detection]
    └──requires──> [Idempotent Runs]
                       └──required by──> [Catch-up Logic]

[Catch-up Logic]
    └──requires──> [Gap Detection]
    └──requires──> [Idempotent Runs]
    └──enhanced by──> [workflow_dispatch with date input]
    └──enhanced by──> [Backfill range input]

[Backfill range input]
    └──requires──> [workflow_dispatch with date input]

[Keepalive Workflow]
    └──independent (separate workflow file)

[Structured Run Summary]
    └──enhanced by──> [Gap Detection] (reports gaps found and filled)

[TOC Structure Validation]
    └──must precede──> [Download Orchestration]

[Prevent Duplicate Concurrent Runs]
    └──required by──> [Catch-up Logic] (prevents double-commit on same date tag)
```

### Dependency Notes

- **Idempotent runs requires gap detection:** Gap detection generates the list of dates to re-scrape. Without idempotency, re-scraping a date that already has data would create duplicate commits or fail on an existing tag.
- **Catch-up logic requires both gap detection and idempotency:** Gap detection supplies the target dates; idempotency ensures re-running is safe whether a partial commit exists or not.
- **Backfill range input requires workflow_dispatch date input:** The range input is an extension of the single-date input capability. Build single-date first.
- **Prevent duplicate concurrent runs required by catch-up logic:** Catch-up may trigger multiple sequential scrapes. If the cron fires while a catch-up is running, they must not race on git push. `cancel-in-progress: false` queues rather than cancels.
- **TOC validation must precede download loop:** If TOC parse returns 0 items, committing an empty data set silently destroys a day's record. Validate before any writes.

---

## MVP Definition

### Launch With (v1) — Migration Complete

Minimum set to replace Docker/Cron and close the 33-day gap.

- [ ] **GitHub Actions cron workflow** — Daily 04:00 UTC trigger with `GITHUB_TOKEN` push to `data` branch. No more Docker, no more SSH keys.
- [ ] **Python 3.11+ with pinned dependencies** — Required for secure, reproducible builds. Fixes EOL runtime and non-deterministic builds from CONCERNS.md.
- [ ] **Idempotent runs** — Check for existing date tag before writing. Re-running the same day produces identical output, not a duplicate commit or a conflict.
- [ ] **Gap detection** — On each run, compare expected daily sequence against actual tags in `data` branch. Log missing dates.
- [ ] **Catch-up logic** — For each missing date, run the scraper and commit with the historical date. Fills the 33-day gap automatically on first deployment.
- [ ] **Concurrency guard** — `concurrency: group: scrape-pipeline, cancel-in-progress: false` to serialize daily run and catch-up runs.
- [ ] **Failure alerting** — Verify GitHub notification settings send email on scheduled workflow failure. No additional setup required; just confirm.
- [ ] **TOC structure validation** — Assert >100 items parsed before starting downloads. Fail fast rather than commit empty data.

### Add After Validation (v1.x) — Reliability Improvements

Add once v1 has run successfully for 1-2 weeks.

- [ ] **`workflow_dispatch` with optional date input** — Trigger: first time an operator needs to re-scrape a specific date without pushing a commit. Enables ad-hoc backfill without editing workflow YAML.
- [ ] **Structured run summary** — Trigger: first time a run's log is too long to scan quickly. `$GITHUB_STEP_SUMMARY` markdown table showing counts and gap status.
- [ ] **ZIP integrity check** — Trigger: first time a corrupted ZIP causes a silent bad commit. Low cost, high diagnostic value.
- [ ] **Configurable parallelism** — Trigger: if run time exceeds 5 minutes. Change `Pool(2)` to `Pool(4)` via env var to cut download time roughly in half.

### Future Consideration (v2+) — Operator Convenience

Defer until v1 proves stable over 30+ days of production operation.

- [ ] **Backfill date range input** — Only needed if operators need to recover from multi-week outages frequently. One-time need for the 33-day gap is covered by automatic catch-up logic in v1.
- [ ] **Keepalive workflow** — Only needed if scraper is intentionally paused for >45 days. Not a concern during active operation since `data` branch commits reset the 60-day timer daily.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| GitHub Actions cron workflow | HIGH | LOW | P1 |
| Python 3.11+ / pinned deps | HIGH | LOW | P1 |
| Idempotent runs | HIGH | MEDIUM | P1 |
| Gap detection | HIGH | MEDIUM | P1 |
| Catch-up logic | HIGH | MEDIUM | P1 |
| Concurrency guard | HIGH | LOW | P1 |
| Failure alerting (built-in) | HIGH | LOW | P1 |
| TOC structure validation | HIGH | LOW | P1 |
| `workflow_dispatch` with date input | MEDIUM | LOW | P2 |
| Structured run summary | MEDIUM | LOW | P2 |
| ZIP integrity check | MEDIUM | LOW | P2 |
| Configurable parallelism | LOW | LOW | P2 |
| Backfill date range input | MEDIUM | MEDIUM | P3 |
| Keepalive workflow | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for migration launch (v1)
- P2: Should have, add within first month of production (v1.x)
- P3: Nice to have, add when/if triggered by operational experience (v2+)

---

## GitHub Actions Reliability Notes

These are known behaviors that affect the feature design. Confidence: HIGH (verified via GitHub community discussions and official docs).

**Cron delay:** GitHub Actions cron is best-effort, not guaranteed. Runs may be delayed 15-60 minutes. For a daily 04:00 UTC job this is irrelevant. Gap detection must use calendar dates (YYYY-MM-DD tags), not exact timestamps.

**60-day inactivity suspension:** GitHub disables scheduled workflows if no repository activity occurs for 60 days. For this project, daily commits to the `data` branch constitute activity. The 60-day timer resets with every successful scrape. A keepalive workflow is only needed if scraping pauses entirely.

**Scheduled workflow notification routing:** Email on failure goes to the user who last modified the cron expression in the workflow file. This is the operator who deployed the migration. Confirm that user's GitHub notification preferences include "GitHub Actions" failures.

**Default branch requirement:** `schedule` triggers only fire from workflows on the repository's default branch (currently `master`). The workflow file must live on `master`, not on `data` or any feature branch.

**Job timeout:** GitHub Actions jobs time out after 6 hours by default. Scraping 150 laws takes ~3 minutes. Even a 33-day catch-up backfill (~33 × 3 min = ~99 min) fits within the 6-hour limit. No custom timeout configuration needed.

---

## Sources

- [Git scraping: track changes over time by scraping to a Git repository — Simon Willison](https://simonwillison.net/2020/Oct/9/git-scraping/) — canonical reference for git-scraping pattern
- [simonw/git-scraper-template — Simon Willison, 2025](https://simonwillison.net/2025/Feb/26/git-scraper-template/) — current template pattern (MEDIUM confidence; page loaded but template internals not fully documented)
- [Notifications for workflow runs — GitHub Docs](https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs) — authoritative source on failure email behavior
- [Control the concurrency of workflows and jobs — GitHub Docs](https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs) — authoritative source on concurrency groups
- [Unexpected delay in scheduled GitHub Actions workflows — GitHub Community Discussion #156282](https://github.com/orgs/community/discussions/156282) — confirms 15-60 min cron delay behavior
- [Scheduled workflows disabled after 60 days — GitHub Community Discussion #86087](https://github.com/orgs/community/discussions/86087) — confirms 60-day inactivity policy
- [Keepalive Workflow — GitHub Marketplace](https://github.com/marketplace/actions/keepalive-workflow) — `gautamkrishnar/keepalive-workflow@v2` implementation
- [How to prevent GitHub from suspending cronjob triggers — DEV Community](https://dev.to/gautamkrishnar/how-to-prevent-github-from-suspending-your-cronjob-based-triggers-knf) — explains keepalive mechanics
- [GitHub Actions: Manual triggers with workflow_dispatch — GitHub Changelog](https://github.blog/changelog/2020-07-06-github-actions-manual-triggers-with-workflow_dispatch/) — authoritative source on workflow_dispatch capability
- [The Importance of Idempotent Data Pipelines — Prefect Blog](https://www.prefect.io/blog/the-importance-of-idempotent-data-pipelines-for-resilience) — idempotency patterns for data pipelines
- [Concurrency — GitHub Docs](https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency) — authoritative source on concurrency group syntax
- `.planning/codebase/CONCERNS.md` — primary source for existing bugs and missing features
- `.planning/PROJECT.md` — authoritative source for project constraints and out-of-scope items

---

*Feature research for: resilient GitHub Actions scraper — gesetze-im-internet*
*Researched: 2026-03-14*
