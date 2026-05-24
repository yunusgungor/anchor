---
topic: "TDD Red-Green-Refactor Cycle"
aliases: ["tdd-cycle", "red-green-refactor", "tdd-loop", "test-first-cycle", "test driven development", "red green refactor", "test first"]
tags: [workflow, tdd, testing, quality, development]
priority: 10
strictness: 0.95
steps:
  - id: write-failing-test
    title: "Kırmızı: Başarısız Test Yaz"
    mandatory: true
    aliases: ["started with a failing test", "wrote a failing test"]
    ch...[truncated]
  - id: verify-failure
    title: "Testin Gerçekten Başarısız Olduğunu Doğrula"
    mandatory: true
    depends_on: [write-failing-test]
    checks: ["fail", "red", "error", "message", "expected failure"]
  - id: minimal-code
    title: "Yeşil: Geçmesi İçin Minimal Kod Yaz"
    mandatory: true
    depends_on: [verify-failure]
    checks: ["pass", "minimal", "implement", "return", "green"]
  - id: verify-pass
    title: "Testin Geçtiğini Doğrula"
    mandatory: true
    depends_on: [minimal-code]
    checks: ["pass", "green", "success", "all tests", "CI"]
  - id: eliminate-duplication
    title: "Refactor: Tekrarı Yok Et, Tasarımı İyileştir"
    mandatory: true
    depends_on: [verify-pass]
    checks: ["duplicate", "DRY", "extract", "simplify", "rename", "refactor"]
  - id: verify-refactor
    title: "Refactor Sonrası Tüm Testleri Çalıştır"
    mandatory: true
    depends_on: [eliminate-duplication]
    checks: ["all tests", "pass", "regression", "CI", "green"]
  - id: next-test
    title: "Sonraki Teste Geç / İterasyonu Tamamla"
    mandatory: false
    depends_on: [verify-refactor]
    checks: ["next", "continue", "cycle", "iteration", "complete"]
---

# TDD Red-Green-Refactor Cycle

## Purpose
The fundamental TDD loop that ensures correct, testable, and well-designed code.

## The Three Laws of TDD
1. You must not write production code until you have written a failing unit test
2. You must not write more of a unit test than is sufficient to fail (and not compiling is failing)
3. You must not write more production code than is sufficient to pass the currently failing test

## Cycle Details

### 🔴 Red Phase
- Write a test that defines a desired behavior
- Run the test — it MUST fail (red)
- If it passes, the test is not testing anything meaningful
- Write the minimum test possible

### 🟢 Green Phase
- Write the minimum production code to pass the test
- No refactoring yet — this phase is about making it work
- "Quick green" — take shortcuts, don't worry about design
- Run all tests — they MUST pass (green)

### 🔵 Refactor Phase
- Improve the code quality without changing behavior
- Remove duplication
- Improve naming
- Simplify design
- Run all tests after each refactoring step
- If tests fail during refactoring, undo the last change

## Key Principles

| Principle | Explanation |
|-----------|-------------|
| Baby Steps | Make the smallest possible change each cycle |
| Triangulation | Add tests to drive general solutions |
| Obvious Implementation | Skip Red phase for trivial code |
| Fake It | Return a constant, then generalize |
| Transformation | Change behavior via refactoring patterns |

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Testing too much | Writing many tests before Red | One test per cycle |
| Skipping Red | Writing code without failing test | Commit to TDD rules |
| Skipping Refactor | Accumulating technical debt | Cycle back to Refactor |
| Testing internals | Brittle tests | Test behavior, not implementation |
