---
phase: 01-scraper-modernization
plan: "01"
subsystem: infra
tags: [uv, python, pyproject-toml, lockfile, dependencies]

# Dependency graph
requires: []
provides:
  - pyproject.toml with Python 3.13 constraint and pinned runtime deps (requests, beautifulsoup4, lxml)
  - uv.lock with fully-resolved, reproducible lockfile (281 lines)
  - .python-version pinned to 3.13
  - Dev dependency group with pytest and pytest-mock
  - [tool.pytest.ini_options] configured for tests/ directory
affects:
  - 01-02 (test scaffold uses pytest from this dev group)
  - Phase 2 CI workflow (uv sync --frozen reads this lockfile)

# Tech tracking
tech-stack:
  added: [uv 0.10.10, beautifulsoup4 4.14.3, lxml 6.0.2, requests 2.32.5, pytest 9.0.2, pytest-mock 3.15.1]
  patterns: [uv-managed Python project, dependency-groups for dev deps, frozen lockfile installs]

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - .python-version
  modified: []

key-decisions:
  - "Used uv init --no-package to avoid src/ layout that would break uv run scrape.py"
  - "lxml>=5.0 lower bound required — lxml <5.0 has no binary wheels for Python 3.13, causing C source compilation on CI"
  - "uv installed via official installer (curl https://astral.sh/uv/install.sh) as it was not present on the system"

patterns-established:
  - "uv add / uv sync --frozen pattern: add deps with uv add, install reproducibly with uv sync --frozen"
  - "dev dependency group [dependency-groups.dev] for test tooling instead of requirements_dev.txt"

requirements-completed: [SCRAPER-01]

# Metrics
duration: 8min
completed: 2026-03-14
---

# Phase 1 Plan 01: uv Migration Summary

**Python 3.13 environment with uv-managed pyproject.toml, frozen uv.lock (281 lines), and retired unpinned requirements.txt files**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-14T20:26:16Z
- **Completed:** 2026-03-14T20:34:00Z
- **Tasks:** 2
- **Files modified:** 5 (pyproject.toml created, uv.lock created, .python-version created, requirements.txt deleted, requirements_dev.txt deleted)

## Accomplishments

- Initialized uv project with `requires-python = ">=3.13"` and no `[build-system]` block
- Generated uv.lock with all runtime and dev dependencies fully pinned (281 lines)
- Deleted unpinned requirements.txt and requirements_dev.txt — uv is now the single authoritative source
- Verified `uv run scrape.py --help` exits 0 and `uv run python --version` reports Python 3.13.5

## Task Commits

Each task was committed atomically:

1. **Task 1: Initialize uv project and pin Python 3.13** - `ee9a2dbc5` (chore)
2. **Task 2: Add runtime and dev dependencies, generate uv.lock, retire old files** - `8d489efa7` (chore)

## Files Created/Modified

- `pyproject.toml` - uv project config with Python 3.13 constraint, runtime deps, dev group, pytest config
- `uv.lock` - Reproducible lockfile (281 lines) — committed to git for CI reproducibility
- `.python-version` - Pins Python to 3.13 for uv toolchain
- `requirements.txt` - Deleted (replaced by pyproject.toml + uv.lock)
- `requirements_dev.txt` - Deleted (replaced by [dependency-groups.dev])

## Resolved Versions (uv.lock)

| Package | Resolved Version |
|---------|-----------------|
| requests | 2.32.5 |
| beautifulsoup4 | 4.14.3 |
| lxml | 6.0.2 |
| pytest | 9.0.2 |
| pytest-mock | 3.15.1 |

## Decisions Made

- Used `uv init --no-package` — the `--no-package` flag prevents uv from creating a `src/` layout that would break `uv run scrape.py`
- Set `lxml>=5.0` lower bound — lxml <5.0 has no binary wheels for Python 3.13 and causes C source compilation failures on CI
- Installed uv via the official installer (curl https://astral.sh/uv/install.sh) because uv was not present on the system; this is a deviation (Rule 3 — blocking issue)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing uv tool**
- **Found during:** Before Task 1 (uv not found on PATH)
- **Issue:** `which uv` returned not found; `uv init` could not be run
- **Fix:** Installed uv 0.10.10 via `curl -LsSf https://astral.sh/uv/install.sh | sh` (official installer)
- **Files modified:** None (system-level install to ~/.local/bin)
- **Verification:** `uv --version` returned `uv 0.10.10`
- **Committed in:** N/A (system tool install, not a code change)

**2. [Rule 1 - Bug] Deleted auto-generated main.py**
- **Found during:** Task 1 (after uv init)
- **Issue:** `uv init` created a `main.py` which the plan explicitly requires to be absent
- **Fix:** Deleted main.py with `rm`
- **Files modified:** main.py (deleted)
- **Verification:** `ls main.py` returns not found
- **Committed in:** ee9a2dbc5 (Task 1 commit)

**3. [Rule 1 - Bug] Force-removed requirements.txt with -f flag**
- **Found during:** Task 2 (git rm rejected due to unstaged modification)
- **Issue:** `requirements.txt` had an unstaged modification (the original file had trailing newline issues visible to git), causing `git rm` to reject without `-f`
- **Fix:** Used `git rm -f requirements.txt requirements_dev.txt`
- **Files modified:** requirements.txt (deleted), requirements_dev.txt (deleted)
- **Verification:** Both files absent after the operation
- **Committed in:** 8d489efa7 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking tool install, 2 rule-1 bug fixes)
**Impact on plan:** All auto-fixes necessary to complete the migration. No scope creep.

## Issues Encountered

- uv was not installed on the system — installed via official installer before proceeding (deviation Rule 3)
- git rm rejected requirements.txt due to an unstaged modification — resolved with -f flag

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `uv sync --frozen` works without compilation steps
- `uv run scrape.py --help` exits 0 confirming uv can invoke the script
- `[tool.pytest.ini_options]` configured for Plan 02 test scaffold
- Plan 02 (test scaffold) can proceed — pytest is installed in the dev dependency group

---
*Phase: 01-scraper-modernization*
*Completed: 2026-03-14*

## Self-Check: PASSED

- pyproject.toml: FOUND
- uv.lock: FOUND
- .python-version: FOUND
- requirements.txt: CONFIRMED DELETED
- requirements_dev.txt: CONFIRMED DELETED
- Task 1 commit ee9a2dbc5: FOUND
- Task 2 commit 8d489efa7: FOUND
