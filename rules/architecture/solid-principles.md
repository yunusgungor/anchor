# SOLID Principles Rules

## Overview

SOLID is a set of five design principles for object-oriented software that produce code that is maintainable, extensible, and resilient to change. These rules apply at the class/module level.

---

## S — Single Responsibility Principle (SRP)

> A class should have one, and only one, reason to change.

- Each class/module should be responsible for a single part of the system's functionality.
- "Reason to change" = one actor or stakeholder whose requirements drive changes.
- If a class mixes concerns (e.g., persistence + business logic + formatting), split it.

**Signs of violation:**
- The class has many public methods that operate on unrelated data.
- A single change in requirements touches the class for multiple reasons.
- The class is hard to name precisely.

---

## O — Open/Closed Principle (OCP)

> Software entities should be open for extension, but closed for modification.

- Extend behaviour through new classes (inheritance, composition, strategy pattern), not by altering existing tested code.
- Use abstract interfaces / base classes that allow polymorphic substitution.
- Prefer composition over inheritance for adding new behaviours.

**Guidelines:**
- Define abstract interfaces for extensible behaviour.
- New features = new implementations of existing interfaces, not `if`/`elif` chains.
- Avoid adding new methods to existing interfaces that break existing implementations (use default methods or new interfaces).

---

## L — Liskov Substitution Principle (LSP)

> Subtypes must be substitutable for their base types without altering the correctness of the program.

- A derived class should not weaken the preconditions or strengthen the postconditions of its base class.
- Derived classes must preserve the invariants of the base class.

**Common violations:**
- Overriding a method to throw `NotImplementedError` or `raise` an unexpected exception.
- Strengthening validation in a subclass so callers' inputs are rejected.
- Returning a different type than the base class contract implies.
- Square extending Rectangle and breaking width/height invariants.

**Test:**
- Can you swap every usage of the base class with the derived class without any test failures? If not, LSP is violated.

---

## I — Interface Segregation Principle (ISP)

> No client should be forced to depend on methods it does not use.

- Prefer many small, focused interfaces over one "fat" interface.
- Split interfaces by role / client need.
- In Python, use duck typing or ABCs (`abc.ABC` + `@abstractmethod`) with minimal method sets.

**Signs of violation:**
- A class implements interface methods with `pass` or `raise NotImplementedError`.
- Clients receive an object but only use a subset of its methods.
- Interfaces are named with "and" (e.g., `ReadableAndWritable` — split it).

---

## D — Dependency Inversion Principle (DIP)

> High-level modules should not depend on low-level modules. Both should depend on abstractions. Abstractions should not depend on details. Details should depend on abstractions.

- High-level policy (use cases) defines the interfaces it needs.
- Low-level implementations (DB drivers, HTTP clients) implement those interfaces.
- Neither side depends on concrete implementations of the other.

**Mechanics:**
- Use abstract interfaces/ABCs defined in the application/domain layer.
- Inject implementations from the composition root (DI container or factory).
- Avoid direct `import` of low-level modules in high-level modules.

**Common Python pattern:**

```python
# Domain / Application layer (high-level)
from abc import ABC, abstractmethod

class UserRepository(ABC):
    @abstractmethod
    def find_by_id(self, user_id: str) -> User | None: ...

# Infrastructure layer (low-level)
class PostgresUserRepository(UserRepository):
    def find_by_id(self, user_id: str) -> User | None:
        # actual SQL query
        ...
```

---

## Enforcement

- Run linters (pylint, flake8-class-attributes) and architecture tests (import-linter) in CI.
- Review designs with SOLID checklist before implementation.
- Prefer composition over inheritance (except for LSP-correct subtype hierarchies).

## References
- Robert C. Martin, *Agile Software Development, Principles, Patterns, and Practices* (2002)
- Martin, Feathers, *SOLID Principles* (talks and blog series)
