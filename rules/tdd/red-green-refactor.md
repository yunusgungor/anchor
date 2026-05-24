# Red-Green-Refactor Cycle

## Core Principle

> *Write a failing test first (Red), make it pass with the simplest code (Green), then improve the code without changing behavior (Refactor).*

The Red-Green-Refactor cycle is the fundamental rhythm of Test-Driven Development. Each cycle typically lasts 30–120 seconds.

---

## 1. Red — Write a Failing Test

Before writing any production code, write a test that defines the desired behavior.

### Rules

- [ ] Write **exactly one** test at a time.
- [ ] The test must **fail** when run against the current codebase.
- [ ] The failure should be **for the intended reason** — not a compile/syntax error or a pre-existing failure.
- [ ] Test the **public interface** only; never test private/internal implementation details.
- [ ] Name the test to describe the **expected behavior**, not the implementation:

```python
# Good
def test_should_return_404_when_user_not_found():
def test_calculator_should_raise_on_division_by_zero():

# Bad
def test_user_repository_throws_exception():
def test_calculator_divide_method():
```

### Checklist

- [ ] Does the test describe one clear behavior?
- [ ] Is the test's failure meaningful?
- [ ] Would I understand what's expected by reading this test alone?

---

## 2. Green — Make the Test Pass

Write the **minimum amount of production code** needed to make the test pass.

### Rules

- [ ] Write **only** enough code to satisfy the current test.
- [ ] "Fake it" if you need to — return constants, hardcode values, write the simplest conditional.
- [ ] Do **not** add features or abstractions the test doesn't call for.
- [ ] Green as quickly as possible — speed matters more than elegance here.
- [ ] You may commit sins: duplication, magic numbers, long methods. **They will be fixed in Refactor.**

### Acceptable shortcut patterns

```python
# 1. Return a constant (then generalize later)
def get_user(id):
    return {"name": "Alice"}  # hardcoded for first test

# 2. If-else for known cases
def is_valid(isbn):
    return isbn == "0-306-40615-2"  # only valid ISBN known so far
```

### Green is SAFE

Once the test passes, you have **green safety**. All previous tests must still pass. If they don't, backtrack to the last green state.

---

## 3. Refactor — Improve Without Changing Behavior

Now that tests are green, **improve the code** — remove duplication, clarify names, extract methods, simplify logic.

### Rules

- [ ] All tests must remain **green** throughout refactoring.
- [ ] Never add new behavior during refactoring.
- [ ] Refactor **both production code and test code**.
- [ ] Run the full test suite after each refactoring step — not just the current test file.

### What to look for

| Smell | Fix |
|-------|-----|
| Duplicated code | Extract method/class |
| Long method | Extract smaller methods |
| Poor naming | Rename for clarity |
| Magic numbers | Define named constants |
| Conditional complexity | Replace with polymorphism/strategy |
| Test smells (brittle, slow, coupled) | Simplify test strategy |

### Refactoring scope

```
┌──────────────────────────────────────────┐
│  1. Production code                      │
│  2. Test code (keep tests clean too!)    │
│  3. Test infrastructure (fixtures, etc)  │
└──────────────────────────────────────────┘
```

---

## Cycle Flow

```
         ┌─────────────────────┐
         │   Write a test      │
         │   (expect failure)  │───── RED
         └─────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │   Test fails?       │─── No ──→ Fix test
         └─────────┬───────────┘
                   │ Yes
                   ▼
         ┌─────────────────────┐
         │  Write prod code    │
         │  (minimal to pass)  │───── GREEN
         └─────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  All tests pass?    │─── No ──→ Fix prod code
         └─────────┬───────────┘
                   │ Yes
                   ▼
         ┌─────────────────────┐
         │  Refactor           │───── REFACTOR
         │  (clean up,        │
         │   keep tests green) │
         └─────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  Write next test    │────→ Back to RED
         └─────────────────────┘
```

---

## Common Mistakes

| Mistake | Why it's wrong |
|---------|----------------|
| Writing many tests before any production code | Over-specification; tests become coupled and brittle |
| Refactoring before tests are green | No safety net; behavior changes may go undetected |
| Writing too much production code in Green phase | Over-engineering; violates YAGNI |
| Skipping Refactor phase | Accumulates technical debt; tests become hard to maintain |
| Testing implementation instead of behavior | Tests break on refactoring; lose their value as documentation |
| Making the test pass for the wrong reason | False confidence; test may pass but logic is wrong |

---

## Starting vs. Maintaining

| Phase | Focus |
|-------|-------|
| **Starting** a new feature | Follow strict RGR cycle from scratch |
| **Maintaining** existing code | Write a test that captures the bug (Red), fix it (Green), clean up (Refactor) |

When fixing a bug: **write a test that reproduces the bug first** — it's your Red step.

---

## References

- Kent Beck, *Test-Driven Development: By Example*
- Martin Fowler, *Refactoring: Improving the Design of Existing Code*
- Robert C. Martin, *Clean Code*
