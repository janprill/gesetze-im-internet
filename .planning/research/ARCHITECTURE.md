# Architecture Research

**Domain:** GitHub Actions scheduled scraper with gap-detection and catch-up logic
**Researched:** 2026-03-14
**Confidence:** HIGH (core GitHub Actions patterns are well-documented; gap-detection is project-specific logic built on primitives)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Actions Runner                        │
│                                                                  │
│  ┌────────────────────┐     ┌──────────────────────────────┐    │
│  │  Workflow Trigger  │     │     Gap Detection Step        │    │
│  │  (cron / manual)  │────▶│  git log → date list →       │    │
│  └────────────────────┘     │  missing_days[]              │    │
│                              └──────────────┬───────────────┘    │
│                                             │                    │
│                              ┌──────────────▼───────────────┐    │
│                              │      Scraper (Python)         │    │
│                              │  for each target_date:        │    │
│                              │    fetch TOC → download ZIPs  │    │
│                              │    → write not_found.txt      │    │
│                              └──────────────┬───────────────┘    │
│                                             │                    │
│                              ┌──────────────▼───────────────┐    │
│                              │     Git Commit Step           │    │
│                              │  for each scraped_date:       │    │
│                              │    git add → git commit       │    │
│                              │    → git tag → git push       │    │
│                              └──────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
         │                                         │
         ▼                                         ▼
┌─────────────────┐                    ┌───────────────────────┐
│ gesetze-im-     │                    │  GitHub Repository    │
│ internet.de     │                    │  (data branch)        │
│  gii-toc.xml    │                    │  data/items/          │
│  *.xml.zip      │                    │  data/not_found.txt   │
└─────────────────┘                    │  data/log.md          │
                                       └───────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Workflow YAML | Trigger (cron + manual), job definition, secret injection, permissions | `.github/workflows/scrape.yml` |
| Gap Detection | Check data branch git tags against expected date range, produce list of missing dates | Python script or inline shell using `git tag -l` |
| Scraper | Fetch TOC XML, download ~150 ZIPs, extract, write not_found.txt | `scrape.py` (modernized) |
| Commit / Tag Step | Stage changes, commit with date-based message, create date tag, push | Shell step in workflow using `GITHUB_TOKEN` |
| Data Branch | Persistent storage of all scraped snapshots, one commit + tag per day | `data` branch in same repo |

## Recommended Project Structure

```
.github/
└── workflows/
    └── scrape.yml          # Single workflow: schedule + manual trigger + gap logic

scrape.py                   # Core scraper — TOC fetch, parallel ZIP downloads, not_found tracking
detect_gaps.py              # Gap detection — queries data branch tags, returns missing dates
requirements.txt            # Pinned dependencies (requests, beautifulsoup4, lxml)
```

### Structure Rationale

- **Single workflow file:** The gap detection and catch-up loop both happen inside one workflow run. A separate workflow for catch-up is unnecessary complexity — the scheduled job IS the catch-up job.
- **Separate detect_gaps.py:** Isolating gap detection makes it independently testable and keeps the workflow YAML readable.
- **No `src/` nesting:** This is a two-file tool. Deep directory structure adds navigation cost with zero benefit.

## Architectural Patterns

### Pattern 1: Schedule + Manual Trigger on Same Workflow

**What:** A single workflow file responds to both `schedule` (daily cron) and `workflow_dispatch` (manual trigger with optional date override). The scheduled path runs gap detection automatically; the manual path allows backfilling a specific date.

**When to use:** Any scraper that needs both automation and operator control without maintaining two workflow files.

**Trade-offs:** Slightly more complex trigger logic, but eliminates drift between two workflow definitions.

**Example:**
```yaml
on:
  schedule:
    - cron: '0 4 * * *'   # 04:00 UTC daily
  workflow_dispatch:
    inputs:
      target_date:
        description: 'Date to scrape (YYYY-MM-DD). Leave empty for gap-detection mode.'
        required: false
        type: string
```

### Pattern 2: Git Tag as Idempotency Key

**What:** Each successful scrape creates a git tag named `YYYY-MM-DD` on the data branch. Gap detection reads existing tags (`git tag -l`) and computes missing dates. Scraping a date that already has a tag is a no-op (skip or overwrite depending on policy).

**When to use:** Whenever the data store IS the git repo. Tags are cheap, queryable, and require no external state.

**Trade-offs:** Tags can be deleted/moved accidentally. Force-push of tags (`-f`) is needed for reruns — acceptable for a data repo with no external consumers of the tag objects themselves.

**Example:**
```python
# detect_gaps.py
import subprocess
from datetime import date, timedelta

def existing_dates(lookback_days=60):
    result = subprocess.run(
        ["git", "tag", "-l", "--sort=version:refname"],
        capture_output=True, text=True, check=True
    )
    return set(result.stdout.strip().splitlines())

def missing_dates(lookback_days=60):
    today = date.today()
    expected = {
        (today - timedelta(days=i)).isoformat()
        for i in range(1, lookback_days + 1)  # yesterday back N days
    }
    return sorted(expected - existing_dates(lookback_days))
```

### Pattern 3: Per-Date Commit Loop (Catch-up)

**What:** The workflow iterates over each missing date, runs the scraper for that date, commits with a backdated commit message and the date's git tag, then moves to the next date. Each iteration is independent — if one fails, prior commits are already persisted.

**When to use:** When you need to reconstruct historical snapshots as if they had been scraped on the correct day.

**Trade-offs:** Catch-up of many days (e.g., 33 days of gap) increases job duration. GitHub Actions has a 6-hour job limit — 33 days at ~5 min/day = ~2.75 hours, comfortably within limit for this dataset.

**Example:**
```python
# In workflow step or entrypoint
for target_date in missing_dates():
    run_scraper(target_date)
    git_commit_and_tag(target_date)
```

## Data Flow

### Normal Daily Run (No Gap)

```
04:00 UTC cron trigger
    │
    ▼
actions/checkout (data branch, full history for tag inspection)
    │
    ▼
detect_gaps.py
    │ git tag -l → compare against [today-1 .. today-60]
    ▼
missing_dates = [yesterday]   (only one missing date in normal operation)
    │
    ▼
scrape.py --date yesterday
    │ fetch https://www.gesetze-im-internet.de/gii-toc.xml
    │ parse XML → extract ~150 item URLs
    │ parallel download *.xml.zip → extract to data/items/{id}/
    │ write data/not_found.txt
    ▼
git add data/
git commit -m "scrape 2026-03-13" --date 2026-03-13T04:00:00
git tag 2026-03-13 -f
git push origin data
git push origin 2026-03-13 -f
```

### Catch-up Run (Gap Detected)

```
04:00 UTC cron trigger  (or manual workflow_dispatch)
    │
    ▼
detect_gaps.py → missing_dates = [2026-02-09, 2026-02-10, ... 2026-03-13]
    │
    ▼
FOR EACH date IN missing_dates:
    │
    ├─ scrape.py --date {date}
    │    └─ downloads all ~150 laws as of today
    │       (NOTE: gesetze-im-internet.de has no historical API;
    │        catch-up ZIPs reflect current content, not the date's content)
    │
    └─ git commit -m "scrape {date}" --date {date}T04:00:00
       git tag {date} -f
       git push origin data
       git push origin {date} -f
    │
    ▼ (repeat for next date)
```

### GITHUB_TOKEN Authentication Flow

```
Workflow job starts
    │
    ▼
GitHub injects GITHUB_TOKEN into job environment
(scoped to this repository only, expires when job ends)
    │
    ▼
actions/checkout configures git credential helper automatically:
    git remote set-url origin https://x-access-token:${GITHUB_TOKEN}@github.com/...
    │
    ▼
git push origin data        ← uses injected credential, no SSH keys needed
git push origin {tag} -f    ← same credential
```

### State Management

- **Persistence layer:** `data` git branch in same repository — no external database
- **Idempotency key:** Git date tag (`YYYY-MM-DD`) — presence means "already scraped"
- **No in-memory state:** Each workflow run is stateless; all state lives in git history
- **Lookback window:** Gap detection checks N days back (recommended: 60 days) to bound cost

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| gesetze-im-internet.de | HTTP GET `gii-toc.xml` + per-item `*.xml.zip` | No auth required. Rate-limit politely (0.25s sleep between items). |
| GitHub (data branch) | `actions/checkout ref: data` + `git push` via GITHUB_TOKEN | `contents: write` permission required in workflow. |
| GitHub Actions scheduler | `schedule: cron` on workflow default branch | Delays of 15-30 min are common; not exact. Gap detection handles missed runs. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Workflow YAML ↔ detect_gaps.py | Workflow calls `python detect_gaps.py`, reads stdout (JSON list of dates) | Keep interface minimal: dates in, dates out. |
| Workflow YAML ↔ scrape.py | Workflow calls `python scrape.py --date YYYY-MM-DD --output-dir ./data` | Date and output path as CLI args. |
| scrape.py ↔ data branch | scrape.py writes files to checked-out data branch working directory | Workflow handles git operations separately — scraper is git-unaware. |
| Workflow ↔ GitHub API | Git push via GITHUB_TOKEN (HTTP, not SSH) | Replaces the Docker/SSH key approach entirely. |

## Anti-Patterns

### Anti-Pattern 1: SSH Key Management in Actions

**What people do:** Reuse the Docker/SSH pattern — store a private key as a GitHub secret, add it to `ssh-agent` in the workflow, clone via `git@github.com:...`.

**Why it's wrong:** Unnecessary complexity. `GITHUB_TOKEN` is automatically injected by GitHub for the repo running the workflow. `actions/checkout` configures the git credential helper automatically. SSH keys need rotation; `GITHUB_TOKEN` does not.

**Do this instead:** Use `actions/checkout` with `persist-credentials: true` (the default) and `git push` directly. Set `permissions: contents: write` in the workflow.

### Anti-Pattern 2: Separate Workflow for Catch-up

**What people do:** Create a second workflow (`catchup.yml`) triggered by `workflow_dispatch` for backfill operations, separate from the daily `scrape.yml`.

**Why it's wrong:** Two workflow files diverge over time. The catch-up logic is identical to normal scraping — just iterated over multiple dates. A single workflow with gap detection handles both cases.

**Do this instead:** One workflow. Gap detection makes the daily run automatically catch up when it finds missing dates. Add `workflow_dispatch` with an optional `target_date` input for emergency manual overrides.

### Anti-Pattern 3: Checking Out Entire data Branch History on Every Run

**What people do:** `git clone --depth=unlimited` the data branch to inspect commit messages for gap detection.

**Why it's wrong:** The data branch accumulates years of commits. Full clone is expensive and slow for a simple date check.

**Do this instead:** Use `git tag -l` to list date tags. Tags are lightweight and fetched by default. Alternatively, use the GitHub REST API (`/repos/{owner}/{repo}/tags`) for zero-clone gap detection.

### Anti-Pattern 4: Embedding git Operations Inside scrape.py

**What people do:** Have the Python scraper itself perform `git add`, `git commit`, `git push`.

**Why it's wrong:** Couples scraping logic to git infrastructure. Makes the scraper untestable in isolation. Makes it impossible to do a dry-run scrape without committing.

**Do this instead:** Scraper writes files to a directory. Workflow YAML handles all git operations as separate steps after the scraper exits successfully.

### Anti-Pattern 5: Committing All Catch-up Dates in One Giant Commit

**What people do:** Scrape all missing dates, then do a single `git commit` with all changes.

**Why it's wrong:** Loses per-date granularity. The core value is one commit per day, each with a date tag, so consumers can check out `git checkout 2026-02-15` to see that day's laws.

**Do this instead:** One commit + one tag per date, pushed immediately. If the job fails mid-catch-up, already-committed dates are preserved.

## Build Order Implications

The components have a clear dependency chain that dictates build order:

```
1. scrape.py (modernized, date-parameterized, git-unaware)
        ↓ required before
2. detect_gaps.py (queries data branch tags)
        ↓ required before
3. Workflow YAML (wires trigger → gap detection → scraper → git commit)
        ↓ integration test
4. Manual catch-up run (fill the existing 33-day gap)
```

**Rationale:** The scraper must accept a `--date` argument before gap detection is useful. Gap detection must produce a reliable date list before the workflow can iterate over it. The workflow is the integration point tested last. The catch-up run is a one-time operational step after all components are verified.

## Scaling Considerations

This architecture handles a fixed-size dataset (~150 laws, daily). Scaling is not a concern. The only operational dimension that changes is the catch-up window.

| Scenario | Impact | Approach |
|----------|--------|----------|
| Normal daily run | ~5-10 min, 1 date | No change needed |
| 33-day gap (current situation) | ~2.75 hours at 5 min/date | Within 6-hour Actions limit; acceptable |
| 6-month gap | ~15 hours | Split into multiple workflow_dispatch runs with date ranges |
| Laws list grows to 500 | Longer per-date scrape | Increase parallelism in Python pool; still within limits |

## Sources

- [GitHub Actions automatic token authentication](https://docs.github.com/en/actions/security-guides/automatic-token-authentication) — MEDIUM confidence (confirmed: GITHUB_TOKEN is auto-injected, scoped to repo)
- [Workflow syntax — permissions](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#permissions) — HIGH confidence (confirmed: `contents: write` needed for git push)
- [Git scraping pattern — Simon Willison](https://simonwillison.net/2020/Oct/9/git-scraping/) — HIGH confidence (foundational pattern: cron + checkout + conditional commit + push)
- [GitHub Actions cron reliability](https://github.com/orgs/community/discussions/156282) — HIGH confidence (confirmed: 15-30 min delays common, runs not guaranteed exact)
- [workflow_dispatch inputs](https://github.blog/changelog/2020-07-06-github-actions-manual-triggers-with-workflow_dispatch/) — HIGH confidence (string inputs for date parameters are standard)
- [actions/checkout](https://github.com/marketplace/actions/checkout) — HIGH confidence (ref parameter for specific branch; persist-credentials default behavior)
- Existing codebase analysis (`scrape.sh`, `docker/cron.sh`, `scrape.py`) — HIGH confidence (current behavior directly inspected)

---
*Architecture research for: gesetze-im-internet GitHub Actions migration*
*Researched: 2026-03-14*
