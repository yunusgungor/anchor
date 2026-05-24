# Automated Testing Standards

> **Purpose:** Define how tests are written, organized, executed, and maintained in the CI pipeline to ensure fast feedback, reliable coverage, and minimal flakiness.

---

## 1. Testing Philosophy

> *Write tests that give you the most confidence for the least maintenance cost.*

- **Every merge to `main` must be tested.** No exceptions.
- Tests are **first-class code** — they undergo code review, follow style guides, and are refactored when necessary.
- Prefer **behavioral testing** (what the system does) over **implementation testing** (how it does it).
- A failing test is a **blocking signal** — investigate and resolve before merging.

---

## 2. What to Automate — Decision Matrix

| Category | Automate? | Tool / Approach |
|----------|-----------|-----------------|
| Unit tests (pure logic) | ✅ Always | pytest, Jest, Vitest, Go test |
| Integration tests (DB, API, I/O) | ✅ Always | pytest + docker, Testcontainers |
| Contract tests (service boundaries) | ✅ Always | Pact, Spring Cloud Contract |
| E2E / smoke tests | ✅ Critical journeys only | Playwright, Cypress, Selenium |
| Visual regression | ✅ UI-heavy projects | Percy, Chromatic, Applitools |
| Security scanning (SAST) | ✅ Always | Semgrep, CodeQL, Bandit |
| Dependency vulnerabilities | ✅ Always | Dependabot, Snyk, pip-audit |
| Performance / load tests | ⚡ Scheduled, not per-commit | k6, Locust, Gatling |
| Accessibility | ✅ On staging deploy | axe-core, Lighthouse CI |
| Manual exploratory testing | 🧠 Human judgment | Test case management (Zephyr, TestRail) |

---

## 3. Test Organization

### Directory structure

```
tests/
    unit/                  # Layer 1 — fast, isolated
        domain/
        services/
        utils/
    integration/           # Layer 2 — real dependencies
        repositories/
        api/
        workflows/
    e2e/                   # Layer 3 — critical user journeys
    contract/              # Consumer-driven contract tests
    performance/           # Load & stress tests (optional)
```

### File naming convention

- Test files match the module they test: `test_{module_name}.py` or `{module}.test.ts`
- Test classes (where used): `Test{ClassName}`
- Test functions: `test__{unit}__{scenario}__{expected_outcome}`

```
test__calculator__with_negative_numbers__returns_zero
test__checkout__when_inventory_low__rejects_order
```

---

## 4. Pre-Commit Testing

Before pushing, developers must run:

- [ ] Linter passes with no errors
- [ ] Type checker passes with no errors
- [ ] All unit tests pass locally
- [ ] New code has corresponding tests (see coverage section)

### Pre-commit hooks

Configured via `.pre-commit-config.yaml`:

| Hook | Purpose |
|------|---------|
| `detect-secrets` | Prevent credential leaks |
| `ruff` / `eslint` | Code linting |
| `black` / `prettier` | Code formatting |
| `mypy` / `tsc` | Type checking (optional, fast path) |
| `pytest` / `jest` | Unit test execution (optional — faster to run in CI) |

---

## 5. CI Test Execution

### Execution order

1. **Unit tests** — run first; must pass before any other test stage begins.
2. **Integration tests** — run after unit tests pass.
3. **Contract tests** — run after integration tests (or in parallel, if infrastructure allows).
4. **E2E tests** — run last, only after deployment to review/staging environment.

### Parallelism

- Unit tests are **fully parallelizable** — split across CI runners by file or by test.
- Integration tests share a **test database per runner** — avoid cross-test interference.
- E2E tests run **serially** within a runner to avoid state contention.

### Timeouts

| Test Type | Timeout | Action |
|-----------|---------|--------|
| Unit test suite | 5 min | Investigate slow tests |
| Individual unit test | 5 s | Split or refactor |
| Integration test suite | 10 min | Optimize fixtures or split |
| Individual integration test | 30 s | Check for unnecessary I/O |
| E2E test suite | 15 min | Reduce scope or parallelize |
| Individual E2E test | 3 min | Simplify test scenario |

---

## 6. Test Fixtures and Data

### Principle

> *Tests should create the data they need and clean up after themselves.*

- **Use factories** (Factory Boy, Fishery, Builders) over raw fixtures for test data.
- **Use transactions** for database tests — wrap each test in a transaction and roll back on teardown.
- **Seeds are not tests** — shared seed data creates hidden dependencies between tests.

### Fixture anti-patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Shared mutable fixtures | Tests order-dependent | Each test creates its own data |
| Static JSON files | Brittle, hard to update | Use factory with in-line overrides |
| Loading production data | Slow, includes irrelevant data | Use minimal targeted fixtures |
| Giant `conftest.py` | Hidden coupling, hard to debug | Scope fixtures to the test file or module |

---

## 7. Coverage Standards

### Minimum thresholds

| Metric | Threshold | Measurement |
|--------|-----------|-------------|
| Line coverage | ≥ 80% | Total codebase |
| Branch coverage | ≥ 70% | Conditional branches |
| New code coverage | ≥ 90% | Lines added in the diff |
| Function coverage | ≥ 85% | All exported/public functions |

### Enforcement

- CI **fails** if coverage drops below the threshold for new code.
- PRs that introduce new code without corresponding tests are **blocked**.
- Coverage reports are generated and published as a CI artifact for every `main` build.

### Measurement tools

| Language | Tool |
|----------|------|
| Python | pytest-cov |
| TypeScript / JavaScript | c8, Istanbul (Jest `--coverage`) |
| Go | `go test -coverprofile` |
| Java | JaCoCo |
| Rust | tarpaulin, `cargo-llvm-cov` |

---

## 8. Flaky Test Management

A **flaky test** is one that passes and fails without code changes.

### Process

1. **Detect** — CI automatically tags tests that fail intermittently (rerun up to 2×; if passes on retry, mark as flaky).
2. **Quarantine** — Move the test to a `tests/quarantine/` directory. CI runs quarantined tests but does not block on them.
3. **Prioritize** — Quarantined tests must be resolved within **5 business days** or a bug is filed.
4. **Resolve** — Fix the root cause (shared state, timing, test ordering, or environment issue).
5. **Return** — Once fixed, move the test back to its original location.

### Flaky test dashboard

Track in a visible location:

```
Test                          | Flaky Count | Last Seen     | Status
test__checkout__concurrent    | 7           | 2026-05-20    | Quarantined (#4281)
test__search__fuzzy_match     | 3           | 2026-05-18    | In review
test__auth__token_refresh     | 1           | 2026-05-15    | ✅ Fixed
```

---

## 9. Test Environment Management

### CI test environments

- All external dependencies (databases, queues, caches) are provisioned **ephemerally** per pipeline run.
- Use **Docker Compose** or **Testcontainers** for local and CI service topology.
- Never share a database or queue between parallel CI runs.

### Local test environment

```bash
# Standard local test invocation
make test              # runs unit tests (fast)
make test-all          # runs unit + integration (requires Docker)
make test-e2e          # runs end-to-end (requires full stack)
make test-coverage     # runs with coverage report
```

### Environment variables for testing

- `DATABASE_URL` — test database connection string
- `REDIS_URL` — test Redis instance
- `API_BASE_URL` — base URL for API tests (set to mock or local server)
- `CI=true` — set by CI platform; tests can branch behavior if needed
- `TEST_ENV=ci|local` — explicit environment indicator

---

## 10. Test Reporting

### Pipeline output

Each test stage produces:

- **JUnit XML** report (or equivalent machine-readable format)
- **Console summary** with pass/fail/skip counts
- **Failure details** — stack trace, expected vs actual, relevant log snippets
- **Duration breakdown** — per test, per suite, per stage

### Artefacts

| Artifact | Retention | Consumers |
|----------|-----------|-----------|
| JUnit XML reports | 30 days | CI platform, dashboards |
| Coverage report (HTML) | 30 days | Developers, PR reviewers |
| Test logs (stdout/stderr) | 7 days | Debugging failures |
| Screenshots (E2E failures) | 30 days | Debugging UI failures |
| Test video (E2E, optional) | 14 days | Debugging flaky E2E tests |

---

## 11. Testing Standards by Technology Stack

### Python (pytest)

- Use `pytest` as the test runner.
- Use `pytest-cov` for coverage.
- Use `pytest-xdist` for parallel execution.
- Use `pytest-mock` for mocking (built-in `unittest.mock` is acceptable).
- Fixtures in `conftest.py` should be **session-scoped** only for truly expensive setup (e.g., Docker containers).

### TypeScript / JavaScript (Jest / Vitest)

- Use `Vitest` for Vite-based projects, `Jest` for others.
- Avoid `jest.resetAllMocks()` in `afterEach` — prefer explicit mock restoration.
- Snapshot tests require **explicit review** during PR — never approve a snapshot update without verifying the change.
- Use `describe` blocks to group related tests.

### Go

- Use standard `testing` package with `go test`.
- Table-driven tests are the preferred pattern.
- Use `testify/assert` or `testify/require` for readable assertions.
- Benchmark tests (`BenchmarkXxx`) where performance is critical.

---

## 12. Enforcement

| Rule | Tool / Method |
|------|--------------|
| Unit tests pass before integration | CI stage ordering |
| Coverage thresholds | CI check (pytest-cov threshold, Jest `--coverageThreshold`) |
| No flaky tests in main branch | Quarantine policy (PR to un-quarantine required) |
| Test naming convention | Linter rule (custom) + code review |
| Pre-commit hooks | `.pre-commit-config.yaml` enforced via CI |
| Contract tests on service boundaries | CI stage that runs pact tests |
| Test environment isolation | Docker Compose / Testcontainers per CI runner |

---

## References

- [Test Pyramid](https://martinfowler.com/bliki/TestPyramid.html) — Martin Fowler
- [The Testing Trophy](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications) — Kent C. Dodds
- [Just Say No to More End-to-End Tests](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html) — Google Testing Blog
- [Flaky Tests at Google](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html)
- [pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
