# Technology Stack

**Analysis Date:** 2026-03-14

## Languages

**Primary:**
- Python 3.7 - Scraping logic and data processing

## Runtime

**Environment:**
- Python 3.7-bullseye (Debian-based)

**Package Manager:**
- pip
- Lockfile: Not present (requirements.txt used)

## Frameworks

**Core:**
- BeautifulSoup4 - HTML/XML parsing for extracting links from TOC
- lxml - XML parser backend for BeautifulSoup (faster processing)
- requests - HTTP client for downloading data from gesetze-im-internet.de

**Testing:**
- Not detected

**Build/Dev:**
- Docker - Containerization for scraper service
- Docker Compose - Multi-container orchestration and resource management

## Key Dependencies

**Critical:**
- `requests` - HTTP library with retry logic implementation for resilient downloads
- `beautifulsoup4` - XML/HTML parsing for TOC document (gii-toc.xml)
- `lxml` - XML parser backend, required for "lxml-xml" parser specification

**Infrastructure:**
- `cron` - Scheduling daily scrapes (via apt-get in Dockerfile)
- `git` - Version control and pushing data to data branch (included in base image)
- `ssh` - Secure communication with GitHub for repository operations

## Configuration

**Environment:**
- Git configuration (user.email, user.name) set in `scrape.sh` for automated commits
- GitHub SSH key injected via Docker secrets at runtime (`gii_scraper_github_key`)
- Cron job scheduled at 04:00 UTC daily (from `/docker/crontab`)

**Build:**
- `Dockerfile` - Multi-stage Python 3.7 container with cron and SSH support
- `docker-compose.yml` - Service definition with resource limits (0.5 CPU, 512MB memory)

## Platform Requirements

**Development:**
- Python 3.7+
- pip
- Git with SSH capability

**Production:**
- Docker Engine for container execution
- Docker Compose for orchestration
- SSH key for GitHub authentication (managed via Docker secrets)
- Cron daemon (built into container)

## Dependency Versions

**From requirements.txt:**
- beautifulsoup4 (pinned version: latest available)
- lxml (pinned version: latest available)
- requests (pinned version: latest available)

**No version pins in requirements.txt** - Dependencies use latest compatible versions, which may introduce non-deterministic builds. Consider pinning specific versions for reproducibility.

---

*Stack analysis: 2026-03-14*
