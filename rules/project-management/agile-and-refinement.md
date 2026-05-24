# Agile Practices & Backlog Refinement

## Core Principle

> *Deliver value iteratively. Refine continuously. The backlog is a living artifact, not a wishlist.*

Agile is about responding to change over following a plan. Backlog refinement ensures the team always has a clear, actionable set of work ready for upcoming sprints. These rules define how we run agile ceremonies and keep the backlog healthy.

---

## 1. Sprint Cadence & Ceremonies

### Rules

- [ ] Sprints are **two weeks** long (Mon–Fri of alternating weeks).
- [ ] All ceremonies start **on time** and have a **hard timebox**.
- [ ] Ceremonies are held **regardless of attendance** — no single person blocks the team's rhythm.
- [ ] Ceremony times are **published in the team calendar** and changed only by team consent.

### Ceremony Schedule

| Ceremony | Duration | When | Purpose |
|----------|----------|------|---------|
| **Sprint Planning** | 60 min | First day of sprint | Commit to sprint backlog; define sprint goal |
| **Daily Standup** | 15 min | Every morning | Sync on progress, blockers, next steps |
| **Backlog Refinement** | 30 min | Mid-sprint (Day 5) | Groom, estimate, and split upcoming items |
| **Sprint Review** | 30 min | Last day of sprint | Demo completed work to stakeholders |
| **Retrospective** | 45 min | Last day of sprint | Inspect and adapt team process |

### Timebox Discipline

```
┌──────────────────────────────────────────────────────┐
│  Sprint Planning (60m)   │ Review (30m) │ Retro (45m)│
├──────────────────────────┴──────────────┴────────────┤
│  Day 1                                  Day 10       │
└──────────────────────────────────────────────────────┘
         ▲ Refinement (30m) on Day 5
         │ Daily Standup (15m) every morning
```

---

## 2. Sprint Planning

### Rules

- [ ] The **Product Owner** presents the top-priority backlog items with clear acceptance criteria.
- [ ] The **team** collectively selects items they can commit to for the sprint.
- [ ] Every sprint MUST have a **single, measurable Sprint Goal**.
- [ ] Planned capacity = (number of developers × available days) − (meetings, PTO, support).
- [ ] No item enters the sprint without an **estimate** and **acceptance criteria**.
- [ ] Unplanned work (bugs, hotfixes) is **tracked and deducted** from sprint capacity.

### Sprint Goal Template

```markdown
## Sprint Goal
<one-line statement of what this sprint aims to achieve>

## Scope
- [Feature A] — <brief description>
- [Feature B] — <brief description>
- [Bug fixes] — <brief description>

## Out of Scope
- Things deliberately deferred to next sprint

## Risks
- Known dependencies or uncertainties
```

### Planning Checklist

- [ ] Sprint goal drafted and agreed?
- [ ] All selected items have estimates?
- [ ] Acceptance criteria are clear?
- [ ] Capacity allocated for support/maintenance?
- [ ] Dependencies identified and tracked?

---

## 3. Daily Standup

### Rules

- [ ] Standup starts **at the same time and place** every working day.
- [ ] Each person answers **three questions**:
  1. What did I do yesterday that helped us meet the sprint goal?
  2. What will I do today to help us meet the sprint goal?
  3. Do I see any blockers or impediments?
- [ ] Standup is **not a status report to management** — it's a peer sync.
- [ ] Side conversations are **taken offline** immediately.
- [ ] The standup is **not the place to solve problems** — only to identify them.

### After Standup Flow

```
Standup ──→ Blockers identified? ──Yes──→ Create follow-up thread/ticket
   │                                      │
   │                                      ▼
   │                               Assign owner + deadline
   │
   └──No──→ Continue with planned work
```

### Standup Etiquette

| Do | Don't |
|----|-------|
| Stay concise — 1–2 minutes per person | Deep-dive into technical details |
| Mention blockers explicitly | Say "nothing" or "same as yesterday" |
| Listen to teammates | Interrupt or multitask |
| Offer help if someone is blocked | Assume someone else will fix it |

---

## 4. Backlog Refinement

### Rules

- [ ] Refinement happens **at least once per sprint** (mid-sprint).
- [ ] The backlog is **kept at 2–3 sprints' worth of refined work**.
- [ ] User stories follow the **INVEST** principle:
  - **I**ndependent — can be delivered in any order
  - **N**egotiable — details emerge through conversation
  - **V**aluable — delivers concrete value to users
  - **E**stimable — team can size it
  - **S**mall — fits within one sprint
  - **T**estable — has clear pass/fail criteria
- [ ] Items older than **3 sprints without activity** are reviewed for closure or archival.
- [ ] Each backlog item MUST have:
  - A clear **title** (imperative: "As a... I want... So that...")
  - **Acceptance criteria** (given/when/then or checklist format)
  - A **size estimate** (story points or t-shirt size)
  - **Labels** for type (bug, feature, tech-debt, chore)

### User Story Format

```markdown
**As a** <role>
**I want** <feature/behavior>
**So that** <benefit/value>

**Acceptance Criteria**
- [ ] Given <context>, when <action>, then <expected outcome>
- [ ] Given <context>, when <action>, then <expected outcome>

**Technical Notes**
- <implementation hints, architectural decisions>

**Estimate:** <points>
**Labels:** <type>
```

### Splitting Large Stories

| Technique | Example |
|-----------|---------|
| **Vertical slice** | Cut by workflow step (login → search → checkout) |
| **Happy path vs. edge cases** | Ship main flow first, error handling later |
| **UI vs. API** | Backend endpoints first, frontend integration second |
| **Business rule variants** | One rule per story |
| **Performance vs. functionality** | Correct first, fast later |

### Refinement Checklist

- [ ] Is the story **independent** of other items in the sprint?
- [ ] Can the team **estimate** it confidently?
- [ ] Is it **small enough** to complete in one sprint?
- [ ] Are **acceptance criteria** unambiguous?
- [ ] Are **dependencies** documented?
- [ ] Do we need a **spike/experiment** to reduce uncertainty?

---

## 5. Estimation

### Rules

- [ ] Use **relative sizing** (story points) — not time-based estimates.
- [ ] Fibonacci sequence: **1, 2, 3, 5, 8, 13, 21** (or t-shirt sizes: XS, S, M, L, XL).
- [ ] Items larger than **13 points** MUST be split.
- [ ] Items < 1 point are tasks, not stories (use hours or checklist).
- [ ] The **whole team** participates in estimation.
- [ ] Estimation is **not a commitment** — it's a forecast.
- [ ] **Planning Poker** is the default technique — everyone votes simultaneously.

### Estimation Guidelines

| Points | Size | Confidence | Typical Effort |
|--------|------|------------|----------------|
| 1 | Trivial | Very high | < 2 hours |
| 2 | Small | High | Half day |
| 3 | Medium | High | 1 day |
| 5 | Large | Medium | 2–3 days |
| 8 | Very large | Medium | 3–5 days |
| 13 | X-large | Low | 5–10 days (split!) |
| 21 | Too big | Very low | Must split |

### Estimation Anti-Patterns

| Anti-Pattern | Why It's Harmful |
|--------------|------------------|
| Anchoring (someone says a number first) | Biases the team; always vote in parallel |
| Debating hours vs. points | Points are relative, not clock-based |
| Estimating perfection | Estimate for a reasonable implementation, not gold-plating |
| Adding padding | Points should reflect complexity, not fear |
| Comparing velocity across teams | Velocity is team-specific, not a benchmark |

---

## 6. Sprint Review

### Rules

- [ ] Demo **working, tested software** — not slides or prototypes (unless for feedback).
- [ ] Focus on **what was accomplished** against the sprint goal.
- [ ] Stakeholders **ask questions and give feedback** — this is not a lecture.
- [ ] Update the backlog based on stakeholder feedback during or immediately after review.
- [ ] If a story is not done, **it is not demoed** — it goes back to the backlog.

### Review Agenda

```
1. Sprint Goal recap (2 min)
2. Demo completed stories (20 min)
3. Stakeholder Q&A / feedback (5 min)
4. Backlog adjustments based on feedback (3 min)
```

---

## 7. Definition of Done (DoD)

### Rules

- [ ] The DoD is **shared and agreed** by the whole team.
- [ ] No story is considered "Done" until all DoD criteria are met.
- [ ] The DoD applies to **every** backlog item — feature, bug, tech-debt, chore.

### Standard Definition of Done

- [ ] Code written and reviewed (at least one approval)
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing (where applicable)
- [ ] No regressions in existing tests
- [ ] Documentation updated (if applicable)
- [ ] Feature flagged or safely deployable
- [ ] Deployed to staging environment
- [ ] Product Owner has accepted the story

---

## 8. Velocity & Forecasting

### Rules

- [ ] Velocity is the **sum of points completed** over the last 3–5 sprints (moving average).
- [ ] Use velocity for **forecasting**, not for performance evaluation.
- [ ] If velocity drops >20% from average, **investigate root cause** (technical debt, team churn, scope creep).
- [ ] Re-forecast at sprint boundaries — never mid-sprint.

### Velocity Tracking

```python
# Example: moving average of last 3 sprints
velocities = [32, 28, 35]
avg_velocity = sum(velocities) / len(velocities)  # 31.7

# Forecast: items up to ~32 points per sprint
```

---

## References

- [Scrum Guide](https://scrumguides.org/)
- [INVEST — Bill Wake](https://xp123.com/articles/invest-in-good-stories-and-story-tasks/)
- [Planning Poker — Mountain Goat Software](https://www.mountaingoatsoftware.com/agile/planning-poker)
- [User Story Mapping — Jeff Patton](https://www.jpattonassociates.com/user-story-mapping/)
- [Definition of Done — Scrum.org](https://www.scrum.org/resources/definition-done)
