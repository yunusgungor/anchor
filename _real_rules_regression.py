#!/usr/bin/env python3
"""Real rules regression test for workflow matching improvements."""

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, 'src')
os.environ['ANCHOR_RULES_DIR'] = '/workspace/anchor/rules'

from anchor.engine import AnchorEngine

TMP = Path('/tmp/anchor-real-rules-regression')
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)


def build_engine():
    eng = AnchorEngine('/workspace/anchor/rules', str(TMP / 'index'))
    eng.build()
    return eng


def run_case(engine, name, query, output):
    result = engine.process(query, output)
    return {
        'name': name,
        'rules': result.rules_activated,
        'corrections': len(result.corrections),
        'step_violations': len(result.step_violations),
        'messages': [c.conflict.llm_claim for c in result.corrections[:5]],
    }


engine = build_engine()
results = []

results.append(run_case(
    engine,
    'code_review_alias_pr',
    'review',
    'Reviewed the PR, checked business logic, reviewed security implications, validated tests, and approved the changes.'
))

results.append(run_case(
    engine,
    'incident_postmortem_alias',
    'incident',
    'We detected the incident, assessed severity, mitigated with rollback, verified recovery, restored service, and wrote a postmortem with action items.'
))

results.append(run_case(
    engine,
    'tdd_term_map',
    'tdd',
    'Started with a failing test in the red phase, wrote minimal code to make it pass in the green phase, then refactored to eliminate duplication.'
))

results.append(run_case(
    engine,
    'output_based_capped',
    '',
    'Detected a production incident, rolled back, wrote tests, reviewed the PR, updated release notes, and deployed again.'
))

passes = 0
checks = []

r1 = results[0]
checks.append(('code_review_alias_pr activates code-review', 'code-review' in r1['rules']))
checks.append(('code_review_alias_pr has <= 6 step violations', r1['step_violations'] <= 6))

r2 = results[1]
checks.append(('incident_postmortem_alias activates incident-response', 'incident-response' in r2['rules']))
checks.append(('incident_postmortem_alias includes postmortem text handling', r2['corrections'] >= 1))

r3 = results[2]
checks.append(('tdd_term_map activates tdd-cycle', 'tdd-cycle' in r3['rules']))
checks.append(('tdd_term_map picks up red/green/refactor semantics', r3['corrections'] >= 1))

r4 = results[3]
checks.append(('output_based_capped keeps <= 3 rules', len(r4['rules']) <= 3))
checks.append(('output_based_capped keeps >= 1 rule', len(r4['rules']) >= 1))

for _, ok in checks:
    if ok:
        passes += 1

print('============================================================')
print('ANCHOR v4.4.2 — REAL RULES REGRESSION TEST')
print('============================================================')
for r in results:
    print(f"{r['name']:<28} rules={r['rules']} corr={r['corrections']} step_viol={r['step_violations']}")
    for msg in r['messages'][:2]:
        print(f"  - {msg[:120]}")
print('------------------------------------------------------------')
for name, ok in checks:
    print(('✅' if ok else '❌'), name)
print('------------------------------------------------------------')
print(f'PASS: {passes}/{len(checks)}')
if passes != len(checks):
    raise SystemExit(1)
