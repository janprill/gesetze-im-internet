# Pitfalls Research

**Domain:** GitHub Actions scheduled scraper — daily data pipeline with git-branch persistence
**Researched:** 2026-03-14
**Confidence:** HIGH (GitHub official docs + community reports + codebase analysis)

---

## Critical Pitfalls

### Pitfall 1: Scheduled Workflows Auto-Disabled After 60 Days of Repo Inactivity

**What goes wrong:**
GitHub automatically disables scheduled workflow triggers when no repository activity (commits, PRs, issues) has been detected for 60 days. The workflow file remains, the cron expression remains — but the job simply never runs. The exact failure message is: "This scheduled workflow is disabled because there hasn't been activity in this repository for at least 60 days." There is no email alert. GitHub Actions' built-in failure notifications do not fire because, from GitHub's perspective, nothing failed — the schedule was simply suspended.

**Why it happens:**
GitHub introduced this policy to reclaim runner capacity. The `data` branch receives a commit every day the scraper runs — but if the scraper itself is broken, commits stop, and the 60-day clock starts. The failure then prevents its own recovery: the scraper can't auto-fix because it's disabled, and no new commits arrive to re-enable it.

For this project, the `data` branch had ~1,917 commits spanning years. There are already known gaps (e.g., 2026-02-04 → 2026-02-06 gap visible in git log). If the new GitHub Actions workflow goes down for any reason and 60 days pass without a commit, the scheduled trigger is silently suspended.

**How to avoid:**
- Add a `keepalive` workflow that fires on `schedule` separately (e.g., weekly) and uses the GitHub API to ping the repository even when the main scraper fails. The `actions/gh-keepalive` pattern or the `gautamkrishnar/keepalive-workflow` action handles this.
- Alternatively, add `workflow_dispatch` as a secondary trigger so the workflow can always be manually re-enabled without code changes.
- Monitor the gap between the last tag in `data` and today's date — if > 2 days, alert.

**Warning signs:**
- Last tag in `git tag --list | sort | tail -1` is more than 1-2 days old.
- No GitHub Actions run visible in the "Actions" tab for the scheduled workflow within the past 24 hours.
- GitHub UI shows "Disabled" next to the workflow name in the Actions tab.

**Phase to address:** Workflow setup phase (earliest). The keepalive mechanism must be built into the first workflow iteration, not added later.

---

### Pitfall 2: GITHUB_TOKEN Contents Permission Defaults to Read-Only

**What goes wrong:**
The workflow commits and pushes to the `data` branch using `GITHUB_TOKEN`. On many repositories — especially those created or modified recently — the default `GITHUB_TOKEN` permission for `contents` is `read`, not `write`. Attempting `git push` fails silently or with a cryptic authentication error: `remote: Permission to org/repo.git denied to github-actions[bot].`

This is particularly insidious because the push error does not necessarily make the workflow exit with a non-zero code unless `set -e` or explicit exit-code checking is in place. The existing `scrape.sh` already has this bug: incomplete error handling on `git push` failures means the script continues and logs "DONE" even when the push failed.

**Why it happens:**
GitHub changed the default token permissions for new repos (and updated org-level defaults) toward `read-only` for security. Developers assume GITHUB_TOKEN always has write access because older repos did, or because the docs list write access as "available." The permission must be explicitly declared in the workflow YAML.

**How to avoid:**
Declare permissions explicitly in the workflow YAML at the job level:
```yaml
permissions:
  contents: write
```
Do not rely on repository-level defaults. Explicitly verify push success with a non-zero exit code check after every `git push`. Do not use `set -e` as the sole guard — check `$?` explicitly after the push step.

**Warning signs:**
- Workflow run shows green but `data` branch has no new commit.
- `git push` step output contains "Permission denied" or "403" buried in step logs.
- `GITHUB_TOKEN` permission not explicitly declared in workflow YAML.

**Phase to address:** Workflow setup phase. Must be validated with a real push before the workflow is considered done.

---

### Pitfall 3: Checkout of `data` Branch Grows Slower Every Day

**What goes wrong:**
The `data` branch currently has 1,917 commits and grows by one per day. Each commit adds ~150 ZIP files. `actions/checkout` with default settings performs a shallow clone (`fetch-depth: 1`), which is fast. However, the gap-detection logic needs to inspect commit history (dates of previous commits / tags) to know which days are missing. If the workflow fetches full history (`fetch-depth: 0`) to enumerate tags, checkout time grows linearly year over year as history accumulates.

With a full fetch of the `data` branch containing years of daily binary ZIP commits, checkout could reach minutes rather than seconds within 1-2 years.

**Why it happens:**
Gap detection is typically implemented by listing git tags or scanning commit messages for dates. This appears simple but requires either full tag listing (`git tag --list`) or full log traversal (`git log --pretty=format:"%s"`). Both require fetching enough history. Developers fetch `fetch-depth: 0` as the "safe" option without measuring the cost.

**How to avoid:**
Design gap detection to work without full history:
- Store the last-successfully-scraped date in a file within the `data` branch (e.g., `last_scrape.txt`) alongside the ZIP data. This file is accessible with `fetch-depth: 1`.
- Use the GitHub API (`/repos/{owner}/{repo}/git/refs/tags`) to list tags without cloning — no git checkout needed at all.
- If git tags must be inspected locally, use `git ls-remote --tags origin` after a shallow clone — this fetches tag refs without blobs or tree objects.

Keep `fetch-depth: 1` for the actual file checkout. Separate the "what date is today" and "what was last scraped" concerns from "what files do I need to commit."

**Warning signs:**
- Checkout step runtime increasing month over month (visible in Actions run history).
- Workflow uses `fetch-depth: 0` without a documented reason.
- Gap detection logic traverses `git log` output.

**Phase to address:** Gap detection phase. Design the state-storage mechanism before implementing gap detection.

---

### Pitfall 4: Catch-Up Runs Creating Duplicate Commits for the Same Day

**What goes wrong:**
When the scraper detects a gap (e.g., 33 missed days as currently exists) and runs catch-up, it executes multiple scrape runs in sequence or in parallel. If idempotency is not enforced, running twice for the same date creates two commits with the same date tag. The second `git tag $SCRAPE_DATE -f` force-pushes the tag, which silently overwrites the first run's data. If both runs push non-force tags, the second push fails with "tag already exists." Either outcome corrupts the intended history.

The existing `scrape.sh` already uses `git push ... $SCRAPE_DATE -f` (force tag push) — this means a duplicate catch-up run would silently overwrite a valid completed scrape.

**Why it happens:**
Catch-up logic is typically implemented as "for each missing date, run the scraper." If two catch-up runs overlap (e.g., manual trigger + scheduled trigger both detect the same gap), both attempt to commit the same date. The developer assumes only one run happens at a time, but GitHub Actions has no built-in mutual exclusion across separate runs without explicit concurrency configuration.

**How to avoid:**
- Use a `concurrency` group on the workflow to ensure only one run executes at a time:
  ```yaml
  concurrency:
    group: scraper-run
    cancel-in-progress: false  # do NOT cancel — let it finish
  ```
  With `cancel-in-progress: false`, a second triggered run queues instead of cancelling the first.
- Before committing for a date, check whether the tag already exists: `git ls-remote --tags origin "$SCRAPE_DATE"`. Skip the commit if the tag is found.
- Do not use force-push for date tags — a failed push (tag exists) becomes the idempotency guard rather than silently overwriting data.

**Warning signs:**
- Two workflow runs active simultaneously in the Actions tab.
- `git push -f` used for date tags anywhere in the workflow.
- No check for existing tags before committing catch-up dates.

**Phase to address:** Gap detection and catch-up phase. Idempotency must be built into the commit step, not assumed.

---

### Pitfall 5: Cron Schedule Silently Skips or Delays Under GitHub Load

**What goes wrong:**
GitHub explicitly states that scheduled workflows "are not guaranteed to run at the scheduled time." During high-load periods (especially midnight UTC, which is when many workflows are scheduled), cron triggers can be delayed by 30+ minutes or silently dropped entirely. A dropped run means a missing day in the archive — the exact failure mode this migration aims to prevent.

Delays are distinct from drops: a delayed run at 04:00 UTC that actually runs at 04:30 is fine. A dropped run where the job simply never starts creates a data gap with no error notification.

**Why it happens:**
GitHub's scheduler is a shared system across all public and private repositories. Peak scheduling times create queuing pressure. The `0 4 * * *` cron is a common scheduling choice (off-peak UTC), which reduces but does not eliminate risk. There is no built-in retry if a scheduled run is dropped.

**How to avoid:**
- Run at a non-peak time that avoids round-hour crowds: e.g., `15 4 * * *` (4:15 UTC) instead of `0 4 * * *`.
- Add a `workflow_dispatch` trigger so a missed run can be manually triggered without code changes.
- Implement gap detection as the primary reliability mechanism — if yesterday's scrape is missing, today's run catches up. This makes the system resilient to any single dropped run.
- Use an external dead-man's-switch (Healthchecks.io, Cronitor) to alert when the expected daily "heartbeat" commit does not appear in the `data` branch.

**Warning signs:**
- Workflow scheduled at exactly `0 0`, `0 12`, or other round-hour UTC times.
- No `workflow_dispatch` trigger on the workflow.
- No external monitoring for missed scrape days.
- Gap detection only runs when the scraper itself runs (self-referential gap detection can't catch its own absence).

**Phase to address:** Workflow setup phase (cron scheduling) and gap detection phase (recovery mechanism).

---

### Pitfall 6: git push Failure is Silent — "Done" Logged, Data Lost

**What goes wrong:**
The existing `scrape.sh` uses `set -e` but the `git push` failure may not trigger a shell exit in all cases. If `git push` fails (network error, auth failure, rejected non-fast-forward), the script reaches the end and exits 0, cron reports success, but no data was persisted. On the next run, `not_found.txt` is rewritten from scratch — lost data from the failed commit is never recovered.

In GitHub Actions, the same failure mode applies: a push step that returns non-zero will fail the step, but only if the step is configured to check it. Using shell scripts that swallow errors or using `continue-on-error: true` can mask push failures.

**Why it happens:**
Push failures are rare in normal operation, so they're not tested. `set -e` gives developers confidence that errors propagate — but `git push` failures don't always produce non-zero exit codes in every shell wrapper scenario. The assumption of "push works or workflow fails" is not guaranteed without explicit verification.

**How to avoid:**
- After every `git push`, explicitly verify the push succeeded by checking that the remote tag exists: `git ls-remote --tags origin "$SCRAPE_DATE" | grep -q "$SCRAPE_DATE"`.
- Structure the GitHub Actions step to fail the run (not just log a warning) if the push fails.
- Never use `set -e` alone as the push guard — add explicit `|| exit 1` on the push command.
- The GitHub Actions run failure automatically sends an email notification — this is the alerting mechanism, so push failures must surface as workflow failures.

**Warning signs:**
- `git push` not followed by a verification step.
- `continue-on-error: true` on any git step.
- Shell scripts wrapping git commands without explicit exit code checks.
- `not_found.txt` being the only artifact persisted (it's rewritten each run, so lost commits are invisible).

**Phase to address:** Workflow setup phase (commit/push step implementation).

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `fetch-depth: 0` for gap detection | Simplest implementation, all tags visible | Checkout grows to minutes as history accumulates; 5+ year daily history = 1,800+ commits with binary blobs | Never — use API-based tag listing or a state file instead |
| Force-push date tags (`-f`) | Allows re-running for same date | Silently overwrites valid completed scrapes if a duplicate run occurs | Never for date tags — use non-force push as idempotency guard |
| No concurrency group on workflow | Less configuration | Two simultaneous runs (e.g., scheduled + manual) corrupt the same date's data | Never for this scraper |
| Relying on `set -e` alone for push error detection | Simpler scripting | Push failures can be silent, data is lost without alerting | Never when data persistence is the core value |
| Hardcoding `Pool(2)` multiprocessing | Works for current ~150 files | Race condition on shared temp paths under load or higher pool size | Acceptable short-term if pool size is not increased |
| Checking for gaps only at scrape time | No extra tooling needed | A completely dropped run can't detect its own absence | Never — gap detection must be independent of the scraper running |
| No pinned Python dependencies | Faster initial setup | Non-deterministic builds; breaking changes in BS4/lxml/requests on next `pip install` | Never for a production pipeline that must be reproducible |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GitHub GITHUB_TOKEN | Assuming default token has `contents: write` | Explicitly declare `permissions: contents: write` in workflow YAML |
| actions/checkout | Using `fetch-depth: 0` because gap detection needs history | Use GitHub API to list tags; use a state file for last-scraped date; keep checkout shallow |
| `git push` in Actions | Trusting exit code propagation through shell scripts | Verify push success independently by checking remote tag existence |
| gesetze-im-internet.de | Treating HTTP 200 + 404 HTML as a success | Parse response body for `<title>404 Not Found</title>` — already done but fragile; prefer checking Content-Type header |
| GitHub Actions cron | Scheduling at `0 * * * *` or midnight UTC | Use an offset like `15 4 * * *` to avoid peak load times |
| GitHub Actions auto-disable | Assuming active scraper prevents 60-day disable | Add a keepalive workflow; monitor for gap > 2 days independently |
| Catch-up loop | Running all missed dates concurrently | Run sequentially in oldest-first order; use concurrency group to prevent parallel triggers |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full git clone of `data` branch | Checkout time grows from seconds to minutes | Shallow clone + API-based tag listing | After ~3 years of daily commits (~1,100 commits with binary blobs) |
| Downloading all ~150 laws unconditionally | No problem at ~3 min runtime today; saturates 6-hour GitHub Actions limit if laws grow to 1,000+ | Check ETag/Last-Modified headers, skip unchanged files | If gesetze-im-internet.de grows significantly in scope |
| `Pool(2)` with shared temp paths | Race condition in multiprocessing (currently a known bug) | Use per-worker temp directories; or replace Pool with `asyncio`/`httpx` | Under higher pool sizes or fast SSDs that expose timing gaps |
| No runner caching for pip dependencies | ~30-60 seconds per run for `pip install` | Cache pip packages with `actions/cache` keyed on `requirements.txt` hash | Minor cost today, adds up over years of daily runs |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing SSH private key in Docker secrets and migrating that pattern to Actions secrets | Long-lived credential; secret rotation is manual; key compromise exposes push access | Use GITHUB_TOKEN (scoped to the repo, auto-rotated per run) — this is the correct migration path |
| Using `git config --global user.email` inside the runner | Pollutes global git config in shared runner environments | Use `git config --local` scoped to the repository clone |
| Committing with hardcoded bot identity "Scraper" | No audit differentiation between scraper versions; hard to blame-trace | Include workflow run ID in commit message: `scrape $DATE (run $GITHUB_RUN_ID)` |
| No validation that pushed ZIP files are genuine ZIPs | Corrupted or HTML "404" content committed as `.zip` silently | Validate with `zipfile.testzip()` before committing; reject and alert on corrupted archives |
| Running workflow with overly broad permissions | Token could be used beyond push if the workflow is compromised | Declare minimal permissions: only `contents: write`, nothing else |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Workflow runs green:** Verify that a tag actually appears on the remote `data` branch — a green run does not guarantee a successful push if push errors are swallowed.
- [ ] **Gap detection implemented:** Verify it can detect a gap that starts *today* (i.e., if this run is the first after a long outage, does the catch-up run all missing days or only yesterday?).
- [ ] **Catch-up is idempotent:** Manually trigger the workflow twice in rapid succession for the same date — verify only one commit results, not two.
- [ ] **60-day keepalive tested:** Confirm a mechanism exists to prevent auto-disable; do not rely on "the scraper runs daily so we won't hit 60 days" — that reasoning is circular.
- [ ] **Push failure is visible:** Deliberately break the GITHUB_TOKEN permission and confirm the workflow fails with a non-zero exit code (not a silent green).
- [ ] **Dependency versions pinned:** `pip install` in the workflow YAML must reference a lockfile or pinned `requirements.txt`, not unpinned package names.
- [ ] **Historical gap backfill verified:** After the migration, confirm all 33+ currently-missing days (since 2026-02-09) are filled with commits, and that the new commits are in correct chronological order.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Workflow auto-disabled (60-day inactivity) | LOW | Re-enable workflow in GitHub UI → Actions tab → click workflow → "Enable workflow". Then trigger manually via `workflow_dispatch`. Gap detection handles missing dates. |
| GITHUB_TOKEN permission denied on push | LOW | Add `permissions: contents: write` to workflow YAML, commit and push to master. |
| Duplicate commit for same date (force-push overwrote valid data) | MEDIUM | `git log data` to identify the overwritten commit SHA (if still in reflog). Restore with `git reset`. If reflog expired, re-run the scraper for the affected date manually. |
| Checkout taking too long (> 10 min) | MEDIUM | Switch to API-based gap detection (no checkout needed for date listing). Use `fetch-depth: 1` for file checkout. No history rewrite required. |
| Cron trigger dropped silently (missed day, no alert) | LOW | `workflow_dispatch` trigger allows manual re-run. Gap detection handles the catch-up. Add external monitoring (Healthchecks.io) to prevent future silent drops. |
| Push failure silently logged (data lost for a day) | HIGH | Data cannot be recovered — gesetze-im-internet.de provides no historical versions. Prevention is the only viable strategy: verify push success explicitly in every run. |
| Python dependency breaks due to unpinned version | MEDIUM | Pin all dependencies to currently-installed versions (`pip freeze > requirements.txt`). Rebuild. Test against live site before re-enabling schedule. |
| Concurrent catch-up runs corrupt same-date tag | MEDIUM | Identify which run's data is correct (likely the one that finished last). Delete the date tag, re-run for that date, verify result. Add concurrency group to prevent recurrence. |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 60-day auto-disable | Workflow setup | Check GitHub Actions tab after 3 days — confirm keepalive fires independently of scraper success |
| GITHUB_TOKEN read-only | Workflow setup | Break permission deliberately, confirm workflow fails visibly |
| Slow `data` branch checkout | Gap detection design | Measure checkout time with `time` before and after; keep under 30 seconds |
| Duplicate catch-up commits | Gap detection + catch-up | Trigger workflow twice simultaneously, count resulting commits |
| Cron silently dropped | Workflow setup + monitoring | Confirm `workflow_dispatch` works; add external monitor |
| Silent push failure | Workflow setup (commit/push step) | Test with read-only token; verify failure produces non-zero exit |
| Unpinned dependencies | Environment setup | `pip install -r requirements.txt` must produce identical installed set across two clean environments |
| Concurrent run corruption | Gap detection + catch-up | Confirm `concurrency: group: scraper-run` is set; run simultaneous triggers |
| Catch-up overwrites valid data | Gap detection + catch-up | Check that non-force tag push fails gracefully when tag already exists |

---

## Sources

- [GitHub Docs: Controlling permissions for GITHUB_TOKEN](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token)
- [GitHub Docs: Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [GitHub Docs: Control workflow concurrency](https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs)
- [GitHub Community: Unexpected delay in scheduled GitHub Actions workflows](https://github.com/orgs/community/discussions/156282)
- [GitHub Community: Scheduled workflow auto-disable at 60 days](https://github.com/orgs/community/discussions/86087)
- [GitHub Community: Allowing github-actions[bot] to push to protected branch](https://github.com/orgs/community/discussions/25305)
- [DEV Community: How to prevent GitHub from suspending cronjob-based triggers](https://dev.to/gautamkrishnar/how-to-prevent-github-from-suspending-your-cronjob-based-triggers-knf)
- [Depot Blog: Why 98.5% of organizations have slow actions/checkout](https://depot.dev/blog/why-organizations-have-slow-actions-checkout)
- [GitHub actions/checkout: suggestions for large repository](https://github.com/actions/checkout/issues/22)
- [CICube: How to Schedule Workflows in GitHub Actions](https://cicube.io/blog/github-actions-cron/)
- [DevActivity: Troubleshooting GitHub Actions Cron Delays](https://devactivity.com/insights/github-actions-cron-delays-a-community-insight-into-engineering-workflow-scheduling/)
- [GitHub Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies)
- [GitHub Community: Is scraping permitted within GitHub Actions usage?](https://github.com/orgs/community/discussions/183117)
- Codebase analysis: `scrape.sh`, `scrape.py`, `.planning/codebase/CONCERNS.md` (2026-03-14)
- Git history analysis: `data` branch — 1,917 commits, last commit 2026-02-09, 33-day gap confirmed

---
*Pitfalls research for: GitHub Actions scheduled scraper migration (gesetze-im-internet)*
*Researched: 2026-03-14*
