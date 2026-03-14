# External Integrations

**Analysis Date:** 2026-03-14

## APIs & External Services

**Data Source:**
- gesetze-im-internet.de - German law database providing legislation in XML format
  - Endpoint: `https://www.gesetze-im-internet.de/gii-toc.xml` (table of contents)
  - Download protocol: Each law item links to a ZIP archive containing XML files
  - Retry strategy: HTTPAdapter with 5 retries, 10-second backoff factor, handles 500/502/504 status codes
  - Rate limiting: 0.25-second delay between downloads (in `handle_links()` at `scrape.py:38`)

## Data Storage

**Primary Storage:**
- GitHub (`git@github.com:QuantLaw/gesetze-im-internet.git`) - Data repository
  - Branch: `data` - Contains all scraped XML law files organized by item ID
  - Branch structure: `/data/items/{item_id}/` directories containing extracted XML files
  - Metadata: `/data/toc.xml` - Table of contents snapshot
  - Metadata: `/data/not_found.txt` - List of items that returned 404
  - Metadata: `/data/log.md` - Log of scrape run timestamps

**Local Storage:**
- Temporary directory: `/data/temp/` - Stores downloaded ZIP files during extraction
- Items directory: `/data/items/` - Extracted XML law files organized by item ID
- TOC cache: `/data/toc.xml` - Latest table of contents XML

**File Storage:**
- Local filesystem only - No external file storage service used

**Caching:**
- None detected

## Authentication & Identity

**Git/GitHub:**
- SSH key authentication via Docker secrets
  - Secret name: `gii_scraper_github_key`
  - Injected at: `/root/.ssh/key` (via `docker/cron.sh:3`)
  - Config: `/docker/ssh/config` - SSH client configuration
  - StrictHostKeyChecking disabled for automated deployments

**HTTP:**
- No API key or authentication required for gesetze-im-internet.de downloads
- Anonymous public access to ZIP archives

## Monitoring & Observability

**Error Tracking:**
- None detected - No external error tracking service

**Logs:**
- File-based logging:
  - Cron execution log: `/var/log/cron.log` (container)
  - Scrape execution log: `/data/log.md` (appended with run timestamps)
  - Failed items: `/data/not_found.txt` (list of 404 responses)

**Error Handling in Code:**
- BadZipFile exception handling - Detects corrupted ZIPs and checks for 404 HTML responses
- HTTP retries via requests library retry adapter

## CI/CD & Deployment

**Hosting:**
- Docker container - Runs on infrastructure with Docker/Docker Compose support
- Scheduled execution via cron (04:00 UTC daily)

**CI Pipeline:**
- None detected - Scraper runs directly via cron, no CI service integration

**Execution Flow:**
1. Cron triggers `/scrape.sh` daily at 04:00 UTC
2. Script clones `data` branch from GitHub
3. Runs `scrape.py` to download and extract laws
4. Git commits changes with timestamp and pushes to `data` branch
5. Tags commit with date and force-pushes tag to GitHub

## Environment Configuration

**Required Environment Variables:**
- None hardcoded - Configuration via arguments and Docker secrets

**Secrets Location:**
- Docker Compose secrets: `gii_scraper_github_key` (external secret managed by Docker)
- Accessed at runtime and copied to `/root/.ssh/key` by cron startup script

**GitHub Credentials:**
- SSH key-based authentication (private key in Docker secret)
- Git user configured globally in `scrape.sh`:
  - Email: `scraper@github.com`
  - Name: `Scraper`

## Webhooks & Callbacks

**Incoming:**
- None detected - Scraper is scheduled, not event-driven

**Outgoing:**
- Git push operations to GitHub:
  - Pushes commits to `data` branch after scrape completion
  - Force-pushes date-based tags (e.g., `2026-03-14`)
  - No webhook callbacks configured

## Data Flow

**Scrape Execution:**

1. **Fetch Table of Contents**
   - Endpoint: `https://www.gesetze-im-internet.de/gii-toc.xml`
   - Response saved to: `/data/toc.xml`

2. **Parse TOC**
   - BeautifulSoup extracts all `<item>` elements with nested `<link>` tags
   - Links point to ZIP files at URLs like `https://www.gesetze-im-internet.de/{item_id}/xml.zip`

3. **Download and Extract (Parallel)**
   - 2 concurrent downloads via Python multiprocessing Pool (`scrape.py:73`)
   - Each download:
     - 0.25-second delay before fetching
     - Saves ZIP to `/data/temp/{item_id}.zip`
     - Extracts to `/data/items/{item_id}/`
     - Deletes temporary ZIP
   - Detects 404 errors (HTML "404 Not Found" in ZIP content)

4. **Record Results**
   - Missing items logged to `/data/not_found.txt`
   - Temporary directory cleaned up
   - Log updated with execution timestamp

5. **Push to GitHub**
   - All changes committed with timestamp message
   - Committed data pushed to `data` branch
   - Date tag created and force-pushed

---

*Integration audit: 2026-03-14*
