---
topic: "Production Incident Response"
aliases: ["incident-response", "on-call", "sev-handling", "incident-management", "pager-duty", "incident response", "production incident", "outage"]
tags: [workflow, incident, devops, reliability, sre, production]
priority: 10
strictness: 0.95
steps:
  - id: detect
    title: "İhlali Tespit Et ve Bildir"
    mandatory: true
    aliases: ["detected the production incident", "incident happened", "outage occurred"]
    checks: ["alert", "monitor", "error", "on-call", "incident", "pager"]
  - id: assess
    title: "Etkiyi ve Şiddeti Değerlendir (SEV)"
    mandatory: true
    depends_on: [detect]
    checks: ["SEV1", "SEV2", "SEV3", "impact", "affected", "severity"]
  - id: mitigate
    title: "Etkiyi Azalt (Rollback/Hotfix/Feature Flag)"
    mandatory: true
    depends_on: [assess]
    aliases: ["rolled back the deployment", "isolated the affected service", "reverted the change", "rolled back"]
    checks: ["rollback", "hotfix", "flag", "mitigate", "stop bleed", "revert"]
  - id: verify-mitigation
    title: "Mitigasyonu Doğrula (Monitoring)"
    mandatory: true
    depends_on: [mitigate]
    aliases: ["resolved the issue", "after stabilization", "the fix is verified", "restored the previous version"]
    checks: ["health", "monitor", "error rate", "recovery", "dashboard"]
  - id: communicate
    title: "Paydaşlara Durumu Bildir"
    mandatory: true
    depends_on: [verify-mitigation]
    aliases: ["communicated the status", "sent an update", "documented the incident", "documented everything"]
    checks: ["status", "update", "stakeholder", "communication", "post"]
  - id: root-cause
    title: "Kök Neden Analizi Yap"
    mandatory: true
    depends_on: [communicate]
    checks: ["5 whys", "root cause", "timeline", "evidence", "kök neden"]
  - id: fix-permanent
    title: "Kalıcı Çözümü Uygula"
    mandatory: true
    depends_on: [root-cause]
    checks: ["fix", "deploy", "patch", "resolve", "permanent"]
  - id: postmortem
    title: "Postmortem Yaz ve Önlem Al"
    mandatory: true
    depends_on: [fix-permanent]
    checks: ["postmortem", "action item", "prevent", "blameless", "retro"]
---

# Production Incident Response

## Purpose
Standardized process for detecting, mitigating, and learning from production incidents.

## Severity Levels

| Level | Definition | Response | Update Frequency |
|-------|-----------|----------|-----------------|
| **SEV1** | Complete service outage or data loss | Immediate, all hands | Every 30 min |
| **SEV2** | Major feature degradation, partial outage | < 15 min | Every 1 hour |
| **SEV3** | Minor issue, no customer impact | < 1 hour | Every 2 hours |

## Key Principles

1. **Safety first** — Mitigate before investigating root cause
2. **Transparency** — Communicate status to stakeholders regularly
3. **Blameless culture** — Focus on system improvements, not individuals
4. **Learn and improve** — Every incident leads to concrete action items

## Incident Command Structure

- **Incident Commander (IC)** — Coordinates response, makes escalation decisions
- **Communications Lead (CL)** — Handles stakeholder updates
- **Technical Lead (TL)** — Drives technical investigation and resolution
- **Scribe** — Documents timeline and decisions

## Communication Templates

### Initial Alert
```
[SEV1/SEV2/SEV3] Incident Detected: <brief description>
Impact: <what's affected>
Action: <initial response>
```

### Status Update
```
Status Update #<n> — <time since detection>
Impact: <current state>
Action: <what we're doing>
Next Update: <time>
```

### Post-Incident
```
Subject: Postmortem: <incident title>
Date: <date>
Duration: <time to resolve>
Root Cause: <summary>
Action Items: <list>
```

## Escalation Path

- **Tier 1** — On-call engineer (within 5 min)
- **Tier 2** — Senior engineer / team lead (within 15 min)
- **Tier 3** — Engineering manager / director (within 30 min)
- **Tier 4** — VP / CTO (within 1 hour)

## Postmortem Template

```markdown
# Postmortem: <Title>

**Date:** <date>
**Severity:** SEV<level>
**Duration:** <start> → <end> (<duration>)
**Incident Commander:** <name>

## Timeline
- <time> — Detection
- <time> — Assessment
- <time> — Mitigation
- <time> — Verification
- <time> — Resolution

## Root Cause
<detailed analysis>

## Impact
<users/data/revenue affected>

## Action Items
| # | Action | Owner | Due Date | Status |
|---|--------|-------|----------|--------|
| 1 | <action> | <person> | <date> | [ ] / [x] |

## Lessons Learned
- What went well
- What went wrong
- What to improve
```
