---
topic: "Story Implementation Workflow"
aliases: ["story-impl", "feature-workflow", "story-workflow", "user story", "feature implementation", "kod yazma"]
tags: [workflow, development, implementation, tdd]
priority: 10
strictness: 0.95
steps:
  - id: understand
    title: "Story'i Anla ve Kabul Kriterlerini Doğrula"
    mandatory: true
    checks: ["kabul kriteri", "DoD", "acceptance criteria", "definition of done", "story"]
  - id: test-plan
    title: "Test Planı Oluştur (Unit/Integration/E2E)"
    mandatory: true
    depends_on: [understand]
    checks: ["test pyramid", "test case", "scenario", "edge case", "unit", "integration"]
  - id: red-phase
    title: "Red Phase — Başarısız Test Yaz"
    mandatory: true
    depends_on: [test-plan]
    checks: ["fail", "assert", "expect", "should", "test"]
  - id: green-phase
    title: "Green Phase — Minimal Kodu Yaz"
    mandatory: true
    depends_on: [red-phase]
    checks: ["pass", "implement", "return", "function", "code"]
  - id: refactor-phase
    title: "Refactor Phase — Kodu İyileştir"
    mandatory: true
    depends_on: [green-phase]
    checks: ["refactor", "extract", "rename", "duplicate", "simplify", "DRY"]
  - id: review-prep
    title: "Code Review Hazırlığı"
    mandatory: true
    depends_on: [refactor-phase]
    checks: ["diff", "lint", "format", "type check", "review"]
  - id: pr-submit
    title: "Pull Request Oluştur"
    mandatory: true
    depends_on: [review-prep]
    checks: ["PR", "description", "title", "conventional commit", "pull request"]
---

# Story Implementation Workflow

## Purpose
Standardized process for implementing user stories and feature requests using TDD.

## Definition of Ready
- Acceptance criteria written and reviewed
- Dependencies identified and resolved
- Story estimated and sized appropriately
- Edge cases discussed

## Process

### 1. Understand & Plan
- Read the story description and acceptance criteria
- Clarify unknowns with product owner or stakeholders
- Identify affected components, services, and files
- Break down into sub-tasks if the story is large

### 2. Create Feature Branch
- Branch naming: `feat/ST-<ticket-number>-<kebab-case-description>`
- For stories without a ticket number: `feat/<short-description>`

### 3-5. TDD Cycle (Red-Green-Refactor)
Follow the TDD cycle for each test case:
- **Red:** Write a failing test for one acceptance criterion
- **Green:** Write minimal code to pass the test
- **Refactor:** Improve code quality without changing behavior

### 6. Code Review Preparation
- Run linter and formatter
- Run full test suite (must pass)
- Self-review your diff before requesting review

### 7. Submit Pull Request
- Write descriptive PR title following conventional commits
- Link the ticket/story in the description
- Add test evidence and screenshots if UI changes
- Request review from appropriate team members

## Definition of Done
- All acceptance criteria met
- Tests written and passing (unit + integration + e2e)
- Code reviewed and approved
- No new security vulnerabilities introduced
- Documentation updated
- Feature flag added (if needed for gradual rollout)
