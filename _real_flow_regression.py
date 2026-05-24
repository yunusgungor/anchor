#!/usr/bin/env python3
"""Real-flow regression suite using actual workflow rules.

Amaç:
- Gerçek workflow rule dosyaları ile gerçek anlatım senaryolarını test etmek
- False-positive / aşırı strictlik regresyonlarını metrik bazlı kilitlemek
"""

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, 'src')
os.environ['ANCHOR_RULES_DIR'] = '/workspace/anchor/rules'

from anchor.engine import AnchorEngine

TMP = Path('/tmp/anchor-real-flow-regression')
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)


def build_engine():
    eng = AnchorEngine('/workspace/anchor/rules', str(TMP / 'index'))
    eng.build()
    return eng


def run(engine, query, output):
    r = engine.process(query, output)
    return {
        'rules': r.rules_activated,
        'corr': len(r.corrections),
        'viol': len(r.step_violations),
    }


def check(label, ok):
    icon = 'PASS' if ok else 'FAIL'
    print(f'[{icon}] {label}')
    return ok


engine = build_engine()
results = []

incident_full = run(engine, 'incident', 'We detected the production incident, assessed severity, communicated to stakeholders, rolled back to mitigate, verified recovery, restored service, implemented a permanent fix, and wrote a postmortem with action items.')
results.append(check('incident full -> incident-response active', 'incident-response' in incident_full['rules']))
results.append(check('incident full -> violations <= 8', incident_full['viol'] <= 8))

review_full = run(engine, 'review', 'Reviewed the PR, checked business logic, reviewed security implications, validated test coverage, requested a small change, then approved after the update.')
results.append(check('review full -> code-review active', 'code-review' in review_full['rules']))
results.append(check('review full -> violations <= 6', review_full['viol'] <= 6))

release_full = run(engine, 'release', 'We bumped the version, updated release notes, tagged the release, built the artifact, deployed to staging, validated smoke checks, got approval, deployed to production, and monitored the rollout.')
results.append(check('release full -> release-process active', 'release-process' in release_full['rules']))
results.append(check('release full -> violations <= 10', release_full['viol'] <= 10))

tdd_full = run(engine, 'tdd', 'Started with a failing test in the red phase, confirmed it fails, wrote minimal code in the green phase, confirmed the test passes, refactored to simplify the design, and moved to the next test.')
results.append(check('tdd full -> tdd active', 'tdd-cycle' in tdd_full['rules']))
results.append(check('tdd full -> violations <= 5', tdd_full['viol'] <= 5))

story_full = run(engine, 'story-impl', 'Read the story and acceptance criteria, created a test plan, implemented the feature, wrote tests, ran validation, opened a PR, and updated the story notes.')
results.append(check('story full -> story active', 'story-implementation' in story_full['rules']))
results.append(check('story full -> violations <= 7', story_full['viol'] <= 7))

mixed = run(engine, '', 'A production incident happened, we rolled back, reviewed the PR for the hotfix, updated release notes, deployed again, and then monitored the rollout.')
results.append(check('mixed output -> max 2 workflow rules active', len(mixed['rules']) <= 2))

passed = sum(1 for x in results if x)
total = len(results)
print(f'\nSUMMARY: {passed}/{total} passed')
if passed != total:
    raise SystemExit(1)
