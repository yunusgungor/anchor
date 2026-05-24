---
topic: "Bug Fix Process"
aliases: ["bug-fix", "bug-workflow", "defect-fix", "hotfix-process", "bug fix", "hata düzeltme", "bug reporting"]
tags: [workflow, bug-fix, quality, maintenance, debugging]
priority: 10
strictness: 0.95
steps:
  - id: reproduce
    title: "Bug'ı Reprodüse Et (Kesin Adımlarla)"
    mandatory: true
    checks: ["reproduce", "replicable", "steps", "environment", "reproduction"]
  - id: root-cause
    title: "Kök Neden Analizi (5 Whys)"
    mandatory: true
    depends_on: [reproduce]
    checks: ["root cause", "5 whys", "why", "trace", "kök neden"]
  - id: failing-test
    title: "Bug'ı Gösteren Test Yaz"
    mandatory: true
    depends_on: [root-cause]
    checks: ["fail", "test", "reproduce", "assert", "regression test"]
  - id: fix-code
    title: "Kodu Düzelt (Minimal Değişiklik)"
    mandatory: true
    depends_on: [failing-test]
    checks: ["fix", "minimal", "change", "pass", "patch"]
  - id: regression
    title: "Regresyon Testlerini Çalıştır"
    mandatory: true
    depends_on: [fix-code]
    checks: ["regression", "all tests", "CI", "pipeline", "test suite"]
  - id: prevent-recurrence
    title: "Tekrarını Önle (Post-mortem)"
    mandatory: false
    depends_on: [regression]
    checks: ["postmortem", "prevent", "monitoring", "alert", "önlem"]
---

# Bug Fix Process

## Purpose
Standardized process for identifying, fixing, and preventing software bugs.

## Bug Severity Classification

| Severity | Definition | Response Time | Fix Target |
|----------|-----------|---------------|------------|
| P0 (Critical) | Production outage, data loss, security breach | Immediate | < 4 hours |
| P1 (High) | Major feature broken, no workaround | < 1 hour | < 24 hours |
| P2 (Medium) | Feature partially broken, workaround exists | < 4 hours | < 1 week |
| P3 (Low) | Cosmetic, edge case, minor inconvenience | < 1 week | Next release |

## Process

### 1. Reproduce
- Get exact reproduction steps from reporter
- Try on different environments (dev/staging/prod)
- Capture logs, screenshots, and error messages
- Document the exact steps

### 2. Root Cause Analysis
- Apply 5 Whys technique
- Trace through the code path
- Check recent changes (git bisect if needed)
- Identify if it's a logic error or environmental issue

### 3. Write Regression Test
- Write a test that captures the bug scenario
- Verify the test fails (confirming the bug)
- The test becomes part of the test suite permanently

### 4. Fix
- Apply minimal change to fix the root cause
- Don't fix unrelated issues in the same change
- Write clear commit message: `fix: description of fix (#ticket)`

### 5. Regression Testing
- Run full test suite
- Run related integration and e2e tests
- Deploy to staging and verify

### 6. Prevent Recurrence
- Add monitoring/alerting if applicable
- Update documentation if behavior changed
- Consider if other code paths have the same issue
- Post-mortem for P0/P1 bugs
