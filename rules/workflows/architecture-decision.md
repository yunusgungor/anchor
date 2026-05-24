---
topic: "Architecture Decision Process"
aliases: ["architecture-decision", "adr-process", "arch-decision", "design-decision", "architecture decision", "system design", "tech decision"]
tags: [workflow, architecture, design, documentation, adr]
priority: 10
strictness: 0.95
steps:
  - id: define-context
    title: "Problemi ve Bağlamı Tanımla"
    mandatory: true
    aliases: ["defined the problem", "defined the context", "set the scope"]
    checks: ["context", "problem", "scope"]
  - id: research-options
    title: "Seçenekleri Araştır (En Az 3 Alternatif)"
    mandatory: true
    depends_on: [define-context]
    aliases: ["evaluated options", "researched alternatives", "considered alternatives"]
    checks: ["option", "alternative", "compare"]
  - id: evaluate
    title: "Her Seçeneği Değerlendir (MECE)"
    mandatory: true
    depends_on: [research-options]
    aliases: ["compared tradeoffs", "weighed tradeoffs", "evaluated tradeoffs"]
    checks: ["trade-off", "benefit", "risk"]
  - id: decide
    title: "Karar Ver ve Gerekçelendir"
    mandatory: true
    depends_on: [evaluate]
    aliases: ["chose an approach", "made the decision", "selected the approach"]
    checks: ["decision", "selected"]
  - id: write-adr
    title: "ADR Belgesini Yaz (docs/adr/)"
    mandatory: true
    depends_on: [decide]
    aliases: ["documented the adr", "wrote the adr", "recorded the adr"]
    checks: ["ADR", "decision"]
  - id: review-adr
    title: "ADR'yi Takımla Birlikte İncele"
    mandatory: true
    depends_on: [write-adr]
    aliases: ["reviewed it with the team", "shared the adr for review", "team reviewed the adr"]
    checks: ["review", "team"]
  - id: implement
    title: "Kararı Kod ve Dokümantasyona Yansıt"
    mandatory: true
    depends_on: [review-adr]
    aliases: ["recorded the decision", "implemented the decision", "updated docs and code"]
    checks: ["implement", "doc", "code"]
---

# Architecture Decision Process

## Purpose
Standardized process for making and documenting architectural decisions using ADRs.

## When to Write an ADR
- Any non-trivial architectural decision
- Technology or framework selection
- API design decisions
- Database schema changes
- Security architecture decisions
- Integration patterns
- NOT: trivial implementation details, bug fixes, minor refactors

## ADR Template

```markdown
# ADR-NNNN: Title

## Status
Proposed | Accepted | Deprecated | Superseded

## Context
What is the problem? What constraints exist? What is the current situation?

## Decision
What is the decision? Why was it chosen over alternatives?

## Consequences
What are the trade-offs? What becomes easier/harder? What must be done?

## Compliance
How will this decision be enforced? (lint rules, CI checks, code reviews)
```

## ADR Lifecycle

```
Proposed → Accepted → (later) Deprecated → Superseded
              ↓
        (action taken)
```

- **Proposed:** Under review by the team
- **Accepted:** Decision is final, implementation can proceed
- **Deprecated:** No longer recommended but still used
- **Superseded:** Replaced by a newer ADR

## Evaluation Criteria
- Development cost (initial implementation time)
- Operational cost (infrastructure, maintenance)
- Learning curve for the team
- Ecosystem maturity and community support
- License compatibility
- Scalability characteristics
- Security posture
