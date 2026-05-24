# Retrospectives

## Core Principle

> *Inspect and adapt. The retrospective is the team's most important ceremony — without it, we repeat mistakes and miss improvements.*

A retrospective is a structured opportunity for the team to examine its own process, celebrate wins, identify areas for improvement, and commit to concrete action. These rules define how we run retrospectives so they remain safe, productive, and actionable.

---

## 1. Retrospective Cadence & Structure

### Rules

- [ ] Retrospectives are held **at the end of every sprint** (last day).
- [ ] Duration is **45 minutes** — strictly timeboxed.
- [ ] Attendance is **mandatory for all team members** (developers, QA, PO, SM).
- [ ] The retrospective is a **safe space** — no blame, no judgment, no retaliation.
- [ ] The facilitator rotates among team members each sprint.

### Retrospective Phases

```
┌──────────────────────────────────────────────────────────┐
│                   45-MINUTE RETRO                        │
├────────────┬───────────┬─────────────┬───────────────────┤
│  Set the   │  Gather   │  Generate   │  Commit to        │
│  Stage     │  Data     │  Insights   │  Action           │
│  (5 min)   │  (15 min) │  (15 min)   │  (10 min)         │
└────────────┴───────────┴─────────────┴───────────────────┘
```

- **Set the Stage** — Establish psychological safety, review the agenda
- **Gather Data** — Share facts and feelings about the sprint
- **Generate Insights** — Find root causes and patterns
- **Commit to Action** — Define 1–3 actionable experiments for next sprint

---

## 2. Psychological Safety

### Rules

- [ ] The **Prime Directive** is read aloud at the start of every retrospective:

  > *"Regardless of what we discover, we understand and truly believe that everyone did the best job they could, given what they knew at the time, their skills and abilities, the resources available, and the situation at hand."*

  — Norm Kerth, *Project Retrospectives*

- [ ] Blame and personal attacks are **not tolerated**.
- [ ] Focus on **process and system** issues, not individuals.
- [ ] Leaders (managers, tech leads) must be **especially careful not to dominate** the conversation.
- [ ] Anyone can call a **safety check** ("I'm feeling unsafe with this conversation") — conversation stops immediately.

### Safety Norms

| Practice | Description |
|----------|-------------|
| **Assume good intent** | Everyone wants the project to succeed |
| **Attack the problem** | Focus on what happened, not who did it |
| **No fixing during data gathering** | Listen first, solutions later |
| **Equal airtime** | Use talking stick, round-robin, or silent writing |
| **Confidentiality** | What's said in retro stays in retro (unless agreed otherwise) |

---

## 3. Retrospective Formats

### Rules

- [ ] Rotate formats frequently to prevent "retro fatigue."
- [ ] Choose a format that fits the **team's current state** (new team, conflict, smooth sailing, post-incident).
- [ ] The facilitator selects the format before the retro begins.

### Recommended Formats

| Format | Best For | Description |
|--------|----------|-------------|
| **Start / Stop / Continue** | General-purpose, fast | What should we start doing? Stop doing? Keep doing? |
| **Mad / Sad / Glad** | Emotional safety | Sort items by emotional sentiment |
| **4Ls** | Structured analysis | Loved, Learned, Lacked, Longed For |
| **Sailboat** | Visual / metaphorical | Wind (what pushes us forward), Anchor (what holds us back), Rocks (risks), Island (goal) |
| **Timeline** | Complex sprints with many events | Plot events on a timeline, discuss emotional highs/lows |
| **Glad / Sad / Mad** 🧪 | Remote teams | Virtual board with sticky notes per column |

### Start / Stop / Continue Template

```markdown
## Start Doing
- <thing we should begin doing>
- <thing we should begin doing>

## Stop Doing
- <thing we should stop doing>
- <thing we should stop doing>

## Continue Doing
- <thing we should keep doing>
- <thing we should keep doing>

## Action Items
- [ ] <action item> — Owner: @name — Due: <date>
```

### Sailboat Retro Template

```markdown
## 🌊 Sailboat Retro

### 🏝️ Goal (what we're aiming for)
- <sprint goal / team vision>

### 🌬️ Wind (what's pushing us forward)
- <good things, tailwinds, successes>

### ⚓ Anchor (what's holding us back)
- <impediments, blockers, recurring issues>

### 🪨 Rocks (risks ahead)
- <upcoming risks, dependencies, threats>

### Action Items
- [ ] <action item> — Owner: @name — Due: <date>
```

---

## 4. Action Items & Follow-Through

### Rules

- [ ] Every retrospective MUST produce **1–3 concrete action items**.
- [ ] Each action item MUST have:
  - A specific, measurable **owner**
  - A **deadline** (within the next sprint)
  - A clear **definition of done**
- [ ] Action items are tracked **visibly** (board, wiki, or team chat pinned post).
- [ ] The next sprint's retrospective **opens by reviewing previous action items**.
- [ ] An action item that's not completed after two sprints is **escalated or abandoned**.

### Action Item Quality

| Poor (likely to fail) | Good (likely to succeed) |
|------------------------|--------------------------|
| "Improve testing" | "Add pre-commit hook for lint + test run by end of sprint" |
| "Communicate better" | "Post daily standup summary in Slack by 10am" |
| "Fix CI pipeline" | "Dedicate 2 hours on Wednesday to reduce CI time from 12m to under 5m" |
| "No owner" | "Owned by @alice, review by Friday" |

### Action Item Tracking

```markdown
## 🎯 Retro Action Items — Sprint N

| # | Action | Owner | Due | Status |
|---|--------|-------|-----|--------|
| 1 | Add pre-commit lint hook | @bob | Sprint N+1, Day 3 | 🔴 Not started |
| 2 | Reduce CI build time < 5 min | @alice | Sprint N+1, Day 10 | 🟡 In progress |
| 3 | Update onboarding docs | @charlie | Sprint N+1, Day 5 | 🟢 Done |
```

---

## 5. Data Gathering Techniques

### Rules

- [ ] Use **silent writing** (5 minutes) before discussion to avoid groupthink.
- [ ] Data comes from **multiple sources**: team members, metrics, incident reports.
- [ ] Rely on **specific examples**, not vague impressions.

### Quantitative Metrics to Consider

| Metric | What It Reveals |
|--------|-----------------|
| **Velocity trend** | Sustained drops may indicate process issues |
| **Cycle time** | How long from start to completion |
| **Bug count / density** | Quality concerns in the sprint |
| **CI pass rate** | Test stability and infrastructure health |
| **Escaped defects** | Gaps in QA process |
| **Deployment frequency** | Process friction in releases |

### Data Gathering Prompts

```markdown
### Sprint Data — Sprint N

**What went well?**
- <specific example>
- <specific example>

**What could be improved?**
- <specific example>
- <specific example>

**What surprised us?**
- <specific example>

**Metrics snapshot:**
- Velocity: <N> (prev: <M>)
- Bugs reported: <N>
- CI pass rate: <N>%
```

---

## 6. Common Anti-Patterns

| Anti-Pattern | Why It's Harmful | Fix |
|--------------|------------------|-----|
| **No action items** | Retro becomes a venting session with no outcome | End every retro with 1–3 commitments |
| **Same action items every sprint** | Nothing changes; team becomes cynical | Escalate or drop stale items; try different format |
| **Too many action items** | None get done; team feels overwhelmed | Limit to 1–3; focus on high-impact changes |
| **Manager dominates** | Psychological safety collapses | Use round-robin or anonymous tools |
| **Skipping retro due to "no time"** | Small problems compound into big ones | Timebox strictly; even 15 min is better than 0 |
| **Focusing only on negatives** | Demoralizing; misses what works | Start with "what went well" at every retro |
| **Fixing during data gathering** | Shuts down exploration; jumps to solutions | Enforce "no solutions" during gather phase |

---

## 7. Remote Retrospectives

### Rules

- [ ] Use a **shared digital board** (Miro, Mural, or equivalent).
- [ ] **Everyone writes simultaneously** — no waiting for turns.
- [ ] Use **anonymous voting** for sensitive topics.
- [ ] Cameras **on** is encouraged but not required.
- [ ] A **dedicated facilitator** is even more important remotely.
- [ ] Record a brief **summary / action items** for absent team members.

### Remote Retro Flow

```
1. Tool setup + norms reminder (2 min)
2. Silent writing on digital board (5 min)
3. Cluster and discuss (15 min)
4. Vote on top issues (5 min)
5. Action items + ownership (10 min)
6. Close + retro check (3 min)
```

### Recommended Tools

| Tool | Strengths |
|------|-----------|
| **Miro / Mural** | Rich templates, real-time collaboration |
| **Google Jamboard** | Simple, free, GSuite integrated |
| **FunRetro** | Purpose-built for retros, lightweight |
| **Notion / Confluence** | Document-centric, good for async retros |

---

## 8. Follow-Up & Accountability

### Rules

- [ ] Action items are **added to the sprint backlog** and tracked like any other work.
- [ ] The **Scrum Master or facilitator** checks action item status mid-sprint.
- [ ] Completed action items are **celebrated** — recognize effort.
- [ ] Action items that didn't help are **openly discussed** and dropped without blame.

### Between Sprints

```
Retro ──→ Action items created
  │
  ├──→ Added to sprint backlog
  │
  ├──→ Mid-sprint check by SM
  │
  ├──→ Completed → Celebrate 🎉
  │
  └──→ Not completed → Review at next retro
         → Either: recommit, escalate, or drop
```

---

## 9. Experimentation Culture

### Rules

- [ ] Treat action items as **experiments** — not mandates.
- [ ] Each experiment has a **clear hypothesis**: "If we do X, we expect Y to improve."
- [ ] If an experiment fails, **that's data, not a failure** — learn and try something else.
- [ ] Teams should aim to **run at least one process experiment per sprint**.

### Experiment Format

```markdown
## Experiment Card

**Hypothesis**
If we <change>, then <expected outcome>.

**Measure**
- <metric 1>
- <metric 2>

**Duration**
1 sprint (Sprint N+1)

**Success Criteria**
- <metric 1> improves by <N>%
- Team votes to continue the practice

**Result (review next retro)**
- <what happened>
- <keep / adapt / drop>
```

---

## References

- Norm Kerth, *Project Retrospectives: A Primer for Successful Retros*
- Esther Derby & Diana Larsen, *Agile Retrospectives: Making Good Teams Great*
- [Retrospective Wiki (Agile Alliance)](https://www.agilealliance.org/glossary/retrospective/)
- [FunRetro — Remote Retro Tool](https://funretro.io/)
- [Prime Directive — Norm Kerth](https://www.retrospectives.com/pages/primeDirective.html)
