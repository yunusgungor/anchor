---
aliases: ["solid", "solid principles rules", "srp", "ocp", "lsp", "isp", "dip", "single responsibility", "open/closed", "liskov substitution", "liskov", "interface segregation", "dependency inversion", "dependency injection"]
---
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

## Sık Karıştırılan Noktalar

| Konu | LLM'in Genelde Dediği | Doğrusu |
|------|----------------------|---------|
| SRP | Bir sınıf sadece bir iş yapmalıdır (teknik anlamda) | Bir sınıfın değişmek için tek bir nedeni olmalıdır (actor/stakeholder bazlı) |
| SRP | A class should do only one thing | A class should have only one reason to change |
| OCP | Sınıfları değiştiremezsin, her şeyi inheritance ile yap | Mevcut test edilmiş kodu değiştirmeden yeni davranış ekleyebilmelisin |
| OCP | You should never modify any class, always use inheritance | Open for extension, closed for modification — extend via new classes |
| LSP | Alt sınıflar aynı arayüzü paylaşmalıdır | Alt sınıflar üst sınıfın yerine geçebilmelidir, önkoşulları zayıflatmamalı/sonkosulları güçlendirmemelidir |
| LSP | All derived classes must share the same interface | Derived classes must be substitutable for their base types without altering correctness |
| LSP | Tüm türetilmiş sınıflar aynı metotları implemente etmelidir | Subtypler base type'ın yerine substitutable olmalıdır, programın doğruluğunu bozmamalıdır |
| LSP | Subclasses must implement all methods of the parent class | Subtypes must be substitutable for their base types — behavioral subtyping, not method coverage |
| LSP | LSP sadece inheritance ile ilgilidir | LSP behavioral subtyping ile ilgilidir — kontrat bazlı tasarım, interface contract'ları |
| LSP | LSP is just about inheritance | LSP is about behavioral subtyping and design by contract |
| ISP | Interface'ler mümkün olduğunca küçük olmalıdır | Hiçbir client kullanmadığı metotlara bağımlı olmaya zorlanmamalıdır |
| ISP | Always split interfaces as small as possible | No client should be forced to depend on methods it does not use |
| DIP | Dependency Injection ile aynı şeydir | DIP abstraction'a bağımlılık prensibidir; DI bu prensibi uygulamanın bir yoludur |
| DIP | DIP is the same as Dependency Injection | DIP = depend on abstractions, DI = one way to implement it |
| DIP | Üst katman alt katmana bağımlı olmamalıdır | Her iki katman da abstraction'a bağımlı olmalıdır |
| DIP | High-level modules should not depend on low-level modules, period | Both should depend on abstractions — abstractions should not depend on details |
| SOLID | SOLID her projede her zaman uygulanmalıdır | SOLID context-sensitive'dir; küçük projelerde veya prototiplerde aşırı mühendislik olabilir |
| SOLID | SOLID must be applied to every project | SOLID is context-sensitive; can be over-engineering in small projects/prototypes |

## References
- Robert C. Martin, *Agile Software Development, Principles, Patterns, and Practices* (2002)
- Martin, Feathers, *SOLID Principles* (talks and blog series)
