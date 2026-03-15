# Phase 2: Workflow and Auth - Research

**Researched:** 2026-03-15
**Domain:** GitHub Actions — scheduled workflows, GITHUB_TOKEN authentication, git push to separate branch, concurrency serialization
**Confidence:** HIGH (core YAML mechanics), MEDIUM (concurrency edge-case behavior)

## Summary

Phase 2 creates a GitHub Actions workflow file (`.github/workflows/scrape.yml`) that runs the already-verified `scrape.py` on a daily cron schedule. The workflow must check out a separate `data` branch, install Python + uv, run the scraper into that branch's directory, commit results, push a dated tag, and do all this with the built-in `GITHUB_TOKEN` — no SSH keys or PATs.

The key non-obvious mechanics are: (1) the `data` branch must be checked out in a separate `actions/checkout` step with `ref: data`, distinct from the workflow source checkout; (2) git user identity must be set explicitly in the job for commits to work; (3) `concurrency: cancel-in-progress: false` correctly serializes two simultaneous triggers, but there is a documented architectural limit of one running + one pending slot per concurrency group — a third simultaneous trigger will displace the pending slot, but for a daily cron this is an acceptable tradeoff.

**Primary recommendation:** Use a single-job workflow with `actions/checkout@v4` (source) + `actions/checkout@v4` (data branch into a subdirectory), `astral-sh/setup-uv@v7` with `enable-cache: true`, and native `git` commands for commit + tag + push. Avoid third-party push actions — they add complexity without benefit here.

A critical gotcha: GitHub's 60-day inactivity auto-disable applies to **commits**, not tags. The daily `data` branch commit resets the counter — but this must be verified that the push happens to a branch in the **same repo** (which it does: `data` branch of `QuantLaw/gesetze-im-internet`). Tags alone do not reset the counter.

## Standard Stack

### Core
| Library / Action | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| `actions/checkout` | v4 | Clone repo content and data branch | Official GitHub action, persists credentials for subsequent `git push` |
| `astral-sh/setup-uv` | v7 | Install uv, set Python version, cache deps | Official uv action; supports `python-version: "3.13"` and `enable-cache: true` with `uv.lock` |
| `ubuntu-latest` runner | current | Linux runner for Python workload | Standard; no platform-specific issues |

### Supporting
| Feature | Mechanism | Notes |
|---------|-----------|-------|
| Auth for git push | `GITHUB_TOKEN` (auto-injected, `persist-credentials: true` default in checkout) | No additional secrets needed |
| Dependency install | `uv sync --frozen` | Respects `uv.lock` exactly; fastest for CI |
| Script invocation | `uv run scrape.py --date YYYY-MM-DD ./data-branch` | Matches Phase 1 verified CLI interface |
| Concurrency | `concurrency:` key at workflow level | Built-in GitHub Actions primitive |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native `git` commands | `ad-m/github-push-action` or `stefanzweifel/git-auto-commit-action` | Third-party actions add a pinning and supply-chain burden; native git with persisted GITHUB_TOKEN credentials is simpler and more transparent |
| `astral-sh/setup-uv@v7` | `actions/setup-python` + pip | setup-uv is purpose-built for uv projects, supports lockfile caching natively |

**Installation:** No pip install needed in the workflow; `uv sync --frozen` handles everything from `uv.lock`.

## Architecture Patterns

### Recommended Workflow Structure
```
.github/
└── workflows/
    └── scrape.yml          # single workflow file for Phase 2
```

The data branch is not stored in the workflow repo — it is a separate orphan branch of the same repository. The workflow checks it out into a local subdirectory (e.g. `./data-branch/`) at runtime.

### Pattern 1: Two-Checkout Pattern (source + data branch)

**What:** Check out workflow source in the default workspace, then check out the `data` branch into a named subdirectory in a second `actions/checkout` step.

**When to use:** Whenever a workflow needs to read its own code (scripts, config) AND write to a separate branch.

**Example:**
```yaml
# Source: https://github.com/actions/checkout
- name: Checkout workflow source
  uses: actions/checkout@v4

- name: Checkout data branch
  uses: actions/checkout@v4
  with:
    ref: data
    path: data-branch
    fetch-depth: 1          # shallow; we only need HEAD to add a commit on top
```

After this, `./data-branch/` is a live git working tree on the `data` branch with credentials persisted. Subsequent `git -C ./data-branch add .` / `git -C ./data-branch commit` / `git -C ./data-branch push` work without additional auth.

### Pattern 2: GITHUB_TOKEN Permissions Declaration

**What:** Declare `permissions: contents: write` at the workflow top level (or job level). This is required because the default repository-level setting may be "read-only" (organizations often set this).

**When to use:** Any workflow that calls `git push` or creates releases/tags via the API.

**Example:**
```yaml
# Source: https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token
permissions:
  contents: write

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      ...
```

### Pattern 3: Concurrency Serialization

**What:** `concurrency` key at workflow level with `cancel-in-progress: false`. Ensures a second simultaneous trigger queues (waits) instead of being cancelled or running in parallel.

**When to use:** Data pipelines where duplicate concurrent runs could cause merge conflicts or duplicate commits.

**Example:**
```yaml
# Source: https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs
concurrency:
  group: scrape-daily          # static string; all runs share one group
  cancel-in-progress: false
```

**Critical limitation:** GitHub enforces at most one running + one pending slot per concurrency group. If a third trigger arrives while two are already queued, the existing pending run is cancelled and replaced by the newest one. For a daily cron that fires once per day, this is irrelevant in normal operation. For two manual `workflow_dispatch` triggers fired in quick succession, the behavior is correct: first runs, second queues. A third simultaneous trigger would displace the second — document this as a known edge case.

### Pattern 4: Git Commit + Dated Tag in Data Branch

**What:** After the scraper writes files into `./data-branch/`, set git identity, stage all changes, commit with a message, create a date tag, and push branch + tag.

**When to use:** Any workflow that must commit structured data to a branch and tag for historical reference.

**Example:**
```yaml
- name: Commit and tag scraped data
  env:
    SCRAPE_DATE: ${{ steps.set-date.outputs.date }}
  run: |
    git -C data-branch config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    git -C data-branch config user.name "github-actions[bot]"
    git -C data-branch add .
    git -C data-branch commit -m "scrape $SCRAPE_DATE"
    git -C data-branch tag "$SCRAPE_DATE"
    git -C data-branch push origin data
    git -C data-branch push origin "$SCRAPE_DATE"
```

Note: the `GITHUB_TOKEN` credential is embedded in the remote URL by `actions/checkout@v4` with the default `persist-credentials: true`. No explicit `git remote set-url` needed.

### Pattern 5: Setting the Scrape Date in Workflow Context

**What:** Compute the UTC date at the start of the job and share it as a step output, so the same value is used for both the scraper `--date` argument and the git tag.

**Example:**
```yaml
- name: Set scrape date (UTC)
  id: set-date
  run: echo "date=$(date -u +%Y-%m-%d)" >> "$GITHUB_OUTPUT"

- name: Run scraper
  run: uv run scrape.py --date "${{ steps.set-date.outputs.date }}" ./data-branch
```

### Pattern 6: Full Trigger Block

```yaml
on:
  schedule:
    - cron: '0 4 * * *'   # 04:00 UTC daily (INFRA-01)
  workflow_dispatch:        # manual trigger for testing and backfill
```

### Anti-Patterns to Avoid

- **Using SSH deploy keys:** Old pattern from `scrape.sh` — replaced by `GITHUB_TOKEN` with `contents: write`. No key material to manage.
- **`git push --force` for tags:** Avoid force-pushing date tags; idempotent re-run behavior (Phase 3 RESIL-03) will handle skipping already-tagged dates before reaching the push step.
- **Global `git config --global`:** Use `git -C <path> config` (local scope) so the runner's global config is not polluted.
- **Hardcoding the date in the workflow YAML:** Always compute via `date -u` in a step; never hardcode, never rely on the runner's local timezone.
- **Checking out with `fetch-depth: 0` for the data branch:** Unnecessary — we only need HEAD; full history adds checkout time proportional to the history length.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Persisting git credentials in CI | Manual `git remote set-url` with token interpolation | `actions/checkout@v4` with default `persist-credentials: true` | The action handles token scoping, cleanup, and edge cases correctly |
| uv + Python version management | `apt-get install python3`, manual venv | `astral-sh/setup-uv@v7` with `python-version: "3.13"` | Handles pinned uv version, Python download, PATH setup, and lockfile-based caching in one step |
| Concurrency control | Shell-based lock files or external state | `concurrency:` key in workflow YAML | Native, atomic, no race conditions |
| Cron scheduling | External cron service, webhook scheduler | `schedule: cron:` trigger | Native GitHub Actions; no external dependency |

**Key insight:** GitHub Actions has native primitives for every problem in this phase. Any custom shell-based solution for auth, concurrency, or scheduling adds fragility with no benefit.

## Common Pitfalls

### Pitfall 1: Default `contents` Permission Is Read-Only in Some Orgs
**What goes wrong:** `git push` in the workflow fails with `403` or `remote: Permission to ... denied to github-actions[bot]`.
**Why it happens:** Repository or organization settings may default `GITHUB_TOKEN` to read-only. Without an explicit `permissions: contents: write` declaration, the token has no write access.
**How to avoid:** Always declare `permissions: contents: write` at the workflow (or job) level explicitly, regardless of repo settings. The requirement INFRA-02 mandates this.
**Warning signs:** Push step fails with 403; workflow logs show `Permission denied` or `Authentication failed`.

### Pitfall 2: Checkout Detached HEAD / Wrong Branch
**What goes wrong:** `git push` after commit succeeds but pushes to the wrong ref, or the `data` branch commit ends up on the workflow's trigger branch.
**Why it happens:** `actions/checkout@v4` without `ref:` defaults to the SHA that triggered the workflow (detached HEAD for schedule triggers). Commits made in detached HEAD cannot be pushed to a named branch with `git push origin data`.
**How to avoid:** Always specify `ref: data` in the second checkout step. Always specify `git -C data-branch push origin data` explicitly (not `git push`).
**Warning signs:** `git -C data-branch branch` shows `(HEAD detached at ...)` instead of `data`.

### Pitfall 3: 60-Day Auto-Disable — Tags Alone Do Not Count
**What goes wrong:** Scheduled workflow stops running after 60 days of no commits. The scraper creates dated tags in the `data` branch every day, but tags alone do not reset the inactivity counter.
**Why it happens:** GitHub's inactivity check counts only commits (confirmed in community discussion: https://github.com/orgs/community/discussions/57858). The `data` branch receives one commit per run, which DOES reset the counter — but only if the push to the `data` branch is a commit (not just a tag push).
**How to avoid:** Ensure the daily commit to `data` branch happens on every run (which it does per INFRA-03). Verify after Phase 2 is live that the counter resets (STATE.md already flags this).
**Warning signs:** Workflow shows "disabled due to 60 days of inactivity" in the Actions UI.

### Pitfall 4: Concurrency Group Name Too Broad or Too Narrow
**What goes wrong:** Too broad (e.g., `group: ${{ github.repository }}`) conflicts with other workflows; too narrow (e.g., including `github.run_id`) defeats serialization entirely.
**Why it happens:** The group string is the key — if every run generates a unique group name, they all run in parallel.
**How to avoid:** Use a static string scoped to this workflow: `group: scrape-daily`. Since this repo has only one scrape workflow, a static name is correct and safe.

### Pitfall 5: Duplicate Tag Push on Manual Re-run
**What goes wrong:** A `workflow_dispatch` manual trigger for the same date as an already-scraped day pushes a new commit but then fails on `git tag` (tag already exists).
**Why it happens:** `git tag YYYY-MM-DD` fails with `fatal: tag 'YYYY-MM-DD' already exists` if the tag was created by a prior run.
**How to avoid:** Phase 3 (RESIL-03) implements idempotency — the scraper will skip already-tagged dates before the git operations. For Phase 2, use `git tag --force` only if idempotency is not yet implemented, or document that re-running the same date without Phase 3 is not supported.
**Warning signs:** Workflow fails at `git tag` step with non-zero exit; duplicate commit appears in `data` branch history.

### Pitfall 6: RESIL-04 Email Notification Is User-Dependent
**What goes wrong:** Team expects automatic email alerts when the scraper fails; only the workflow creator (or last person to edit the cron line) receives notifications.
**Why it happens:** GitHub's built-in notification for scheduled workflow failures goes only to the user who last modified the cron trigger syntax — it is not sent to all collaborators or repo watchers automatically.
**How to avoid:** Per STATE.md, RESIL-04 is considered satisfied by the built-in notification alone. Ensure the repo owner (who created/last modified the workflow) has GitHub email notifications for Actions failures enabled in their account settings. No additional workflow code is required.
**Warning signs:** Workflow fails silently; no email received — check GitHub account notification settings at Settings > Notifications > GitHub Actions.

## Code Examples

Verified patterns from official sources:

### Complete Workflow Skeleton
```yaml
# Source: https://docs.github.com/en/actions/writing-workflows/
name: Daily Scrape

on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: scrape-daily
  cancel-in-progress: false

jobs:
  scrape:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout workflow source
        uses: actions/checkout@v4

      - name: Checkout data branch
        uses: actions/checkout@v4
        with:
          ref: data
          path: data-branch
          fetch-depth: 1

      - name: Set up uv and Python 3.13
        uses: astral-sh/setup-uv@v7
        with:
          python-version: "3.13"
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Install dependencies
        run: uv sync --frozen

      - name: Set scrape date (UTC)
        id: set-date
        run: echo "date=$(date -u +%Y-%m-%d)" >> "$GITHUB_OUTPUT"

      - name: Run scraper
        run: uv run scrape.py --date "${{ steps.set-date.outputs.date }}" ./data-branch

      - name: Commit and push to data branch
        env:
          SCRAPE_DATE: ${{ steps.set-date.outputs.date }}
        run: |
          git -C data-branch config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git -C data-branch config user.name "github-actions[bot]"
          git -C data-branch add .
          git -C data-branch commit -m "scrape $SCRAPE_DATE"
          git -C data-branch tag "$SCRAPE_DATE"
          git -C data-branch push origin data
          git -C data-branch push origin "$SCRAPE_DATE"
```

### Verifying the Tag Exists After Run
```bash
# Manual verification (INFRA-03 success criterion)
git ls-remote --tags origin | grep "refs/tags/2026-"
```

### Trigger-Only Verification (workflow_dispatch smoke test)
The INFRA-01/02/03/04 success criteria require:
1. `workflow_dispatch` completes successfully
2. `git ls-remote --tags origin` shows expected date tag
3. `permissions: contents: write` present in YAML and no SSH keys used
4. Two simultaneous `workflow_dispatch` triggers serialize (second queues, not cancels the first)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SSH deploy keys (`git@github.com:...`) | `GITHUB_TOKEN` with `permissions: contents: write` | 2021 (GitHub Actions permissions GA) | No key material to manage or rotate; scoped to run duration |
| `actions/checkout@v2/v3` | `actions/checkout@v4` | 2023 | v4 stores credentials in `$RUNNER_TEMP` (not `.git/config`), improving security |
| `pip install` / `requirements.txt` | `uv sync --frozen` + `astral-sh/setup-uv@v7` | 2024-2025 | Reproducible from `uv.lock`; 10-100x faster than pip |
| `setup-python` + pip | `astral-sh/setup-uv@v7` | 2024 | setup-uv handles Python version + uv install + lockfile-based cache in one action |

**Deprecated/outdated from `scrape.sh`:**
- `git@github.com:QuantLaw/gesetze-im-internet.git` SSH remote: replaced by GITHUB_TOKEN
- `git push git@github.com:... $SCRAPE_DATE -f` force-push of tag: use non-forced push; idempotency via Phase 3 RESIL-03
- `git config --global`: use local `git -C <path> config` instead

## Open Questions

1. **Does the `data` branch already exist in the remote repo?**
   - What we know: `scrape.sh` referenced it and the old Docker workflow pushed to it; likely it exists
   - What's unclear: Whether the branch needs to be created as an orphan branch before the workflow can check it out, or if it already exists with history
   - Recommendation: Verify with `git ls-remote --heads origin data` before running Phase 2. If missing, create it as an orphan branch with an initial commit manually (or as a Wave 0 step in the plan).

2. **Will `git push origin data` + `git push origin TAG` succeed separately, or should they be combined?**
   - What we know: Both are standard git operations; the GITHUB_TOKEN credential is embedded in the remote config by `actions/checkout`
   - What's unclear: Whether the remote URL has the token embedded in a way that supports both pushes, or if one of them needs a `--set-upstream` flag
   - Recommendation: Use `git -C data-branch push origin data` (branch push) and `git -C data-branch push origin "YYYY-MM-DD"` (tag push) as two separate commands; this is the most explicit and debuggable pattern.

3. **Exact behavior of concurrency with exactly 2 simultaneous `workflow_dispatch` triggers**
   - What we know: `cancel-in-progress: false` + one-running-one-pending limit means the first runs, the second queues
   - What's unclear: Whether there is any race condition if both are triggered within the same second (both enter the group before either starts running)
   - Recommendation: Accept this as LOW risk for a daily scraper. Document the limitation. The success criterion only requires "second run queues, not cancels" — this is the documented behavior of `cancel-in-progress: false` for the two-trigger case.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (via `uv run pytest`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` testpaths = ["tests"]) |
| Quick run command | `uv run pytest tests/ -v` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| INFRA-01 | Workflow YAML exists with `schedule: cron: '0 4 * * *'` | smoke / grep | `grep -q "0 4 \* \* \*" .github/workflows/scrape.yml` | ❌ Wave 0 |
| INFRA-02 | YAML declares `permissions: contents: write`; no SSH key references | smoke / grep | `grep -q "contents: write" .github/workflows/scrape.yml && ! grep -q "ssh-key\|deploy_key" .github/workflows/scrape.yml` | ❌ Wave 0 |
| INFRA-03 | Workflow commits + tags `data` branch on success | integration / manual | `git ls-remote --tags origin \| grep "refs/tags/$(date -u +%Y-%m-%d)"` (run after `workflow_dispatch`) | ❌ manual-only |
| INFRA-04 | `concurrency: cancel-in-progress: false` present in YAML | smoke / grep | `grep -q "cancel-in-progress: false" .github/workflows/scrape.yml` | ❌ Wave 0 |
| RESIL-04 | Workflow exits non-zero on scraper failure (enabling GitHub failure email) | manual | trigger with broken scraper; observe failure email | manual-only |

**Note:** INFRA-03 and RESIL-04 require a live GitHub Actions run for full verification. The YAML-level checks (INFRA-01, INFRA-02, INFRA-04) can be verified with grep/static analysis in the test suite.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -v` (existing 6 tests; new YAML-grep tests added in Wave 0)
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green + `workflow_dispatch` live run confirming INFRA-03 before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `.github/workflows/scrape.yml` — does not exist yet; must be created in Plan 01
- [ ] `tests/test_workflow_yaml.py` — YAML static verification tests for INFRA-01, INFRA-02, INFRA-04 (can use Python `yaml` stdlib or grep)

## Sources

### Primary (HIGH confidence)
- [GitHub Docs — Controlling permissions for GITHUB_TOKEN](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token) — `permissions: contents: write` syntax
- [GitHub Docs — Control the concurrency of workflows and jobs](https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs) — concurrency key behavior, one-running-one-pending limit
- [GitHub Docs — Notifications for workflow runs](https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs) — RESIL-04 built-in email notification behavior
- [actions/checkout GitHub repo](https://github.com/actions/checkout) — `ref:`, `path:`, `persist-credentials:` inputs; v4 security improvement
- [astral-sh/setup-uv GitHub repo](https://github.com/astral-sh/setup-uv) — v7, `python-version`, `enable-cache`, `cache-dependency-glob` inputs
- [uv GitHub Actions integration docs](https://docs.astral.sh/uv/guides/integration/github/) — `uv sync --locked`, `uv run --frozen` CI patterns

### Secondary (MEDIUM confidence)
- [GitHub community discussion #57858 — 60-day auto-disable and tags](https://github.com/orgs/community/discussions/57858) — confirmed tags alone do not reset inactivity counter; only commits do
- [GitHub community discussion #53506 — cancel-in-progress: false bug reports](https://github.com/orgs/community/discussions/53506) — confirmed one-running-one-pending architectural limit; third trigger displaces pending

### Tertiary (LOW confidence)
- Community blog posts on git commit patterns in GitHub Actions — corroborates `git -C <path> config` + `push origin <branch>` pattern; not independently verified against official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — official docs and official action repos consulted directly
- Architecture: HIGH — workflow YAML syntax verified against GitHub official docs
- Pitfalls: HIGH (auth/permissions), MEDIUM (concurrency edge cases — community-reported behavior confirmed but not in official docs), MEDIUM (60-day timer — community-confirmed, official docs lack explicit commit-vs-tag distinction)

**Research date:** 2026-03-15
**Valid until:** 2026-09-15 (GitHub Actions API is stable; setup-uv version may increment but pattern is stable)
