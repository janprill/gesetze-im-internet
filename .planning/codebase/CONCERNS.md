# Codebase Concerns

**Analysis Date:** 2026-03-14

## Tech Debt

**Python 3.7 end-of-life:**
- Issue: Python 3.7 reached end-of-life on 2023-06-27. No security patches available.
- Files: `Dockerfile` (line 1), `requirements.txt`, `requirements_dev.txt`
- Impact: Security vulnerabilities in Python runtime, no upstream security fixes. Dependency updates may become impossible if packages drop 3.7 support.
- Fix approach: Upgrade to Python 3.11+ (current stable LTS), test scraper against new version, rebuild and redeploy Docker image.

**Unpinned dependency versions:**
- Issue: `requirements.txt` lists packages without version constraints: `beautifulsoup4`, `lxml`, `requests` (no `==X.Y.Z` pins)
- Files: `requirements.txt` (all lines), `requirements_dev.txt` (all lines)
- Impact: Non-deterministic builds across environments. Future `docker build` calls may pull different versions, causing unexpected behavior changes or new bugs. Already observed in historical PRs (dependabot branches exist but unmerged).
- Fix approach: Pin all dependencies to specific versions (e.g., `requests==2.31.0`). Document decision on security vs stability tradeoffs. Implement automated dependency scanning (dependabot or renovate) with scheduled updates.

**Old dependency versions in stale branches:**
- Issue: Dependabot branches exist (`dependabot/pip/certifi-2022.12.7`, `dependabot/pip/lxml-4.9.1`, `dependabot/pip/urllib3-1.26.5`) but were never merged to master
- Files: Git history - branches remain in remote but not integrated
- Impact: Known security updates are available but not deployed. Suggests broken update process or decision to stay on old versions without documentation.
- Fix approach: Review dependabot PRs, merge or explicitly reject with reasoning. Set clear policy on dependency update cadence.

**GitHub Actions → Docker migration without CI/CD:**
- Issue: Commit `e6abd4ad2` moved from GitHub Actions to Docker (no date, but predates current setup). No GitHub Actions workflows remain in `.github/workflows/`.
- Files: No GitHub Actions present; cron execution only via Docker
- Impact: No automated testing, no pre-deployment checks, no visibility into scraper health. Scraper can fail silently for hours until next scheduled run (04:00 UTC).
- Fix approach: Restore GitHub Actions for scheduled runs (cron trigger), add job that validates scraper output, detects failures quickly, sends alerts.

## Known Bugs

**Zip file 404 detection via HTML parsing:**
- Issue: When a law file is removed from gesetze-im-internet.de, the server returns HTTP 200 with a 404 HTML page instead of HTTP 404 status. Code must parse HTML to detect this.
- Files: `scrape.py` lines 53-59
- Symptoms: Removed laws are silently skipped. They appear in `not_found.txt` but this is a workaround, not a real error code.
- Trigger: When gesetze-im-internet.de removes or reorganizes a law (e.g., repealed law).
- Workaround: The code handles it by checking for `<title>404 Not Found</title>` in response body, but this is fragile (depends on exact HTML format).

**Race condition in multiprocessing pool:**
- Issue: `scrape.py` uses `Pool(2)` for concurrent downloads with shared file paths (`TEMP_PATH`, `ITEMS_PATH`). Multiple workers write/delete simultaneously.
- Files: `scrape.py` lines 73-84, concurrent `handle_links()` calls
- Impact: If two workers try to extract to the same path or delete `TEMP_PATH` before all workers complete, file system errors can occur (rare but possible under load).
- Trigger: Unpredictable; depends on timing and file system state.
- Workaround: None currently. Assumes 2 concurrent workers won't conflict (may fail with higher pool sizes).

**Incomplete error handling on git push failures:**
- Issue: `scrape.sh` pushes to data branch without checking push exit code. If `git push` fails (network, auth, conflict), the script continues silently.
- Files: `scrape.sh` lines 27-28 (uses `set -e` but git push may not be fatal)
- Symptoms: A failed push means data isn't persisted, but log shows "DONE" and cron reports success.
- Trigger: Network outage, auth failure, GitHub API rate limit, force push rejected.
- Workaround: Check git status on next run; `not_found.txt` is rewritten each time so lost data isn't detected.

## Security Considerations

**SSH key mounted in Docker without strict permissions:**
- Risk: Private SSH key injected via Docker secret at `/root/.ssh/key` (line 3 in `docker/cron.sh`). Key permissions set to 600 but runs as root in container (no user isolation).
- Files: `docker/cron.sh` (lines 3-6), `docker-compose.yml` (secrets config)
- Current mitigation: Docker secrets encrypted at rest in Swarm, SSH key only available to scraper container, SSH agent used to avoid exposing key in environment.
- Recommendations: Run container as non-root user (create scraper user in Dockerfile). Add key rotation strategy. Monitor git push operations for unauthorized commits. Consider using GitHub App authentication with short-lived tokens instead of long-lived SSH keys.

**Cron job runs with no output monitoring:**
- Risk: Cron job output redirected to `/var/log/cron.log` with no log aggregation or alerting. If scraper crashes, only operator manually checking logs discovers it.
- Files: `docker/crontab` (line 1), `docker/cron.sh` (line 14)
- Current mitigation: Log file exists and is tailed in foreground process.
- Recommendations: Implement centralized logging (syslog, CloudWatch, Datadog). Send alerts on scraper failure (non-zero exit code). Expose container metrics to monitoring system.

**Git config hardcoded with bot identity:**
- Risk: Scraper makes commits as "Scraper" user with no audit trail to distinguish from human commits or detect compromise.
- Files: `scrape.sh` lines 17-18
- Current mitigation: Commits pushed to `data` branch, not `master`.
- Recommendations: Use GitHub App for authentication with audit log. Sign commits with GPG key. Log all push operations.

**Force push on tag without safety checks:**
- Risk: `scrape.sh` line 28 uses `git push -f` on daily tags. If two scraper instances run simultaneously, force push could lose data.
- Files: `scrape.sh` line 28
- Current mitigation: Only one instance runs (single Docker container). Cron ensures once-daily execution.
- Recommendations: Add lock file or distributed lock check before push. Use atomic tag operations or verify tag hasn't changed before force push.

## Performance Bottlenecks

**Multiprocessing pool size hardcoded to 2:**
- Problem: Scraper downloads ~150-200 law files sequentially in pairs. Each download takes ~0.5-1s (includes 0.25s sleep). Total runtime ~2-3 minutes.
- Files: `scrape.py` line 73
- Cause: Pool size fixed at 2, no tuning based on available CPU/memory. Docker memory limit is 512MB (sufficient for 2 workers).
- Improvement path: Profile scraper to find optimal pool size (may be 4-8 with 512MB limit). Remove hardcoded value, make configurable. Measure actual download + parse time vs sleep. Consider removing sleep if not needed for rate limiting.

**Redundant XML parsing:**
- Problem: TOC downloaded twice - once saved to file, once parsed with BeautifulSoup to extract links.
- Files: `scrape.py` lines 65-71
- Cause: Separation of concerns between download/save and parsing.
- Improvement path: Parse in-memory after first download, then save. Avoid round-trip to disk.

**Sleep delay on every download:**
- Problem: `time.sleep(0.25)` in `handle_links()` adds 0.25s delay before every law file download (~40+ seconds total for 150 files).
- Files: `scrape.py` line 38
- Cause: Rate limiting for server politeness, but no evidence of rate limit being hit. May be overly conservative.
- Improvement path: Monitor actual request rate. Consider adaptive backoff (only sleep if rate limit headers present). Remove if server accepts faster rates.

## Fragile Areas

**XML parser assumptions:**
- Files: `scrape.py` lines 69-71
- Why fragile: Assumes `item.link.get_text()` always exists. If gesetze-im-internet.de changes TOC structure (adds attributes, changes nesting), parser silently fails to extract links or crashes. No validation of parsed structure.
- Safe modification: Add explicit error handling with try-catch on parsing. Validate structure before use (assert/raise). Log skipped items.
- Test coverage: No tests - bugs only found after deployment.

**Hardcoded file path assumptions:**
- Files: `scrape.py` lines 42-44 (assumes `-2` and `-1` indices in link path)
- Why fragile: Parsing link assumes format `*/item_id/xml.zip`. If link format changes, assertion fails and entire scrape halts.
- Safe modification: Use URL parsing library (urllib.parse) instead of string split. Validate extracted item_id format.
- Test coverage: No unit tests.

**Zip extraction without integrity validation:**
- Files: `scrape.py` lines 50-59
- Why fragile: Catches `BadZipFile` but only checks for 404 HTML. If zip is corrupted but valid ZIP structure, content is corrupted but extraction succeeds silently.
- Safe modification: Validate zip integrity (test extraction on CRC). Compare file sizes before/after extraction. Log warnings.
- Test coverage: No tests.

**Temporary file cleanup assumes success:**
- Files: `scrape.py` lines 84, 105-106
- Why fragile: Removes temp directory at end of scrape. If scraper crashes mid-run, temp files accumulate. Next run may fail if disk is full.
- Safe modification: Use context managers (tempfile.TemporaryDirectory). Clean up on entry, not exit. Use try-finally blocks.
- Test coverage: No integration tests.

## Scaling Limits

**Single-instance, daily-run constraint:**
- Current capacity: One scrape run per day at 04:00 UTC, takes ~3-5 minutes
- Limit: Cannot run on-demand or more frequently. Cannot handle incremental updates.
- Scaling path: Implement incremental scraping (check for modified files since last run). Add API endpoint to trigger scrape on-demand. Run as service (not cron) with queue.

**Fixed memory limit in Docker Compose:**
- Current capacity: 512MB per scraper container
- Limit: If law files grow larger or pool size increases, OOM killer may terminate scraper mid-run.
- Scaling path: Monitor memory usage during scrapes. Increase limit if needed. Consider streaming/chunked download for large files.

**No data persistence across failures:**
- Current capacity: Partial downloads lost if scraper crashes
- Limit: No checkpoint/resume support. Must restart from scratch.
- Scaling path: Implement checkpoint system (track downloaded files). Use persistent work queue (Redis, database) to resume failed downloads.

## Dependencies at Risk

**BeautifulSoup4 with lxml-xml parser:**
- Risk: Code relies on `BeautifulSoup(..., "lxml-xml")` which requires lxml. If lxml drops support or breaks XML parsing, scraper fails silently.
- Files: `scrape.py` line 69, `requirements.txt` line 2
- Impact: XML parsing completely broken; no fallback parser.
- Migration plan: Keep lxml pinned. Add fallback to `xml.etree.ElementTree` (stdlib). Test both parsers. Document parser choice.

**Requests library with custom retry logic:**
- Risk: Code reimplements retry logic with `requests.packages.urllib3.util.retry`. This is internal API that may change. Urllib3 updates may break compatibility.
- Files: `scrape.py` lines 10-11, 14-28
- Impact: Downloads fail silently or lose retry behavior if urllib3 changes.
- Migration plan: Use `requests.adapters.Retry` (public API, already done). Verify compatibility after urllib3 updates. Consider using `httpx` for more modern async support.

**Python 3.7 EOL - already addressed above**

## Missing Critical Features

**No health checks or monitoring:**
- Problem: Scraper runs in background with no alerting on failure. Operator may not notice for days that scraping stopped.
- Blocks: Cannot detect outages proactively. Cannot distinguish between "no updates available" and "scraper crashed".
- Recommendations: Add HTTP health check endpoint. Expose metrics (last_scrape_time, items_downloaded, errors). Set up alerting on failed runs. Log scraper exit code visibly.

**No incremental updates:**
- Problem: Every scrape downloads all ~150 laws even if only 1 changed. Wastes bandwidth and time.
- Blocks: Cannot support high-frequency scraping. Cannot optimize for small changes.
- Recommendations: Implement incremental update (check ETag or Last-Modified headers). Track file hashes. Only download changed files.

**No test suite:**
- Problem: No unit tests, integration tests, or end-to-end tests. Changes risk breaking scraper.
- Blocks: Cannot refactor safely. Cannot onboard new maintainers. Bug fixes are manual and error-prone.
- Recommendations: Add tests for XML parsing (mock TOC structure). Add tests for zip extraction (use fixture zips). Add integration test against staging server. Use CI/CD to run tests automatically.

**No configuration file:**
- Problem: All paths, sleep duration, pool size, retry counts are hardcoded in `scrape.py`.
- Blocks: Cannot adjust behavior without code changes. Difficult to deploy to different environments.
- Recommendations: Create config file (YAML/JSON) or environment variables for tunable parameters. Load at startup.

**No rollback mechanism:**
- Problem: If a scrape corrupts data or pushes bad commits, no way to revert without manual git operations.
- Blocks: Cannot recover from operator error or software bug quickly.
- Recommendations: Store last-known-good snapshot. Implement scrape validation (verify all files present, checksums match expected). Add rollback command.

## Test Coverage Gaps

**XML parsing untested:**
- What's not tested: BeautifulSoup parsing of `gii-toc.xml`. What happens if TOC structure changes, links are malformed, or parsing fails.
- Files: `scrape.py` lines 69-71
- Risk: Parser may silently skip items or crash unexpectedly in production.
- Priority: High

**HTTP client and retry logic untested:**
- What's not tested: Retry behavior on 5xx errors, backoff timing, connection failures, timeout handling.
- Files: `scrape.py` lines 14-28, 46
- Risk: Downloads may fail silently or hang if retry logic breaks.
- Priority: High

**Zip extraction and error handling untested:**
- What's not tested: BadZipFile exception handling, 404 detection, extraction errors, corrupted archives.
- Files: `scrape.py` lines 50-61
- Risk: Corrupted or missing files go unnoticed.
- Priority: High

**End-to-end integration untested:**
- What's not tested: Full scrape workflow against live or mock server, git commit/push, file I/O.
- Files: All of `scrape.py` and `scrape.sh`
- Risk: Only discovered at runtime; failures block data collection.
- Priority: Medium

**Multiprocessing edge cases untested:**
- What's not tested: Race conditions with `Pool(2)`, concurrent file writes, cleanup behavior on partial failure.
- Files: `scrape.py` lines 73-84
- Risk: Rare but critical bugs that manifest under specific conditions.
- Priority: Medium

---

*Concerns audit: 2026-03-14*
