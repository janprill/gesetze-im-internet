# Coding Conventions

**Analysis Date:** 2026-03-14

## Naming Patterns

**Files:**
- Snake case for all Python and shell scripts: `scrape.py`, `scrape.sh`, `cron.sh`
- Docker configuration files: `Dockerfile`, `docker-compose.yml`
- Documentation: uppercase markdown files: `README.md`

**Functions:**
- Snake case for Python functions: `requests_retry_session()`, `ensure_exists()`, `handle_links()`, `scrape()`
- Function names are descriptive and action-oriented (verb-first pattern)

**Variables:**
- Snake case for local and global variables: `item_id`, `zip_path`, `TEMP_PATH`, `ITEMS_PATH`
- UPPERCASE for module-level path constants: `BASE_PATH`, `LOG_PATH`, `TOC_PATH`, `NOT_FOUND_PATH`, `ITEMS_PATH`, `TEMP_PATH`
- Function parameters use snake case and simple names: `retries`, `backoff_factor`, `status_forcelist`, `session`

**Types:**
- No explicit type hints used in codebase (Python 3.7 compatible, pre-type annotation era)
- Implicit types inferred from usage

## Code Style

**Formatting:**
- No linter configuration present (no `.pylintrc`, `.flake8`, or `pyproject.toml`)
- PEP 8 style followed informally: 4-space indentation
- Line length approximately 80-100 characters (no hard limit detected)
- Blank lines between functions and logical sections

**Linting:**
- No automated linting configured
- No formatter configuration (no `.prettierrc` or similar)

## Import Organization

**Order:**
1. Standard library imports (first): `argparse`, `os`, `shutil`, `multiprocessing.pool`, `zipfile`, `time`
2. Third-party imports (second): `requests`, `BeautifulSoup`, HTTP adapters
3. No local imports (single-file module)

**Example from `scrape.py`:**
```python
import argparse
import os
import shutil
from multiprocessing.pool import Pool
from zipfile import ZipFile, BadZipFile
import time

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
```

**Path Aliases:**
- No path aliases used (simple flat structure)

## Error Handling

**Patterns:**
- Assertion-based validation: `assert link_parts[-1] == "xml.zip"` in `handle_links()` line 43
- Exception handling with specific exception types: `except BadZipFile` in `handle_links()` line 53
- Error detection via content inspection: checking for `<title>404 Not Found</title>` in response content (lines 56-57)
- Re-raising exceptions when content doesn't match expected error pattern: `raise` on line 59
- Graceful cleanup with `ignore_errors=True`: `shutil.rmtree(ITEMS_PATH, ignore_errors=True)` (line 104)
- No custom exceptions defined; uses built-in exception types

**Error Propagation:**
- `handle_links()` returns `error` (None or item_id) rather than raising exceptions
- Errors are collected and written to file (`not_found.txt`) rather than failing execution
- Network failures trigger retries via `requests_retry_session()` with exponential backoff

## Logging

**Framework:** Standard `print()` statements

**Patterns:**
- Minimal logging: only final status printed to stdout
- Print statement for completion: `print("DONE", args.datetime)` (line 114)
- Commented-out debug line present: `# print("Loading", link)` (line 40)
- No structured logging framework used
- Shell script logging via file redirection to cron log: `>> /var/log/cron.log 2>&1`

## Comments

**When to Comment:**
- Very sparse comment usage (only 1 active comment in 114 lines of Python)
- Comments appear for disabled code: `# print("Loading", link)` suggests previously used debugging
- No function-level comments or docstrings

**JSDoc/TSDoc:**
- Not applicable (Python codebase without docstrings)

## Function Design

**Size:**
- Functions are concise (3-50 lines)
- `requests_retry_session()`: 15 lines - single responsibility (session configuration)
- `ensure_exists()`: 3 lines - utility function
- `handle_links()`: 25 lines - download and extract single item
- `scrape()`: 21 lines - orchestrate entire scrape operation

**Parameters:**
- Functions accept necessary parameters explicitly: `requests_retry_session(retries=5, backoff_factor=10, status_forcelist=(500, 502, 504), session=None)`
- Default values provided: `retries=5`, `backoff_factor=10`, `session=None`
- Paths passed as parameters to functions rather than global imports

**Return Values:**
- Most functions return results or None: `handle_links()` returns error identifier or None
- Main orchestration function (`scrape()`) returns nothing (side effects only)
- `ensure_exists()` returns path for chaining or logging

## Module Design

**Exports:**
- No explicit module exports (single-file script)
- Functions exposed as top-level callables

**Barrel Files:**
- Not applicable (single-file Python script)

## Script Entry Point

**Pattern:**
- Standard `if __name__ == "__main__":` guard (line 87) ensures code runs only when executed directly
- Command-line arguments parsed with `argparse.ArgumentParser()` (line 88)
- Argument validation implicit (paths don't exist check is performed, not raised)
- Configuration via positional arguments: `data_repo_path`, `datetime` (lines 89-90)

## Shell Script Conventions

**`scrape.sh` patterns:**
- Error handling with `set -e` (exit on first error)
- Clear variable naming: `SCRAPE_DATETIME`, `SCRAPE_DATE`
- Date formatting: `date +'%Y-%m-%dT%T'` and `date +'%Y-%m-%d'`
- Git configuration with global scope: `git config --global`
- Explicit path navigation with `cd` commands
- Proper Python script invocation with absolute path interpretation

**`docker/cron.sh` patterns:**
- SSH key setup from Docker secrets: `cp /run/secrets/gii_scraper_github_key /root/.ssh/key`
- Environment variable injection: `printenv | cat - /etc/cron.d/cron-jobs`
- File permissions explicitly set: `chmod 600`, `chmod 644`
- Foreground cron daemon: `cron -f` with background log tail

---

*Convention analysis: 2026-03-14*
