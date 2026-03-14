# Codebase Structure

**Analysis Date:** 2026-03-14

## Directory Layout

```
gesetze-im-internet/                     # Repository root (master branch)
├── scrape.py                            # Core scraping logic
├── scrape.sh                            # Shell orchestration wrapper
├── Dockerfile                           # Container image definition
├── docker-compose.yml                   # Docker Compose deployment config
├── docker/                              # Docker runtime assets
│   ├── cron.sh                          # Cron initialization script
│   ├── crontab                          # Cron schedule configuration
│   └── ssh/                             # SSH key directory (mounted at runtime)
├── requirements.txt                     # Python dependencies
├── requirements_dev.txt                 # Development dependencies
└── README.md                            # Project documentation

data/                                    # (Separate branch, not included)
└── [scraped XML files and logs]
```

## Directory Purposes

**Root Directory:**
- Purpose: Scraping code and deployment configuration
- Contains: Python scraper, shell scripts, Docker config, dependency manifests
- Key files: `scrape.py`, `scrape.sh`, `Dockerfile`

**docker/ Directory:**
- Purpose: Runtime assets for containerized execution
- Contains: Cron scheduler, SSH key mounting, credential management
- Key files: `cron.sh` (SSH setup), `crontab` (schedule definition)

**docker/ssh/ Directory:**
- Purpose: SSH private key storage (mounted into container at runtime)
- Contains: GitHub SSH key for authentication to data repository
- Generated: No (provided via Docker secrets at deployment time)
- Committed: No (git-ignored, injected via Docker)

## Key File Locations

**Entry Points:**

- `scrape.py`: Main Python entry point. Called with arguments: `{data_repo_path} {datetime}`. Initiates entire scraping pipeline.
- `scrape.sh`: Shell orchestration wrapper. Executed by cron daemon. Clones data branch, invokes scraper, commits and pushes results.
- `docker/cron.sh`: Container startup script. Initializes SSH credentials and launches cron daemon.

**Configuration:**

- `Dockerfile`: Container image build definition. Installs Python, dependencies, copies scraper code, configures cron entry.
- `docker-compose.yml`: Docker Compose service definition. Specifies CPU/memory limits (0.5 CPU, 512MB RAM), restart policy, Docker secret mount.
- `docker/crontab`: Cron schedule. Runs `scrape.sh` at 04:00 UTC daily.
- `requirements.txt`: Python runtime dependencies (beautifulsoup4, lxml, requests).
- `requirements_dev.txt`: Development dependencies (same as requirements.txt currently).

**Core Logic:**

- `scrape.py`: Complete scraping implementation:
  - `requests_retry_session()` (lines 14-28): HTTP client factory with exponential backoff
  - `ensure_exists()` (lines 31-34): Directory creation utility
  - `handle_links()` (lines 37-61): Single-item download worker function
  - `scrape()` (lines 64-84): Orchestration: fetch TOC, parse, parallel download, error tracking
  - `main` (lines 87-114): Entry point: argument parsing, directory setup, execution, logging

**Documentation:**

- `README.md`: Project overview in German. Describes archival process, data availability, background.

## Naming Conventions

**Files:**

- Python: `scrape.py` (lowercase, underscore-separated)
- Shell: `scrape.sh`, `cron.sh` (lowercase, .sh extension)
- Configuration: `Dockerfile`, `docker-compose.yml` (CamelCase for Docker files, kebab-case for compose)
- Dependencies: `requirements.txt`, `requirements_dev.txt` (Python standard)

**Directories:**

- Docker assets: `docker/` (lowercase)
- Nested subdirectories: `docker/ssh/` (lowercase, functional naming)
- Output directories (created at runtime): `data/items/`, `data/temp/` (lowercase, semantic)

**Functions (in scrape.py):**

- Utilities: `ensure_exists()`, `requests_retry_session()` (snake_case, descriptive)
- Main logic: `scrape()`, `handle_links()` (snake_case, verb-based)

**Variables:**

- Paths: `TEMP_PATH`, `ITEMS_PATH`, `TOC_PATH`, `NOT_FOUND_PATH`, `LOG_PATH`, `BASE_PATH` (SCREAMING_SNAKE_CASE for constants)
- Function parameters: `retries`, `backoff_factor`, `status_forcelist` (lowercase snake_case)
- Loop variables: `link`, `item_id`, `e` (descriptive or conventional single-letters)

**Command-line Arguments:**

- Positional args: `data_repo_path` (snake_case)
- Datetime: `datetime` (matches `SCRAPE_DATETIME` pattern in shell)

## Where to Add New Code

**New Scraping Feature:**
- Primary code: Add functions to `scrape.py` alongside existing `scrape()` and `handle_links()`
- Tests: Create `test_scrape.py` in repository root (no existing test structure; use pytest)
- Configuration: Add new parameters to argparse in `scrape.py` main block (lines 88-91)

**New Deployment/Scheduling Logic:**
- Shell scripts: Add functions to `scrape.sh` or create new shell files in root
- Docker changes: Modify `Dockerfile` if new dependencies or setup required
- Cron changes: Edit `docker/crontab` to adjust schedule or add new jobs

**Utilities and Helpers:**
- Shared HTTP utilities: Add to `scrape.py` near `requests_retry_session()` (lines 14-28)
- Path management: Add to main block or create `config.py` (not yet present)
- Error handling: Extend exception handling in `handle_links()` (lines 37-61)

**External Service Integration:**
- Database/API clients: Add to `scrape.py` with own configuration section
- Authentication: Store credentials in Docker secrets, reference in `docker/cron.sh`
- Secrets: Mount via Docker Compose `secrets` section and reference in `cron.sh`

## Special Directories

**docker/ssh/ Directory:**
- Purpose: SSH key storage for GitHub authentication
- Generated: No (externally provided)
- Committed: No (git-ignored during build; injected at runtime via Docker secrets)
- Runtime behavior: Mounted into container filesystem, permissions set to 600 by `cron.sh`

**Working Data Directories (created at runtime):**
- `data/temp/`: Temporary ZIP file storage during download. Deleted after extraction.
- `data/items/`: Extracted law files organized by item ID. Persisted to git.
- Location computed dynamically from `{data_repo_path}/data/` argument

---

*Structure analysis: 2026-03-14*
