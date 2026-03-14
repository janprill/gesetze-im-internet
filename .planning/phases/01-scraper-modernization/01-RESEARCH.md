# Phase 1: Scraper Modernization - Research

**Researched:** 2026-03-14
**Domain:** Python scraper modernization — uv dependency management, argparse CLI, TOC validation, git operation removal
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCRAPER-01 | Scraper runs on Python 3.13 with pinned dependencies via `uv.lock` | uv init + uv add workflow documented; Python 3.13 confirmed as current bugfix-phase release |
| SCRAPER-02 | Scraper accepts `--date YYYY-MM-DD` argument to scrape and commit for a specific date | argparse `--date` pattern documented; existing positional `datetime` arg must be replaced |
| SCRAPER-03 | Scraper validates TOC structure (>100 items parsed) before starting downloads and fails fast if invalid | assertion + `sys.exit(1)` pattern before Pool creation; source line identified in scrape.py |
| SCRAPER-04 | Scraper preserves existing output format (ZIP files in `data/items/`, `not_found.txt`, `log.md`, dated git tags) | output paths identified in scrape.py lines 94-98; git operations belong only in workflow YAML, not scrape.py |
</phase_requirements>

---

## Summary

Phase 1 is a focused modernization of the existing `scrape.py` file. The codebase is already functional Python with correct HTTP retry logic, ZIP extraction, and parallel download patterns. The work is strictly additive and surgical: add a `--date` CLI argument, add a TOC item count assertion, replace the unpinned `requirements.txt` with a `uv`-managed `pyproject.toml` + `uv.lock`, and remove the four git operations that currently live in `scrape.sh` (which are out of scope for `scrape.py` itself). No new libraries are needed. No architectural changes to the download logic.

The output format — ZIP files in `data/items/`, `not_found.txt`, `log.md` — must be preserved exactly. Downstream consumers depend on this structure. The `--date` argument controls what date string is written to `log.md`; it does not change what content is downloaded (gesetze-im-internet.de serves only current state, not historical snapshots).

The core risk in this phase is breaking the existing working behavior during the modernization. The `uv` migration is the highest-impact change: it replaces `pip` + `requirements.txt` with a lockfile-based workflow. All other changes (argparse, TOC validation, removing git ops from the Python script) are low-risk and isolated.

**Primary recommendation:** Migrate to `uv` with `pyproject.toml` first, verify `uv run scrape.py` works with existing behavior, then add `--date` argument, then add TOC validation. Three sequential PRs or commits — each verifiable independently.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13 | Scraper runtime | Current bugfix-phase release (supported until Oct 2029). 3.11/3.12 are security-only. 3.7 is EOL since 2023-06-27. |
| uv | latest (astral-sh/setup-uv@v7) | Dependency management + lockfile | Replaces pip + venv in one binary. `uv.lock` gives bit-for-bit reproducibility that unpinned `requirements.txt` cannot provide. 10-100x faster than pip in CI. |
| requests | >=2.31 | HTTP downloads with retry | Already used; no change. Keep `requests_retry_session()` pattern. |
| beautifulsoup4 | >=4.12 | XML TOC parsing | Already used. `BeautifulSoup(toc.text, "lxml-xml")` pattern preserved exactly. |
| lxml | >=5.0 | XML parser backend | lxml 5.x has Python 3.13 binary wheels. Pin to >=5.0 to avoid CI compiling from source (which requires gcc and adds ~5 min). lxml <5.0 has no 3.13 wheels. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0 | Test framework | Wave 0 gap — no tests exist. Needed for nyquist validation of SCRAPER-03 (TOC validation) and SCRAPER-02 (argparse). |
| pytest-mock | >=3.12 | HTTP mock for tests | Use to mock `requests_retry_session()` without live network calls in unit tests. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| uv | poetry | Poetry is designed for library publishing to PyPI. Overkill for a standalone scraper. uv is lighter and faster. |
| uv | pip-compile | pip-compile is pip-tools-based. uv supersedes it with better performance and a single binary. |
| lxml | xml.etree.ElementTree | stdlib has no third-party dependency, but BeautifulSoup's "lxml-xml" parser mode is already in use and the codebase has no fallback. Keep lxml. |

**Installation:**

```bash
# One-time migration (run locally in project root)
curl -LsSf https://astral.sh/uv/install.sh | sh    # install uv if not present
uv init --no-package                                # create pyproject.toml (no src layout)
uv add requests "beautifulsoup4>=4.12" "lxml>=5.0"  # pin deps, generates uv.lock
git add pyproject.toml uv.lock
git rm requirements.txt requirements_dev.txt         # retire the old files
```

In CI (Phase 2 workflow — for reference, not Phase 1 scope):
```bash
uv sync --frozen    # installs exactly what uv.lock specifies
uv run scrape.py --date 2026-03-14 /path/to/data
```

---

## Architecture Patterns

### Recommended Project Structure After Phase 1

```
scrape.py              # Modernized: --date arg, TOC validation, no git ops
pyproject.toml         # uv project config + dependency declarations
uv.lock                # Pinned lockfile — committed to git
tests/
├── conftest.py        # Shared fixtures (mock HTTP session, temp dirs)
└── test_scrape.py     # Unit tests for TOC validation and arg parsing
requirements.txt       # DELETED — replaced by uv.lock
requirements_dev.txt   # DELETED — merged into uv dev dependencies
docker/                # Unchanged — Docker artifacts left as-is for now
scrape.sh              # Unchanged — shell wrapper left as-is for now
```

### Pattern 1: uv `--no-package` Init for Script Projects

**What:** `uv init --no-package` creates a minimal `pyproject.toml` without the `[build-system]` and `[tool.uv.sources]` sections that would be needed for a publishable package. This is the correct form for a standalone script that is not distributed as a Python package.

**When to use:** Any project that is a tool or script rather than a library. This project is a tool.

**Example:**
```toml
# pyproject.toml (generated by uv init --no-package, then uv add ...)
[project]
name = "gesetze-im-internet"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "requests>=2.31",
]

[tool.uv]
# No [build-system] block — this is a script, not a package
```

### Pattern 2: `--date` CLI Argument Replacing Positional `datetime`

**What:** The current signature is `scrape.py data_repo_path datetime` (two positional args). The new signature is `scrape.py --date YYYY-MM-DD output_dir` (one optional named flag + one positional for the output directory).

**When to use:** Any scraper that needs to be driven by an external orchestrator (GitHub Actions workflow) passing in a specific date.

**Critical constraint from SCRAPER-04:** The existing consumers expect `log.md` to record the date. The `--date` argument provides the string written to `log.md`. It is NOT used to select what content is downloaded — gesetze-im-internet.de has no date-parameterized API.

**Example:**
```python
# Source: current scrape.py lines 87-91 → modernized pattern
import argparse
from datetime import date

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        type=str,
        default=date.today().isoformat(),
        help="Scrape date label (YYYY-MM-DD). Written to log.md. Default: today.",
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="Path to the data output directory (checked-out data branch root).",
    )
    args = parser.parse_args()
    # args.date  → written to log.md
    # args.output_dir → replaces current data_repo_path argument
```

**Backwards-compatibility note:** The current positional `data_repo_path` argument becomes the `output_dir` positional. The current positional `datetime` argument is removed — its job is now done by `--date`. The shell wrapper `scrape.sh` calls `python scrape.py /data_branch $SCRAPE_DATETIME` — this shell wrapper is NOT changed in Phase 1 (it is Docker-based infrastructure that Phase 2 replaces). No risk of breaking production until Phase 2 rewires the call site.

### Pattern 3: TOC Validation Guard Before Download Loop

**What:** After fetching and parsing the TOC XML, assert that the item count is above a minimum threshold (>100) before entering the parallel download pool. If the assertion fails, print a descriptive error and exit non-zero. This prevents committing an empty or truncated data set.

**When to use:** Any scraper that uses an external TOC/manifest as the source of truth for download URLs. A truncated TOC means "don't download anything" — not "download nothing."

**Example:**
```python
# Source: scrape.py lines 69-73 → insert validation before Pool()
soup = BeautifulSoup(toc.text, "lxml-xml")
links = [item.link.get_text() for item in list(soup.find_all("item"))]

MIN_EXPECTED_ITEMS = 100
if len(links) < MIN_EXPECTED_ITEMS:
    print(
        f"ERROR: TOC validation failed. Expected >={MIN_EXPECTED_ITEMS} items, "
        f"got {len(links)}. Aborting before download.",
        file=sys.stderr,
    )
    sys.exit(1)

# Only reach Pool() if TOC is valid
with Pool(2) as p:
    ...
```

### Pattern 4: Removing Git Operations From `scrape.py`

**What:** The current `scrape.py` has no git operations — all git work happens in `scrape.sh`. However, the success criteria for SCRAPER-04 explicitly states "all git operations are absent from `scrape.py`." This is a verification requirement, not a change requirement. Confirm during implementation that no git calls are present and that none are accidentally introduced.

**Anti-Patterns to Avoid:**
- **Introducing subprocess git calls in scrape.py:** The scraper must be git-unaware. It writes files to a directory. The workflow or shell wrapper handles all git operations.
- **Changing the `data/items/` directory structure:** Existing consumers diff against known paths. Do not rename or reorganize.
- **Writing datetime strings instead of YYYY-MM-DD to log.md:** The old code wrote a datetime string (`$SCRAPE_DATETIME` like `2026-03-14T04:00:00`). The `--date` argument should accept and write `YYYY-MM-DD` — verify expected format with ROADMAP.md success criterion 1 which shows `--date 2026-03-14`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dependency lockfile | Custom pinning logic in requirements.txt | uv + uv.lock | uv handles transitive deps, platform markers, hash verification automatically |
| HTTP retry with backoff | Custom retry loop | `requests.adapters.HTTPAdapter` + `urllib3.util.retry.Retry` | Already in use; handles connection, read, and status-code retries correctly |
| XML parsing | Custom regex on TOC XML | `BeautifulSoup(toc.text, "lxml-xml")` | Already in use; handles namespaces, malformed XML more robustly than regex |
| Argument validation | Manual `sys.argv` parsing | `argparse` | Already used; `type=` and `default=` handle type coercion and defaults |
| Temporary directory cleanup | Manual `os.remove` + `shutil.rmtree` on exception paths | `tempfile.TemporaryDirectory()` as context manager | Current code uses manual cleanup (lines 84, 105-106) and will leave temp files on crash. Context manager is automatic. HOWEVER: changing this is out of scope for Phase 1 unless it causes test failures. |

**Key insight:** The existing `scrape.py` already has good bones. The "don't hand-roll" principle applies primarily to the `uv` migration — do not attempt to implement a custom lockfile solution.

---

## Common Pitfalls

### Pitfall 1: lxml <5.0 Has No Python 3.13 Wheels

**What goes wrong:** `uv add lxml` without a lower bound may resolve to lxml 4.x, which has no pre-built binary wheel for Python 3.13. `uv sync` will attempt to compile lxml from C source, which requires `gcc` and `libxml2-dev`. On a bare macOS or GitHub Actions runner without these, the install fails.

**Why it happens:** The unpinned `requirements.txt` currently installs whatever lxml version is latest. On Python 3.13, latest lxml (5.x) has wheels — but an under-constrained `uv add lxml` could resolve to an older version if the solver has a reason to.

**How to avoid:** Always specify `uv add "lxml>=5.0"` to guarantee a version with 3.13 binary wheels.

**Warning signs:** `uv sync` output shows "Building lxml..." or "compiling...". Install takes >60 seconds. `gcc: command not found` errors.

### Pitfall 2: `uv init` Creates a `main.py` and a `src/` Layout

**What goes wrong:** Running `uv init` without `--no-package` creates a package project with a `src/` directory and an `__init__.py`. Running `uv run scrape.py` then fails because uv tries to install the package, which may conflict with the project name or structure.

**Why it happens:** `uv init` defaults to a package project. This project is a standalone script, not a package.

**How to avoid:** Use `uv init --no-package`. This creates a minimal `pyproject.toml` without build system configuration and does not create `src/` or `main.py`.

**Warning signs:** `uv init` creates a `src/gesetze_im_internet/` directory. `uv run scrape.py` fails with an import error or "no module named" error.

### Pitfall 3: `--date` Default of "Today" Uses Local TZ, Not UTC

**What goes wrong:** `date.today()` returns the local machine's date, which may differ from UTC by +/- 1 day depending on timezone. A scraper run at 23:30 UTC on March 13 on a machine in UTC+1 would log `2026-03-14` to log.md while the data represents March 13 content.

**Why it happens:** `datetime.date.today()` is timezone-naive and uses the system clock.

**How to avoid:** Use `datetime.datetime.now(datetime.timezone.utc).date().isoformat()` for the default date value. This is consistent with the GitHub Actions runner, which runs in UTC.

**Warning signs:** Local tests pass but CI produces a different date in `log.md`. Log entries are off by one day.

### Pitfall 4: TOC Validation Runs After Writing Files

**What goes wrong:** TOC validation placed after partial state initialization (TEMP_PATH created, TOC file written) exits non-zero but leaves orphaned directories behind. On the next run, `os.makedirs` may behave unexpectedly if directories already exist.

**Why it happens:** The current code creates directories before calling `scrape()` (lines 107-109). If `scrape()` is where validation happens and it exits, the directories exist but are empty.

**How to avoid:** Validation (item count check) must happen before any file system writes. The `scrape()` function already fetches TOC and parses it as its first action — placing the guard immediately after `links = [...]` and before any `Pool()` call is correct. The directories created in main (lines 107-109) are a minor issue — on next run they already exist and `ensure_exists()` handles that gracefully.

**Warning signs:** After a validation failure, `data/temp/` and `data/items/` directories exist but are empty.

### Pitfall 5: pytest Import Fails Because `scrape.py` Is Not a Module

**What goes wrong:** `import scrape` in test files fails because `scrape.py` has a `if __name__ == "__main__":` block that calls `main()` on import in some Python versions, or because uv's project structure doesn't put the project root on `sys.path`.

**Why it happens:** `scrape.py` is a standalone script, not a module in a package. pytest must be configured to find it.

**How to avoid:** Add a `conftest.py` in the project root (or `tests/`) that adds the project root to `sys.path`. The `if __name__ == "__main__":` guard in `scrape.py` prevents `main()` from running on import — confirm this guard is in place.

**Warning signs:** `ModuleNotFoundError: No module named 'scrape'` in pytest output.

---

## Code Examples

Verified patterns from codebase analysis and official sources:

### uv Project Initialization (One-Time Migration)

```bash
# Source: https://docs.astral.sh/uv/guides/projects/ (official uv docs)
# Run from project root, with Python 3.13 already installed
uv init --no-package
uv python pin 3.13
uv add requests "beautifulsoup4>=4.12" "lxml>=5.0"
# Generates: pyproject.toml, uv.lock, .python-version
# Commit all three files
```

### pyproject.toml Minimal Template

```toml
# Source: uv official docs — script project (no-package) layout
[project]
name = "gesetze-im-internet"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "requests>=2.31",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
]
```

### Running the Modernized Scraper Locally

```bash
# Source: uv docs — uv run invocation
uv run scrape.py --date 2026-03-14 /path/to/data-branch-checkout
```

### TOC Validation Guard (Insert in scrape.py After Link Extraction)

```python
# Source: codebase analysis — scrape.py lines 69-73
import sys

MIN_EXPECTED_ITEMS = 100

links = [item.link.get_text() for item in list(soup.find_all("item"))]

if len(links) < MIN_EXPECTED_ITEMS:
    print(
        f"ERROR: TOC returned {len(links)} items (minimum {MIN_EXPECTED_ITEMS}). "
        "Aborting scrape to avoid committing empty data.",
        file=sys.stderr,
    )
    sys.exit(1)
```

### Argparse `--date` Pattern

```python
# Source: codebase analysis — scrape.py lines 87-91, modernized
import argparse
import datetime

def main():
    parser = argparse.ArgumentParser(description="Scrape gesetze-im-internet.de")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        metavar="YYYY-MM-DD",
        help="Date label for this scrape run. Written to log.md. Default: today (UTC).",
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="Root of the checked-out data branch directory.",
    )
    args = parser.parse_args()
```

### Test Skeleton for TOC Validation (Wave 0 Gap)

```python
# Source: project pattern — pytest unit test
# tests/test_scrape.py
import sys
import pytest
from unittest.mock import MagicMock, patch

def test_toc_validation_fails_on_empty_response(tmp_path, monkeypatch):
    """SCRAPER-03: scraper exits non-zero if TOC has fewer than 100 items."""
    from scrape import scrape

    mock_response = MagicMock()
    mock_response.content = b"<items></items>"
    mock_response.text = "<items></items>"

    with patch("scrape.requests_retry_session") as mock_session:
        mock_session.return_value.get.return_value = mock_response
        with pytest.raises(SystemExit) as exc_info:
            scrape(
                TEMP_PATH=str(tmp_path / "temp") + "/",
                ITEMS_PATH=str(tmp_path / "items") + "/",
                TOC_PATH=str(tmp_path / "toc.xml"),
                NOT_FOUND_PATH=str(tmp_path / "not_found.txt"),
            )
    assert exc_info.value.code != 0
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pip + unpinned requirements.txt | uv + uv.lock | 2024-2025 (uv 1.0 release) | Reproducible builds; 10-100x faster CI installs |
| Python 3.7 (EOL) | Python 3.13 | EOL: 2023-06-27 | Security patches; binary wheels for lxml 5.x |
| Positional datetime argument | `--date YYYY-MM-DD` named flag | Phase 1 | Workflow can pass date explicitly; default is UTC today |
| No TOC validation | Assert >100 items before downloads | Phase 1 | Prevents silent empty-data commits |
| Git ops in scrape.sh | Git ops in GitHub Actions workflow YAML | Phase 2 | Separates scraping from infrastructure; scraper is testable |

**Deprecated/outdated:**
- `requirements.txt` / `requirements_dev.txt`: Replaced by `pyproject.toml` + `uv.lock`. Delete both files after migration.
- `Dockerfile` / `docker-compose.yml` / `docker/`: Docker infrastructure is superseded by GitHub Actions in Phase 2. Leave untouched during Phase 1 — do not delete until Phase 2 is validated.

---

## Open Questions

1. **Minimum item count threshold (100)**
   - What we know: The TOC currently returns ~150 items (PROJECT.md and FEATURES.md reference "~150 laws")
   - What's unclear: Exact current count. If the count naturally falls below 100 due to laws being removed (not a TOC failure), the scraper would abort incorrectly
   - Recommendation: Use 100 as the threshold per REQUIREMENTS.md SCRAPER-03 verbatim. Document that this is a structural sanity check, not a "all laws present" check. If laws fall below 100, that is an operator concern, not a scraper concern.

2. **Whether to preserve the `datetime` positional arg for backwards compatibility**
   - What we know: `scrape.sh` calls `python scrape.py /data_branch $SCRAPE_DATETIME` — this is the Docker-based shell wrapper that Phase 2 replaces
   - What's unclear: Whether anyone else calls `scrape.py` with the old signature
   - Recommendation: Break the old signature cleanly. Phase 1 changes the CLI; Phase 2 provides the new call site. The Docker wrapper (`scrape.sh`) is not Phase 1 scope and will be superseded by the GitHub Actions workflow in Phase 2. No need for backwards compatibility.

3. **Whether `log.md` write should use the `--date` value or a full datetime**
   - What we know: The current code writes `- 2026-03-14T04:00:00` format (full datetime from `$SCRAPE_DATETIME`). The success criterion says `--date 2026-03-14` format.
   - What's unclear: Whether downstream consumers of `log.md` expect datetime or date format
   - Recommendation: Write `YYYY-MM-DD` date format (matching the `--date` argument). The ROADMAP.md success criterion explicitly shows `--date 2026-03-14`. Changing from datetime to date in `log.md` is an intentional simplification.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 |
| Config file | None — Wave 0 gap: create `pyproject.toml` `[tool.pytest.ini_options]` section |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCRAPER-01 | `uv sync --frozen` installs without network errors | smoke | `uv sync --frozen` (shell, not pytest) | Wave 0 — uv.lock does not exist yet |
| SCRAPER-02 | `--date 2026-03-14` arg accepted; default is UTC today | unit | `uv run pytest tests/test_scrape.py::test_date_arg -x` | Wave 0 — test_scrape.py does not exist |
| SCRAPER-03 | TOC with <100 items causes `sys.exit` with non-zero code | unit | `uv run pytest tests/test_scrape.py::test_toc_validation_fails -x` | Wave 0 — test_scrape.py does not exist |
| SCRAPER-04 | Output written to `data/items/`, `not_found.txt`, `log.md` at correct paths | integration (manual) | `uv run scrape.py --date 2026-03-14 /tmp/test-data && ls /tmp/test-data/data/items/` | manual-only — live network required |

**SCRAPER-04 integration test is manual-only** because it requires live network access to gesetze-im-internet.de and produces ~150 ZIP files totaling hundreds of MB. It cannot be made into a fast automated test without significant mocking of the entire download layer. The acceptance criterion (success criterion 1 in ROADMAP.md) covers it: "Running `uv run scrape.py --date 2026-03-14` succeeds locally."

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green + manual SCRAPER-04 smoke test before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `pyproject.toml` — does not exist; needed for `uv run` and `uv sync --frozen` to work; also hosts `[tool.pytest.ini_options]`
- [ ] `uv.lock` — does not exist; generated by `uv add` during migration task
- [ ] `tests/conftest.py` — shared fixtures (temp output directory, mock HTTP session)
- [ ] `tests/test_scrape.py` — covers SCRAPER-02 (date arg) and SCRAPER-03 (TOC validation)
- [ ] Framework install: `uv add --dev "pytest>=8.0" "pytest-mock>=3.12"` — adds pytest to dev dependencies

---

## Sources

### Primary (HIGH confidence)

- Codebase: `/scrape.py` — direct inspection of current implementation; all line references verified
- Codebase: `/scrape.sh` — confirmed git operations live here, not in scrape.py
- Codebase: `/requirements.txt` — confirmed unpinned (no version constraints on any of the 3 packages)
- `.planning/research/STACK.md` — prior stack research; Python 3.13, uv@v7, lxml>=5.0 recommendations verified
- `.planning/codebase/CONCERNS.md` — confirmed known bugs: TOC parse fragility, multiprocessing race, unpinned deps, EOL Python
- `.planning/REQUIREMENTS.md` — SCRAPER-01 through SCRAPER-04 verbatim requirements
- `.planning/ROADMAP.md` — Phase 1 success criteria (exact CLI invocation expected)
- `https://devguide.python.org/versions/` — Python 3.13 in bugfix phase, 3.7 EOL 2023-06-27 (HIGH)
- `https://docs.astral.sh/uv/guides/projects/` — uv `--no-package` init, `uv add`, `uv sync --frozen` (HIGH)

### Secondary (MEDIUM confidence)

- `.planning/research/PITFALLS.md` — lxml wheels pitfall, uv init pitfall, date timezone pitfall documented
- `.planning/research/FEATURES.md` — TOC validation feature design; >100 item threshold confirmed as project requirement

### Tertiary (LOW confidence)

- None for this phase — all claims are grounded in direct codebase inspection or official documentation.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Python 3.13 + uv + existing 3 deps verified against official sources and prior research
- Architecture: HIGH — scrape.py directly inspected; all line references are exact
- Pitfalls: HIGH — lxml wheel issue and uv init issues documented from official uv docs and prior research

**Research date:** 2026-03-14
**Valid until:** 2026-06-14 (stable ecosystem; uv and Python 3.13 release cadence is slow)
