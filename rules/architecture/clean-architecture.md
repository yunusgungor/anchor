# Clean Architecture Rules

## Overview

Clean Architecture (Robert C. Martin) prescribes a layered separation of concerns where dependencies point inward — from infrastructure and delivery mechanisms toward business rules and entities.

## Core Principles

### 1. Dependency Rule
- Source code dependencies must point **inward** toward higher-level policies.
- Nothing in an inner circle can know about anything in an outer circle.
- Outer circles (frameworks, drivers, UI) depend on inner circles (use cases, entities).

### 2. Layer Structure

**Entities / Domain Layer** (innermost)
- Enterprise-wide business rules and domain objects.
- Pure Python — no framework imports, no I/O, no database references.
- Methods encapsulate critical business logic without side effects.

**Use Case / Application Layer**
- Application-specific business rules.
- Orchestrates the flow of data to and from entities.
- Depends only on entities and boundary interfaces (repositories, presenters).
- Contains no UI, no database, no external framework code.

**Interface Adapters Layer**
- Adapters that convert data between use cases and external agencies.
- Presenters, controllers, gateway implementations.
- Database ORM mappers, serializer/deserializer.
- Cast external formats (HTTP requests, DB rows) into use-case-friendly objects.

**Frameworks & Drivers Layer** (outermost)
- Glue code — frameworks, HTTP routers, database drivers.
- Minimal logic; delegates to interface adapters.

### 3. Cross-Boundary Communication

- **Boundary interfaces** are defined by the inner layer (use case) and implemented by the outer layer.
- Use **Data Transfer Objects (DTOs)** or simple dicts for crossing boundaries; never pass framework objects.
- Example: `Repository` abstract class lives in the use-case layer; its SQLAlchemy implementation lives in the adapters layer.

### 4. Dependency Injection

- Outer layers construct and inject dependencies into inner layers.
- Inner layers never instantiate concrete outer-layer classes.
- A DI container or factory at the composition root wires the graph.

### 5. Testing

- Inner layers (entities + use cases) must be testable without a database, HTTP server, or UI.
- Mock/stub boundary interfaces for unit tests.
- Integration tests cover adapter implementations.

## File Organization Convention

```
src/domain/          # Entities, value objects, domain events
src/application/     # Use cases, ports (interfaces)
src/adapter/         # Presenters, controllers, gateway impls
src/infrastructure/  # DB config, framework setup, external APIs
```

## Enforcement (Linting / Architecture Tests)

- Use `import-linter` (Python) or equivalent to enforce layer dependency boundaries.
- Architectural boundaries should be checked in CI.

## References
- Robert C. Martin, *Clean Architecture: A Craftsman's Guide to Software Structure and Design* (2017)
- The Dependency Rule is inviolable — any violation is an architectural debt.
