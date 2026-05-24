---
topic: "Code Review Process"
aliases: ["code-review", "peer-review", "pr-review", "review-process", "code review", "pull request review", "PR review"]
tags: [workflow, quality, review, development]
priority: 10
strictness: 0.95
steps:
  - id: review-pr
    title: "PR'yi İncele (Diff + Context)"
    mandatory: true
    checks: ["diff", "context", "description", "ticket", "pull request"]
  - id: logic-check
    title: "İş Mantığı ve Doğruluk Kontrolü"
    mandatory: true
    depends_on: [review-pr]
    checks: ["edge case", "business logic", "correctness", "boundary", "logic"]
  - id: quality-check
    title: "Kod Kalitesi ve Standartlar"
    mandatory: true
    depends_on: [logic-check]
    checks: ["style", "naming", "complexity", "duplication", "SOLID", "clean code"]
  - id: security-check
    title: "Güvenlik Taraması"
    mandatory: true
    depends_on: [quality-check]
    checks: ["injection", "XSS", "auth", "secret", "dependency", "security"]
  - id: test-check
    title: "Test Kapsamı Doğrulama"
    mandatory: true
    depends_on: [security-check]
    checks: ["coverage", "test", "assert", "mock", "test case"]
  - id: approve-or-request
    title: "Onayla veya Değişiklik İste"
    mandatory: true
    depends_on: [test-check]
    checks: ["approve", "changes", "comment", "resolve", "LGTM"]
---

# Code Review Process

## Purpose
Standardized peer review process to ensure code quality, consistency, and knowledge sharing.

## Reviewer Checklist

### 1. Design Review
- Does the change belong in the codebase?
- Is the design appropriate for the problem?
- Is the solution over-engineered or under-engineered?
- Does it follow the existing architecture patterns?

### 2. Functionality Review
- Does the code do what the PR description claims?
- Are edge cases handled properly?
- Are error paths tested?
- Are there any race conditions or concurrency issues?

### 3. Code Quality Review
- Follows naming conventions (PEP8, ESLint, etc.)
- Functions are small and focused (single responsibility)
- No magic numbers or strings
- Comments explain WHY not WHAT
- No dead code or commented-out code

### 4. Testing Review
- Tests cover the change adequately
- Tests are deterministic (no flaky tests)
- Tests follow the team's naming conventions
- Edge cases and error paths are covered
- No test duplication

### 5. Performance Review
- No N+1 queries
- No unnecessary computations in hot paths
- Resource cleanup is proper (files, connections)
- Caching strategy is appropriate

### 6. Security Review
- Input validation on all user-facing endpoints
- Authentication checks on protected routes
- No secrets in code (API keys, passwords)
- SQL injection prevention (parameterized queries)
- XSS prevention (output encoding)

## Review Etiquette
- Be respectful and constructive
- Explain WHY something is wrong, not just WHAT
- Use "nit:" prefix for minor style suggestions
- Use "blocking:" prefix for must-fix issues
- Approve only when all blocking issues are resolved
