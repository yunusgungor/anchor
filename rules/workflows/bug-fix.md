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
    aliases: ["reproduced the bug", "reproduced issue", "confirmed the bug"]
    checks: ["reproduce", "steps"]
  - id: root-cause
    title: "Kök Neden Analizi (5 Whys)"
    mandatory: true
    depends_on: [reproduce]
    aliases: ["analyzed the root cause", "found the root cause", "identified the root cause"]
    checks: ["root cause", "trace"]
  - id: failing-test
    title: "Bug'ı Gösteren Test Yaz"
    mandatory: true
    depends_on: [root-cause]
    aliases: ["wrote a failing test", "added a regression test"]
    checks: ["fail", "test"]
  - id: fix-code
    title: "Kodu Düzelt (Minimal Değişiklik)"
    mandatory: true
    depends_on: [failing-test]
    aliases: ["implemented the fix", "applied the fix", "patched the bug"]
    checks: ["fix", "patch"]
  - id: regression
    title: "Regresyon Testlerini Çalıştır"
    mandatory: true
    depends_on: [fix-code]
    aliases: ["verified the test passes", "ran the test suite", "confirmed tests pass"]
    checks: ["regression", "test suite", "all tests"]
  - id: prevent-recurrence
    title: "Tekrarını Önle (Post-mortem)"
    mandatory: false
    depends_on: [regression]
    aliases: ["documented the change", "added preventive follow-up"]
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
