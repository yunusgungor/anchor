# Architecture Decision Records (ADRs)

## Core Principle

> *Document every significant architectural decision with its context, consequences, and rationale — so future teams understand **why** the system is the way it is.*

An Architecture Decision Record (ADR) is a short, structured document that captures a single architectural decision and its rationale. ADRs live alongside the code and are reviewed as part of the development process.

---

## 1. When to Write an ADR

### Rules

- [ ] Write an ADR for ANY decision that affects the system's structure, non-functional properties, or development approach.
- [ ] Write an ADR when the decision is **hard to reverse** or has significant downstream impact.
- [ ] Write an ADR when there are multiple viable options and a choice was made between them.

### Examples of decisions that require an ADR

| Decision type                    | Example                                               |
|----------------------------------|-------------------------------------------------------|
| Technology choice                | "Use PostgreSQL over MongoDB for document storage"    |
| Framework selection              | "Use FastAPI instead of Flask"                        |
| Library or dependency adoption   | "Adopt Pydantic v2 for data validation"               |
| Architectural pattern            | "Use CQRS for the reporting subsystem"                |
| Deployment strategy              | "Adopt Kubernetes over ECS for orchestration"         |
| Security architecture            | "Use OAuth2 with PKCE for API authentication"         |
| Data model decisions             | "Use soft-deletes with tombstone columns"             |
| API design decisions             | "Use GraphQL over REST for the public API"            |
| Migration strategy               | "Migrate from monolith to microservices in phases"    |

### Examples of decisions that do NOT need an ADR

| Non-decision                     | Why                                            |
|----------------------------------|------------------------------------------------|
| Choosing a variable name         | Too granular; handled by code review           |
| Minor library version bump       | Covered by changelog and release notes         |
| Formatting or linting preference | Covered by `.editorconfig` and linter config   |
| Daily implementation choices     | Captured in commit messages and PR descriptions|

---

## 2. ADR File Format

### Rules

- [ ] Each ADR is a single markdown file.
- [ ] File naming convention: `adr-<NNNN>-<short-slug>.md` where `<NNNN>` is a zero-padded, monotonically increasing number.
- [ ] The slug MUST be kebab-case matching the title.
- [ ] ADRs live in `docs/adr/` at the repository root.
- [ ] Metadata is stored in YAML frontmatter.

### File Structure

```
docs/adr/
├── adr-0001-use-postgresql-for-primary-store.md
├── adr-0002-adopt-fastapi-framework.md
├── adr-0003-message-queue-with-redis-streams.md
└── index.md           # auto-generated or manual table of contents
```

### Frontmatter Template

```yaml
---
title: "<short title, max ~20 words>"
status: "proposed | accepted | deprecated | superseded"
date: <YYYY-MM-DD>
deciders: <comma-separated list of people who made the decision>
supersedes: <adr-NNNN if applicable>
superseded-by: <adr-NNNN if applicable>
---
```

---

## 3. ADR Body Template

Each ADR body MUST follow the **Y-Statements** format:

```markdown
# ADR-NNNN: <Title>

## Context

What is the issue motivating this decision? Describe the problem, forces at play,
and any relevant background. Be specific about technical, business, or operational
constraints. This section should give a reader enough context to understand the
options, even if they are new to the project.

## Decision

State the decision clearly in one sentence. Then provide a brief description of
the chosen approach.

**We will adopt <X> over <Y> because <Z>.**

## Options Considered

List the alternatives that were seriously evaluated. For each option, include:

### Option 1: <Name>

- **Description**: Brief summary of this approach
- **Pros**: Key advantages
- **Cons**: Key disadvantages
- **Feasibility**: High / Medium / Low

### Option 2: <Name>

- **Description**: ...
- **Pros**: ...
- **Cons**: ...
- **Feasibility**: ...

### Option 3: <Name>

- **Description**: ...
- **Pros**: ...
- **Cons**: ...
- **Feasibility**: ...

## Rationale

Why was the chosen option selected over the alternatives? Reference specific
criteria that drove the decision:

- **Performance**: ...
- **Maintainability**: ...
- **Team expertise**: ...
- **Ecosystem maturity**: ...
- **Operational cost**: ...
- **Security**: ...
- **Scalability**: ...

## Consequences

What trade-offs were accepted? What becomes easier or harder as a result of this
decision?

### Positive

- [ ] ...
- [ ] ...

### Negative

- [ ] ...
- [ ] ...

## Compliance

How will this decision be enforced or verified?

- [ ] Automated checks (linters, architecture tests, CI gates)
- [ ] Code review guidelines
- [ ] Manual audit during release

## References

- [Link to related ADRs](...)
- [Link to external documentation](...)
- [Link to discussion or RFC](...)
```

---

## 4. ADR Lifecycle & States

### State Machine

```
                    ┌──────────────┐
                    │   Proposed   │
                    └──────┬───────┘
                           │ Review & approval
                           ▼
                    ┌──────────────┐
              ┌─────│   Accepted   │─────┐
              │     └──────────────┘     │
              │           │              │
              │    Implementation        │
              │           │              │
              ▼           ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │ Superseded │ │ Deprecated │ │   Active   │
     └────────────┘ └────────────┘ └────────────┘
```

### Rules

- [ ] `proposed` — The ADR is under review. It has been submitted as a PR but not yet merged.
- [ ] `accepted` — The ADR has been approved and merged. Implementation may not have started.
- [ ] `active` — (Implied) The decision is currently in effect. Use `accepted` status for merged ADRs; once implementation is done, the status remains `accepted` unless superseded.
- [ ] `deprecated` — The decision is no longer recommended but still in use. No active development should follow this ADR.
- [ ] `superseded` — A newer ADR has replaced this one. The `superseded-by` field points to the replacement.
- [ ] A status column in the index SHOULD reflect the current state of each ADR.

### Versioning

- ADRs are **immutable after merge** — never edit an accepted ADR to change the decision.
- If the decision changes, create a NEW ADR that supersedes the old one.
- The old ADR gets `status: superseded` and `superseded-by: adr-NNNN`.
- The new ADR gets `supersedes: adr-NNNN`.
- Fix typos or formatting errors via a separate PR; use `status: accepted` (unchanged).

---

## 5. ADR Review Process

### Rules

- [ ] ADRs MUST go through the same PR review process as code changes.
- [ ] At least one **architect or tech lead** MUST approve an ADR before merge.
- [ ] The PR description SHOULD link to any supporting research, spike results, or discussion threads.
- [ ] Review criteria:
  - Is the Context sufficient for someone new to understand the problem?
  - Were a reasonable set of Options Considered?
  - Is the Rationale clear and data-driven (not just preference)?
  - Are the Consequences honestly assessed (both positive and negative)?
  - Is the Compliance section actionable?

### PR Checklist for ADRs

- [ ] Is the numbering sequential (no gaps)?
- [ ] Does the filename match the slug in the title?
- [ ] Is the frontmatter complete?
- [ ] Are all sections filled (Context, Decision, Options Considered, Rationale, Consequences, Compliance, References)?
- [ ] Does the ADR supersede any previous ADR? If so, is that noted?

---

## 6. Index / Table of Contents

Maintain a `docs/adr/index.md` that serves as a registry of all ADRs.

### Template

```markdown
# Architecture Decision Records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-0001](adr-0001-use-postgresql-for-primary-store.md) | Use PostgreSQL for Primary Store | Accepted | 2025-01-15 |
| [ADR-0002](adr-0002-adopt-fastapi-framework.md) | Adopt FastAPI Framework | Accepted | 2025-02-01 |
| [ADR-0003](adr-0003-message-queue-with-redis-streams.md) | Message Queue with Redis Streams | Superseded | 2025-03-10 |
| [ADR-0004](adr-0004-message-queue-with-nats.md) | Message Queue with NATS | Active | 2025-04-01 |
```

---

## 7. Tooling & Automation

### Recommendations

| Concern | Tool / Approach |
|---------|----------------|
| ADR scaffolding | `adr-log` CLI or a simple `cp` from template |
| Status tracking | YAML frontmatter + index regeneration |
| Linking ADRs to code | Reference ADR numbers in comments: `# See ADR-0003` |
| CI validation | Check frontmatter completeness, filename conventions, link validity |

### Example: ADR CLI (adr-log)

```bash
# Generate a new ADR from template
adr new "Use NATS for message queuing"

# Rebuild the index
adr generate index
```

---

## References

- [Michael Nygard — Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [ADR GitHub Organization](https://adr.github.io/)
- [Joel Parker Henderson — ADR Examples](https://github.com/joelparkerhenderson/architecture-decision-records)
- [Y-Statements — A Structured Format for ADRs](https://medium.com/@olafhartig/y-statements-aka-architecture-decision-records-10e9c54b0eb9)
