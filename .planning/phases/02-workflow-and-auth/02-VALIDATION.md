---
phase: 2
slug: workflow-and-auth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (via `uv run pytest`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` testpaths = ["tests"]) |
| **Quick run command** | `uv run pytest tests/ -v` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -v`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green + `workflow_dispatch` live run confirming INFRA-03
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | INFRA-01 | smoke/grep | `grep -q "0 4 \* \* \*" .github/workflows/scrape.yml` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 0 | INFRA-02 | smoke/grep | `grep -q "contents: write" .github/workflows/scrape.yml` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 0 | INFRA-04 | smoke/grep | `grep -q "cancel-in-progress: false" .github/workflows/scrape.yml` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 1 | INFRA-03 | integration/manual | `git ls-remote --tags origin \| grep "refs/tags/$(date -u +%Y-%m-%d)"` | ❌ manual-only | ⬜ pending |
| 2-01-05 | 01 | 1 | RESIL-04 | manual | trigger with broken scraper; observe failure email | manual-only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `.github/workflows/scrape.yml` — does not exist yet; must be created in Plan 01
- [ ] `tests/test_workflow_yaml.py` — YAML static verification tests for INFRA-01, INFRA-02, INFRA-04 (using Python `yaml` stdlib or grep)

*Note: INFRA-03 and RESIL-04 require a live GitHub Actions run for full verification. YAML-level checks (INFRA-01, INFRA-02, INFRA-04) can be verified with grep/static analysis in the test suite.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Workflow commits + tags `data` branch on success | INFRA-03 | Requires live GitHub Actions run; cannot mock git push to remote | Trigger `workflow_dispatch`, then run `git ls-remote --tags origin \| grep "refs/tags/$(date -u +%Y-%m-%d)"` |
| Two simultaneous triggers serialize (second queues, not cancels) | INFRA-04 | Requires concurrent real workflow runs | Fire two `workflow_dispatch` triggers in quick succession; verify in Actions UI that second run shows "queued" status |
| Workflow exits non-zero on scraper failure (enabling GitHub failure email) | RESIL-04 | Requires triggering actual failure and observing email | Temporarily break scraper, trigger workflow, verify failure email received |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
