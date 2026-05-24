# Design Patterns Rules

## Overview

This document catalogs the design patterns preferred in this codebase, when and why to use them, and specific implementation guidance. Patterns from the Gang of Four (GoF) and domain-driven design (DDD) are covered.

---

## Creational Patterns

### Factory Method
- **Use when**: A class can't anticipate the class of objects it must create; subclasses specify the concrete type.
- **Our convention**: Name factory methods `create_*` or `of_*` (e.g., `PaymentGateway.create(type)`).
- **Anti-pattern**: Avoid factory explosion — one factory per family is sufficient.

### Abstract Factory
- **Use when**: Creating families of related products without specifying their concrete classes.
- **Our convention**: One abstract factory interface per product family; concrete factories bound at composition root.

### Builder
- **Use when**: An object requires multi-step construction with many optional parameters (especially when immutable after build).
- **Avoid when**: A simple dataclass with default values suffices.
- **Our convention**: Builder methods return `self` for fluent chaining; final product retrieved via `.build()`.

### Singleton
- **Use sparingly**: Only for truly system-wide resources (logging, config, DI container).
- **Implementation**: Prefer module-level instance or dependency injection over a `__new__`-based Singleton class.
- **Avoid**: Singletons that hold mutable shared state — they create hidden coupling and impede testing.

---

## Structural Patterns

### Adapter
- **Use when**: You need to make an existing class interface conform to a target interface expected by a client.
- **Our convention**: `*Adapter` suffix (e.g., `PaymentGatewayAdapter`). Name the target interface clearly (e.g., `PaymentProcessor`).

### Facade
- **Use when**: A complex subsystem should be exposed through a simplified uniform interface.
- **Our convention**: A single class in the outer layer that delegates to internal components. The facade should not become a god object.

### Repository
- **Use when**: You need to abstract data access behind a collection-like interface (DDD tactical pattern).
- **Our convention**:
  - Repository interfaces live in the domain/application layer.
  - One repository per aggregate root.
  - Standard methods: `find_by_id`, `save`, `delete`, `find_all`, plus domain-specific queries.

### Proxy
- **Use when**: Controlling access to an object (lazy loading, access control, logging).
- **Our convention**: Same interface as the real subject; proxy forwards calls after cross-cutting logic.

---

## Behavioural Patterns

### Strategy
- **Use when**: A family of algorithms should be interchangeable at runtime.
- **Our convention**: A strategy interface (ABC) with one method; concrete strategies injected via constructor or setter.
- **Example**: Shipping cost calculators, validation rules, pricing strategies.

### Observer / Event Publisher
- **Use when**: A change in one object should trigger updates in multiple dependents without tight coupling.
- **Our convention**: Use an event bus / message broker abstraction in the domain layer (domain events). Listeners are registered at the composition root.
- **Avoid**: Direct `Observer` lists exposed publicly — wrap in a publisher.

### Command
- **Use when**: Encapsulating a request as an object (undoable operations, queuing, transactional boundaries).
- **Our convention**: `Command` classes with a single `execute()` method. Use with a command bus for dispatch.
- **Consider**: CQRS — separate Commands (writes) from Queries (reads).

### Template Method
- **Use when**: You want to define the skeleton of an algorithm in a base class and let subclasses override specific steps without changing the structure.
- **Our convention**: Base class methods call abstract "hook" methods; subclasses implement hooks. Mark the template method as `final` if the language supports it.

### Chain of Responsibility
- **Use when**: More than one handler may process a request, and the handler is determined at runtime.
- **Our convention**: Middleware pipeline for HTTP requests, validation chains, or event processing. Each handler decides to process or pass to the next.

### Mediator
- **Use when**: Multiple objects interact in complex ways and you want to centralise communication logic.
- **Example**: Chat room, orchestration layer in a microservice, UI component coordinator.

---

## Architectural Patterns

### MVC / MVT
- Django naturally follows Model-View-Template. Views handle request logic; templates handle presentation.
- **Our rule**: Keep business logic in services/forms, not in views, not in templates.

### Domain-Driven Design (DDD)
- Use entities, value objects, aggregates, domain events, and repositories at the core.
- Application services orchestrate domain logic; infrastructure provides persistence and external I/O.
- Ubiquitous language must be reflected in code names.

### Hexagonal Architecture (Ports & Adapters)
- Define ports (interfaces) in the domain/application layer.
- Adapters (implementations) live in the infrastructure layer.
- Core has zero imports from frameworks.

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why |
|---|---|
| **God Class** | A class that knows too much or does too much. Violates SRP. |
| **Singleton Overuse** | Creates hidden coupling, complicates testing. |
| **Call Super** | Subclasses must call `super().method()` for correctness — fragile hierarchy. Prefer Template Method. |
| **Yo-Yo Problem** | Deep inheritance hierarchies require jumping up and down to understand flow. Favour composition. |
| **Anemic Domain Model** | Domain objects with getters/setters only; logic lives in services. Violates encapsulation. |

## Enforcement

- Design patterns should be documented with a rationale in the module docstring or README.
- Code reviews check for appropriate pattern usage (not over-engineering, not under-engineering).
- Heavy patterns (Abstract Factory, Mediator, Command Bus) require team consensus before adoption.

## References
- Gamma, Helm, Johnson, Vlissides, *Design Patterns: Elements of Reusable Object-Oriented Software* (1994, GoF)
- Eric Evans, *Domain-Driven Design: Tackling Complexity in the Heart of Software* (2003)
- Martin Fowler, *Patterns of Enterprise Application Architecture* (2002)
