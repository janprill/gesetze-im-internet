# Stack Research

**Domain:** GitHub Actions — scheduled Python scraper with git-branch data persistence
**Researched:** 2026-03-14
**Confidence:** HIGH (core Actions syntax verified against official docs and GitHub release pages)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13 | Scraper runtime | In active "bugfix" phase (supported until Oct 2029). 3.11 and 3.12 are in "security" phase only — no binary updates, no bug fixes. 3.13 is the safe long-horizon choice for a repo intended to run unattended for years. |
| uv | latest via `astral-sh/setup-uv@v7` | Dependency install in CI | 10-100x faster than pip in CI (where no cache exists on fresh runners). Replaces pip + virtualenv in one binary. The `uv sync --frozen` command is the exact equivalent of `pip install -r requirements.txt` with guaranteed reproducibility. |
| `astral-sh/setup-uv` | v7 (major pin) | Install uv in Actions runner | Official action from Astral (uv authors). Current stable major is v7 (v7.5.0 released 2025-03-12). Handles binary download, PATH setup, and caching. Do not float to `@main`. |
| `actions/checkout` | v6 (major pin) | Clone repo in workflow | Current stable major is v6 (v6.0.2 released 2025-01-09). Uses Node.js 20. v3/v4 use older Node runtimes being deprecated. Use `fetch-depth: 0` only when gap detection needs full branch history; omit (default = 1) for daily scrape. |
| `actions/setup-python` | v6 | Set up Python version | Current stable major is v6. Use only if NOT using uv's built-in Python management. If `astral-sh/setup-uv` is configured with `python-version`, this action is redundant — skip it. |
| GitHub Actions `schedule` | N/A | Daily cron trigger | Native GHA feature. `cron: '0 4 * * *'` runs at 04:00 UTC matching existing Docker/cron schedule. No third-party service needed. |
| `GITHUB_TOKEN` | Auto-provisioned | Push commits to `data` branch | Automatically available in every workflow run. No SSH key management, no secrets rotation. Sufficient for pushing to any non-protected branch. Requires `permissions: contents: write` in workflow YAML. |

### Supporting Actions (Marketplace)

| Action | Version | Purpose | When to Use |
|--------|---------|---------|-------------|
| `stefanzweifel/git-auto-commit-action` | v7.1.0 | Stage, commit, push changed files | **Do not use** for this project — see "What NOT to Use". The manual git pattern gives precise control over commit messages, tags, and the target branch. |
| `actions/cache` | v4 | Cache uv package downloads | Optional. For a daily scraper with 3 dependencies (requests, beautifulsoup4, lxml), the setup-uv built-in cache (`enable-cache: true`) is sufficient. |

### Workflow Trigger Configuration

```yaml
on:
  schedule:
    # Daily at 04:00 UTC — matches existing cron schedule
    # Note: GHA cron can delay 10-60 min under load; this is expected behavior
    - cron: '0 4 * * *'
  workflow_dispatch:
    # Manual trigger — essential for backfill runs and gap remediation
    inputs:
      target_date:
        description: 'Date to scrape (YYYY-MM-DD). Leave empty for today.'
        required: false
        type: string
```

**Why `workflow_dispatch` is mandatory:** GitHub Actions cron is not perfectly reliable — runs can be delayed or (rarely) dropped. The gap-detection and backfill logic requires a way to trigger individual historical dates. `workflow_dispatch` with a `target_date` input covers this without a separate workflow file.

### Python Dependency Management

**Use `uv` with a lockfile (`uv.lock`).** Do not continue with unpinned `requirements.txt`.

```bash
# One-time local setup
uv init --no-package
uv add requests "beautifulsoup4>=4.12" "lxml>=5.0"
# This creates uv.lock — commit it to git
```

In CI:
```bash
uv sync --frozen   # Installs exactly what uv.lock specifies — no surprises
```

**Why lockfile over requirements.txt:** The existing `requirements.txt` has no version pins (confirmed by inspection of the file). This means `pip install` in CI could pick up a breaking release of any dependency at any time. A lockfile makes the build bit-for-bit reproducible.

### Authentication: GITHUB_TOKEN vs PAT vs GitHub App

**Use `GITHUB_TOKEN` with explicit `contents: write` permission.**

```yaml
permissions:
  contents: write   # Required to push commits to data branch
```

**Decision rationale:**

| Option | Verdict | Reason |
|--------|---------|--------|
| `GITHUB_TOKEN` (default) | **USE THIS** | Auto-provisioned, zero maintenance, sufficient for unprotected branches. The `data` branch should NOT be branch-protected (no review required for scraper pushes). |
| Personal Access Token (PAT) | Avoid | Tied to a human account. Expires or breaks if the owner changes team membership. Adds rotation overhead. SSH key management failures were the root cause of the 33-day outage — PAT has the same class of problem. |
| GitHub App token | Avoid (overkill) | Required only if `data` branch is branch-protected. Adds App registration, private key secret management, and token generation step to every run. Use only if branch protection is added later. |

**Critical constraint:** `GITHUB_TOKEN` cannot trigger a new workflow run. Since the scraper pushes to `data` branch (not `master`), this is not an issue — no recursive trigger risk.

### Canonical Workflow YAML Structure

```yaml
name: Daily Law Scraper

on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:
    inputs:
      target_date:
        description: 'Target date (YYYY-MM-DD). Empty = today.'
        required: false
        type: string

permissions:
  contents: write   # Allow pushing to data branch

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout scraper code (master branch)
        uses: actions/checkout@v6
        # Default ref: the branch that triggered the workflow (master)
        # fetch-depth: 1 is the default — sufficient for running the script

      - name: Install uv and Python 3.13
        uses: astral-sh/setup-uv@v7
        with:
          python-version: '3.13'
          enable-cache: true   # Cache uv downloads between runs

      - name: Install dependencies
        run: uv sync --frozen

      - name: Checkout data branch (into subdirectory)
        uses: actions/checkout@v6
        with:
          ref: data
          path: data_branch
          fetch-depth: 1

      - name: Run scraper
        run: uv run python scrape.py data_branch "${{ inputs.target_date || '' }}"
        # Scraper writes ZIPs into data_branch/ directory

      - name: Commit and push to data branch
        working-directory: data_branch
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A
          # Idempotent: skip commit if nothing changed
          git diff --cached --quiet && echo "No changes to commit" && exit 0
          SCRAPE_DATE="${{ inputs.target_date || '$(date -u +%Y-%m-%d)' }}"
          git commit -m "scrape: ${SCRAPE_DATE}"
          git tag -f "${SCRAPE_DATE}"
          git push origin data
          git push --force origin "${SCRAPE_DATE}"
```

**Why manual git over `git-auto-commit-action`:** The scraper needs tagged commits (existing behavior: each day's commit carries a date tag). The auto-commit action does not handle git tagging. Manual git commands give precise control and are trivial to debug. The `git diff --cached --quiet && exit 0` pattern makes runs idempotent — re-running the same day twice is safe.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `uv` with lockfile | `pip` + `requirements.txt` | Never for this project. pip has no lockfile support; uv is strictly better in CI for both speed and reproducibility. |
| `uv` | `poetry` | If the project were a library being published to PyPI. Poetry is overkill for a standalone scraper. |
| `GITHUB_TOKEN` | PAT | If branch protection rules are added to `data` branch in the future (requires PAT or GitHub App). |
| `GITHUB_TOKEN` | GitHub App | If multiple repos need the same workflow with precise token scoping. |
| `actions/checkout@v6` | `actions/checkout@v4` or `@v3` | v4 and v3 use older Node runtimes. v6 is current; use it for all new workflows. |
| Python 3.13 | Python 3.12 | Both are viable today. 3.12 is in "security" phase — still patches until Oct 2028, but no bug fix releases. Acceptable if a specific 3.12 behavior is needed. |
| Python 3.13 | Python 3.11 | 3.11 is also security-only. No reason to target 3.11 for a new workflow in 2026. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Python 3.7 (current codebase) | EOL since June 2023. No security patches for 3 years. Running EOL Python in unattended scraper is a maintenance liability. | Python 3.13 |
| Unpinned `requirements.txt` | Non-deterministic. A breaking release of `requests` or `lxml` will silently fail the daily scrape. Already the case in the current codebase. | `uv.lock` committed to repo |
| `actions/checkout@v3` or `@v4` | Use older Node runtimes (v16/v20). v6 is the current stable — always use the latest major. | `actions/checkout@v6` |
| `stefanzweifel/git-auto-commit-action` | Does not support git tagging. This project tags every commit with the scrape date — the action cannot replicate that. Using it would require a separate tagging step anyway, eliminating its convenience advantage. | Manual `git commit` + `git tag` in `run` step |
| SSH key auth for git push | SSH key management in Docker secrets was the entire reason the scraper broke for 33 days. `GITHUB_TOKEN` eliminates this entire problem class. | `GITHUB_TOKEN` with `contents: write` |
| `actions/setup-python` (standalone) | Redundant when using `astral-sh/setup-uv` with `python-version` input. Installs Python twice. | Remove it; configure Python version in `setup-uv` step instead. |
| Cron-only trigger (no `workflow_dispatch`) | With no manual trigger, backfilling the 33-day gap requires external tooling or temporary workflow hacks. `workflow_dispatch` solves this cleanly and permanently. | `schedule` + `workflow_dispatch` both declared |

---

## GitHub Actions Cron Reliability: Known Limitations

**Confidence: MEDIUM — verified against GitHub community discussions (2024-2025) and GitHub staff responses. Not an official SLA.**

GitHub Actions `schedule` is NOT a real-time cron. Known behavior:

1. **Delay (common):** Runs can start 10-60 minutes late during peak load periods, particularly at the top of the hour. A `04:00 UTC` trigger may start at `04:45 UTC`. This is acceptable for a daily scraper.

2. **Drop (rare):** Under extreme load, a run may be silently skipped entirely. This is the exact failure mode the gap-detection logic must guard against.

3. **60-day inactivity disable:** If the repository has zero commits for 60 days, GitHub automatically disables all scheduled workflows. Since the scraper commits daily to `data` branch, this risk is low during normal operation. If the scraper stops running (the failure mode being fixed), the workflow gets disabled after 60 days of silence — requiring manual re-enable. Consider a lightweight keepalive commit to `master` as a defensive measure.

4. **Fork behavior:** Scheduled workflows in forks are disabled by default. Irrelevant for this project since it runs on the canonical repo.

**Implication for gap-detection architecture:** The logic MUST NOT assume a missed day means the source data is unavailable. It means GitHub may have dropped or delayed the run. The correct response is to re-scrape that date. The `workflow_dispatch` `target_date` input is specifically designed for this recovery path.

---

## Version Compatibility

| Package | Minimum Version | Python 3.13 Compatible | Notes |
|---------|----------------|------------------------|-------|
| requests | >= 2.31 | Yes | No known issues |
| beautifulsoup4 | >= 4.12 | Yes | No known issues |
| lxml | >= 5.0 | Yes | lxml 5.x added Python 3.13 binary wheels. Pin to `>= 5.0` to avoid CI compiling from source (requires gcc, adds ~5 min). |

---

## Installation

```bash
# Install uv locally (one-time, macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Migrate from requirements.txt to uv lockfile
uv init --no-package
uv add requests "beautifulsoup4>=4.12" "lxml>=5.0"
# Commit both pyproject.toml and uv.lock
```

In GitHub Actions (uv binary downloaded automatically by setup-uv):
```yaml
- uses: astral-sh/setup-uv@v7
  with:
    python-version: '3.13'
- run: uv sync --frozen
```

---

## Sources

- `https://github.com/actions/checkout/releases` — Verified v6.0.2 (Jan 2025) as current stable; README confirms `@v6` as recommended pin — HIGH confidence
- `https://github.com/actions/setup-python/releases` — Verified v6.2.0 (Jan 2025) as current stable — HIGH confidence
- `https://github.com/astral-sh/setup-uv/releases` — Verified v7.5.0 (Mar 12, 2025) as latest; `@v7` is the current major pin — HIGH confidence
- `https://docs.astral.sh/uv/guides/integration/github/` — Official uv GitHub Actions integration guide; shows `@v7` syntax — HIGH confidence
- `https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token` — Official GITHUB_TOKEN `contents: write` permissions syntax — HIGH confidence
- `https://devguide.python.org/versions/` — Python version lifecycle: 3.13 = bugfix phase, 3.11/3.12 = security phase — HIGH confidence
- `https://github.com/orgs/community/discussions/156282` and related GH community threads — GHA cron delay and drop confirmed by community and GitHub staff — MEDIUM confidence (community reports, not official SLA documentation)
- `https://github.com/stefanzweifel/git-auto-commit-action/releases` — Confirmed v7.1.0 (Dec 2024) as latest; evaluated git tagging limitations against project requirements — HIGH confidence

---
*Stack research for: gesetze-im-internet GitHub Actions migration*
*Researched: 2026-03-14*
