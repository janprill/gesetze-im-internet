---
phase: 01-scraper-modernization
plan: 02
subsystem: scraper
tags: [python, pytest, argparse, tdd, cli, beautifulsoup, requests]

# Dependency graph
requires:
  - phase: 01-scraper-modernization plan 01
    provides: uv project setup with pyproject.toml, dev dependencies (pytest, pytest-mock)
provides:
  - --date YYYY-MM-DD CLI argument in scrape.py with UTC default
  - TOC validation guard (MIN_EXPECTED_ITEMS=100) in scrape() before Pool(2)
  - tests/conftest.py with shared fixtures (tmp_output, mock_toc_response factory)
  - tests/test_scrape.py with 6 passing unit tests (SCRAPER-02, 03, 04)
affects:
  - 02-github-actions
  - 03-gap-detection

# Tech tracking
tech-stack:
  added: [pytest>=8.0 (test runner), pytest-mock>=3.12 (mocker fixture)]
  patterns:
    - TDD RED-GREEN-REFACTOR cycle
    - mocker.patch("scrape.Pool") to prevent actual downloads in unit tests
    - mocker.patch("scrape.requests_retry_session") to inject mock HTTP responses

key-files:
  created:
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_scrape.py
  modified:
    - scrape.py

key-decisions:
  - "Used datetime.datetime.now(datetime.timezone.utc).date().isoformat() for --date default to ensure UTC correctness, not date.today() which uses local TZ"
  - "MIN_EXPECTED_ITEMS=100 set as named constant before the guard for readability"
  - "test_date_arg_accepted and test_date_default_is_utc_today verify both parser behavior AND presence of UTC-aware default in source code"
  - "tests/__init__.py created (empty) to help pytest discover tests/ correctly"

patterns-established:
  - "TDD pattern: write failing tests first, then implement minimally to green, skip refactor if code is already clean"
  - "Pool mocking pattern: use mocker.patch('scrape.Pool', return_value=pool_context) where pool_context mocks __enter__/__exit__/starmap"
  - "HTTP session mocking: mocker.patch('scrape.requests_retry_session', return_value=mock_session_obj) where mock_session_obj.get.return_value = mock_resp"

requirements-completed: [SCRAPER-02, SCRAPER-03, SCRAPER-04]

# Metrics
duration: 3min
completed: 2026-03-14
---

# Phase 01 Plan 02: --date CLI arg, TOC validation guard, and unit tests Summary

**--date YYYY-MM-DD CLI arg with UTC default and MIN_EXPECTED_ITEMS=100 TOC guard added to scrape.py, backed by 6 pytest unit tests via TDD RED-GREEN cycle**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T20:32:35Z
- **Completed:** 2026-03-14T20:35:10Z
- **Tasks:** 2
- **Files modified:** 4 (scrape.py, tests/__init__.py, tests/conftest.py, tests/test_scrape.py)

## Accomplishments
- Replaced positional `datetime` and `data_repo_path` args with `--date YYYY-MM-DD` (optional, UTC default) and `output_dir` (positional)
- Added TOC validation guard: `scrape()` exits non-zero if fewer than 100 items are returned before spawning Pool
- Created `tests/conftest.py` with `tmp_output` directory fixture and `mock_toc_response(n)` factory
- Created `tests/test_scrape.py` with 6 tests covering SCRAPER-02/03/04 — all passing GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests (RED)** - `27115b7af` (test)
2. **Task 2: Implement --date arg and TOC guard (GREEN)** - `63206bfcf` (feat)

_Note: REFACTOR phase skipped — no behavior changes needed, code was already clean after GREEN._

## Files Created/Modified
- `/Users/jan.prill/codex/gesetze-im-internet/scrape.py` - Added `import datetime`, `import sys`; TOC guard with `MIN_EXPECTED_ITEMS=100`; replaced argparse positional `datetime`+`data_repo_path` with `--date` optional + `output_dir` positional; `args.date` in log write and print
- `/Users/jan.prill/codex/gesetze-im-internet/tests/conftest.py` - Shared fixtures: `tmp_output` (tmp_path with data/items/temp dirs), `mock_toc_response` (factory returning MagicMock with .content/.text set)
- `/Users/jan.prill/codex/gesetze-im-internet/tests/test_scrape.py` - 6 unit tests: test_date_arg_accepted, test_date_default_is_utc_today, test_toc_validation_fails_on_empty_toc, test_toc_validation_fails_on_small_toc, test_toc_validation_passes_on_sufficient_toc, test_no_git_ops_in_scrape
- `/Users/jan.prill/codex/gesetze-im-internet/tests/__init__.py` - Empty, enables pytest test discovery

## Decisions Made
- Used `datetime.datetime.now(datetime.timezone.utc).date().isoformat()` for `--date` default — ensures UTC date regardless of server timezone, not `date.today()` which is local-TZ-dependent
- `MIN_EXPECTED_ITEMS = 100` defined as a named constant before the guard for readability (not hardcoded inline)
- Date tests check both parser behavior and source-level presence of `datetime.timezone.utc` — so tests catch if someone changes the default to a non-UTC approach
- `test_toc_validation_passes_on_sufficient_toc` mocks `Pool.__enter__`/`__exit__`/`starmap` to prevent actual HTTP downloads while verifying no `SystemExit` is raised for a sufficient TOC

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `uv run scrape.py --date 2026-03-14 /some/output_dir` now works correctly
- `uv run pytest tests/ -v` passes 6/6 tests
- Ready for Phase 2 (GitHub Actions workflow integration): the `--date` arg is the hook the CI workflow uses to pass the current date to the scraper
- No blockers

---
*Phase: 01-scraper-modernization*
*Completed: 2026-03-14*

## Self-Check: PASSED

- FOUND: tests/conftest.py
- FOUND: tests/test_scrape.py
- FOUND: tests/__init__.py
- FOUND: 01-02-SUMMARY.md
- FOUND commit: 27115b7af (test RED phase)
- FOUND commit: 63206bfcf (feat GREEN phase)
