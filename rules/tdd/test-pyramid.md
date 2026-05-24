# Test Pyramid

## Core Principle

> *Write tests at different granularities — many fast unit tests, fewer integration tests, and a small number of end-to-end tests.*

The Test Pyramid guides how to distribute test effort across layers. It ensures fast feedback, maintainable suites, and sufficient coverage where it matters most.

---

## The Pyramid

```
                    ╱╲
                   ╱  ╲
                  ╱ E2E╲          ← Few: critical user journeys
                 ╱━━━━━━╲
                ╱Integration╲     ← Some: module boundaries, I/O
               ╱━━━━━━━━━━━━╲
              ╱              ╲
             ╱   Unit Tests   ╲    ← Many: fast, isolated, pure logic
            ╱━━━━━━━━━━━━━━━━━━╲
```

---

## Layer 1: Unit Tests (70–80% of tests)

### Definition

Tests that verify a single unit of behavior **in isolation**. A "unit" is typically a function, method, or class — tested without its real dependencies.

### Characteristics

- [ ] **Fast** — sub-millisecond per test
- [ ] **Deterministic** — same result every run
- [ ] **Isolated** — no database, no network, no filesystem
- [ ] **Focused** — test one behavior, one code path
- [ ] **Simple setup** — mocks/stubs for external dependencies

### When to use

- Pure functions (business logic, validators, transformers)
- Domain models and value objects
- Algorithm correctness
- Edge cases and error handling
- Utility functions

### Example structure

```
tests/
    unit/
        domain/
            test_inventory.py
            test_pricing.py
        services/
            test_calculator.py
        validators/
            test_isbn_validator.py
```

### Best practices

- One assert per test (or a small set of related asserts)
- Descriptive test names that read as specifications
- Parametrize tests to cover many cases efficiently
- Avoid mocks for value objects — use real instances

---

## Layer 2: Integration Tests (15–25% of tests)

### Definition

Tests that verify a module **interacts correctly** with its external dependencies (database, filesystem, network services, other modules).

### Characteristics

- [ ] **Moderate speed** — tens to hundreds of milliseconds
- [ ] **Real or near-real dependencies** — test database, test containers
- [ ] **Boundary-focused** — tests the seam between your code and the outside world
- [ ] **Stateful setup/teardown** — fixtures, transactions, clean-up

### What to cover

- Repository/database operations (CRUD, transactions, migrations)
- I/O operations (file read/write, streams)
- Network calls (API clients, message queues — use test doubles or sandboxes)
- Module interaction (service calls repository, controller calls service)
- Configuration loading and environment setup

### Example structure

```
tests/
    integration/
        repositories/
            test_user_repository.py
        api/
            test_payment_client.py
        services/
            test_checkout_flow.py
        database/
            test_migrations.py
```

### Best practices

- Use **transactional rollbacks** — wrap each test in a database transaction that rolls back after the test
- Use **test infrastructure** (Docker Compose, Testcontainers) for real dependencies
- Tests should be **order-independent** — any test can run in any sequence
- Keep fixtures **shared but minimal** — not every test needs a full data dump
- Prefer **contract tests** over end-to-end tests for service boundaries

---

## Layer 3: End-to-End Tests (5–10% of tests)

### Definition

Tests that exercise the entire system **from the user's perspective** — through the UI, API, and all backend services.

### Characteristics

- [ ] **Slow** — seconds to minutes per test
- [ ] **Brittle** — sensitive to timing, network, and state
- [ ] **Expensive** — requires full system deployment
- [ ] **High confidence** — validates real user workflows

### What to cover

- **Critical user journeys** (signup → purchase, search → detail → checkout)
- **System-level behaviors** (logging, auth, error pages)
- **Deployment verification** (smoke tests after deploy)
- Only paths that **cannot be adequately covered** by lower layers

### Example structure

```
tests/
    e2e/
        test_user_signup_and_login.py
        test_catalog_browsing.py
        test_checkout_payment.py
        test_admin_workflows.py
```

### Best practices

- **Minimize** — every E2E test is a bet against your CI pipeline's stability
- Use **API-level tests** instead of UI-driven tests when possible
- Design tests to be **idempotent** — running twice should produce the same result
- Use **retry logic** for flaky operations (with bounded attempts)
- Run in **CI only**, not on developer machines (pre-commit hooks)
- Consider the **Trophy Test** approach (see below)

---

## Alternative: The Test Trophy

Some teams prefer the **Test Trophy** (popularized by Kent C. Dodds) over the strict pyramid:

```
          ╱╲
         ╱  ╲
        ╱ E2E╲
       ╱━━━━━━╲
      ╱Integration╲
     ╱━━━━━━━━━━━━╲
    ╱  Static Analysis ╲    ← TypeScript, ESLint, Pyright, mypy
   ╱━━━━━━━━━━━━━━━━━━━━╲
  ╱    Unit Tests         ╲
 ╱━━━━━━━━━━━━━━━━━━━━━━━━╲
```

This emphasizes: **write tests that give you the most confidence for the least maintenance cost**. Integration tests often yield better ROI than excessive unit tests.

---

## Anti-Patterns

| Anti-Pattern | Description | Fix |
|-------------|-------------|-----|
| **Ice-cream Cone** | Too many E2E tests, few unit tests | Shift left — more unit + integration |
| **Hourglass** | Many unit + E2E, few integration | Add integration layer for I/O boundaries |
| **Golden Hammer** | Every test uses the same technique (e.g., all mocked) | Vary technique by layer and dependency |
| **Test Pyramid of Giza** | Giant, slow E2E suite covering everything | Replace with targeted E2E + broad lower layers |
| **No Integration Tests** | All unit tests, all mocked | Add real integration tests for critical I/O paths |

---

## Decision Matrix

| Scenario | Layer | Reason |
|----------|-------|--------|
| Pure business logic | Unit | Fast, isolated, comprehensive |
| Database query / mutation | Integration | Real SQL semantics matter |
| API request/response handling | Integration | Serialization, status codes, headers |
| 3rd-party API call | Integration (with sandbox) | Confirm contract, handle errors |
| User signup → dashboard | E2E | Validates full system wiring |
| UI rendering | E2E or Visual Regression | Depends on stack and priority |
| Configuration loading | Integration | Environment-specific behavior |
| Utility/helper function | Unit | Pure input → output |

---

## Checking Your Balance

Run the test suite periodically and review:

```
Unit tests:       1200 / 1500 (80%)    ✅
Integration tests:  250 / 1500 (17%)   ✅
E2E tests:           50 / 1500 (3%)    ✅
Suite runtime:   4.2 seconds           ✅
```

- If E2E > 20% → **add more unit/integration tests**
- If integration < 10% → **add boundary tests for I/O dependencies**
- If suite runtime > 10 seconds → **slow tests need attention**
- If unit tests are > 95% and integration/E2E near 0% → **you're likely over-mocking**

---

## References

- Mike Cohn, *Succeeding with Agile* (original pyramid concept)
- Martin Fowler, *TestPyramid* (martinfowler.com)
- Kent C. Dodds, *The Testing Trophy and Testing Classifications*
- Google Testing Blog, *Just Say No to More End-to-End Tests*
