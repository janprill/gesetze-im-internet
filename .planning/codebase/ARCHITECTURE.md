# Architecture

**Analysis Date:** 2026-03-14

## Pattern Overview

**Overall:** Batch scraping pipeline with scheduled container-based execution

**Key Characteristics:**
- Pull-based scraping from upstream XML feed
- Containerized deployment with cron scheduling
- Multi-process parallel downloads
- Git-based data persistence and versioning
- Resilient HTTP with automatic retries and backoff

## Layers

**Network/HTTP Layer:**
- Purpose: Handle all communication with gesetze-im-internet.de
- Location: `scrape.py` (functions `requests_retry_session`, `handle_links`)
- Contains: Retry logic, HTTP session management, network error handling
- Depends on: `requests`, `urllib3`
- Used by: Download orchestration layer

**Data Discovery Layer:**
- Purpose: Parse XML table of contents to identify all laws and documents
- Location: `scrape.py` (function `scrape`, lines 65-71)
- Contains: XML parsing with BeautifulSoup, link extraction
- Depends on: HTTP layer, BeautifulSoup, lxml XML parser
- Used by: Download orchestration layer

**Download Orchestration Layer:**
- Purpose: Coordinate parallel downloads of all discovered items
- Location: `scrape.py` (function `scrape`, lines 73-77)
- Contains: Multiprocess pool management, task distribution
- Depends on: Network layer, extraction layer
- Used by: Main entry point

**Extraction & Storage Layer:**
- Purpose: Unzip downloaded content and persist to filesystem
- Location: `scrape.py` (function `handle_links`, lines 50-60)
- Contains: ZIP extraction, error handling for corrupted/missing archives
- Depends on: Network layer
- Used by: Download orchestration layer

**Logging & Reporting Layer:**
- Purpose: Track execution history and report failures
- Location: `scrape.py` (main block, lines 100-114)
- Contains: Not-found tracking, execution logging
- Used by: Entry point and deployment wrapper

**Scheduler/Deployment Layer:**
- Purpose: Automate scraping on fixed schedule
- Location: `scrape.sh`, `docker/cron.sh`, `docker/crontab`
- Contains: SSH key management, git operations, cron scheduling
- Depends on: Scraping layer, git, ssh
- Used by: Container runtime

## Data Flow

**Daily Scraping Cycle:**

1. Cron triggers at 04:00 UTC daily (Docker cron daemon)
2. `cron.sh` initializes SSH credentials from Docker secrets
3. `scrape.sh` clones data branch from GitHub to `/data_branch`
4. `scrape.sh` invokes Python scraper with timestamp: `python scrape.py /data_branch DATETIME`
5. Scraper creates working directories: `data/temp/`, `data/items/`, logs path
6. Scraper fetches TOC from `https://www.gesetze-im-internet.de/gii-toc.xml`
7. BeautifulSoup parses XML to extract download links (item elements)
8. Multiprocess pool (2 workers) downloads ZIP files in parallel:
   - Each worker: sleeps 0.25s, fetches ZIP, extracts to `data/items/{item_id}/`
   - Tracks 404 errors (missing items) in error list
9. Scraper writes `data/not_found.txt` with list of unavailable items
10. Scraper cleans up `data/temp/` directory
11. `scrape.sh` commits changes to data branch with timestamp
12. `scrape.sh` tags commit with date and pushes to GitHub

**State Management:**

- Filesystem-based: All downloaded XMLs stored in `data/items/` directory tree
- Git-based versioning: Each scrape creates dated commit on `data` branch
- No in-memory state persistence between runs
- Log appended to `data/log.md` with execution timestamp

## Key Abstractions

**Resilient Session:**
- Purpose: Manage HTTP connection retries with exponential backoff
- Examples: `requests_retry_session()` in `scrape.py` lines 14-28
- Pattern: Factory function returning configured requests.Session
- Config: 5 retries, 10s backoff factor, targets 5xx errors

**Item Download Task:**
- Purpose: Encapsulate download, extraction, error handling for single law
- Examples: `handle_links()` in `scrape.py` lines 37-61
- Pattern: Single-responsibility function safe for multiprocessing
- Handles: ZIP download, extraction, 404 detection, cleanup
- Returns: Item ID if 404 error, None if successful

**Path Configuration:**
- Purpose: Centralize directory layout and avoid hardcoding
- Examples: Main block lines 93-98
- Pattern: Computed from single data_repo_path argument
- Paths: BASE_PATH, TEMP_PATH, ITEMS_PATH, TOC_PATH, NOT_FOUND_PATH, LOG_PATH

## Entry Points

**Python Scraper:**
- Location: `scrape.py` main block (lines 87-114)
- Triggers: Called by `scrape.sh` with arguments: `{data_repo_path} {datetime}`
- Responsibilities:
  - Parse command-line arguments
  - Initialize working directories
  - Invoke scraping pipeline
  - Log execution timestamp

**Shell Orchestrator:**
- Location: `scrape.sh` lines 1-28
- Triggers: Executed by Docker cron daemon daily at 04:00 UTC
- Responsibilities:
  - Clone data branch from GitHub
  - Manage SSH authentication via Docker secrets
  - Call Python scraper
  - Push changes back to GitHub with tags

**Container Entry:**
- Location: `Dockerfile` line 22 entrypoint
- Triggers: Docker container startup
- Responsibilities: Initialize cron daemon and SSH, execute cron.sh

## Error Handling

**Strategy:** Graceful degradation with detailed logging

**Patterns:**
- HTTP retries: Exponential backoff (max 5 retries, 10s factor) for 5xx errors
- ZIP extraction: Catch BadZipFile exception, detect 404 responses (HTML "404 Not Found" in binary)
- Missing items: Log item ID to `data/not_found.txt`, continue processing
- Directory cleanup: Use `ignore_errors=True` for robust rmtree operations
- Failed pushes: Script will fail fast if git operations fail (set -e in shell)

## Cross-Cutting Concerns

**Logging:** Append-only log in `data/log.md` with ISO datetime. No structured logging framework.

**Validation:** Light validation: assertion on ZIP link format (must end with "xml.zip"), detection of HTML 404 responses.

**Error Reporting:** Missing items tracked in `data/not_found.txt`. Failed runs fail container with non-zero exit.

**Network Resilience:** HTTP layer has built-in retries; 0.25s rate limiting per item (line 38 `time.sleep`).

**Authentication:** SSH key injected by Docker secrets at runtime, mounted to `/root/.ssh/key`.

---

*Architecture analysis: 2026-03-14*
