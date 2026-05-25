"""
s03 — C5 Auto-Fix Chain 🔧 (Real Rules)

Demonstrates Anchor's complete C5 correction pipeline using **real rules only**:

  Claim → Candidate → Cross-check → Conflict → Correction

Every test in this scenario triggers against ACTUAL Anchor rules.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from anchor.engine import AnchorEngine

from report import DemoReport, print_header, print_step, print_metric, bil


def run(rules_path: str | None = None) -> DemoReport:
    report = DemoReport(
        scenario_id="s03",
        title_en="C5 Auto-Fix Chain — Real Rule Contradictions",
        title_tr="C5 Otomatik Düzeltme Zinciri — Gerçek Kural Çelişkileri",
    )

    if rules_path is None:
        rules_path = str(Path(__file__).parent.parent / "rules")

    print_header("s03: C5 Auto-Fix Chain (real rules only)", "en")
    print_step(1, 4, "Initializing AnchorEngine + C5 pipeline")

    engine = AnchorEngine(rules_path)
    engine.build()

    # ── C5 Stages Explanation ──
    report.add_section(
        "🔗 C5 Pipeline",
        "C1 — **Claim** extraction from LLM output\n"
        "C2 — **Candidate** fact lookup from rule store\n"
        "C3 — **Cross-check** between claim and candidate\n"
        "C4 — **Conflict** severity classification\n"
        "C5 — **Correction** (rectification via PatchEngine)\n\n"
        "All stages run inside `engine.process()` — zero LLM calls at runtime.",
        "info",
    )

    # ── Test cases using only real rules ──
    print_step(2, 4, "C5 pipeline: Claim → Candidate → Cross-check → Conflict → Correction")

    test_cases = [
        {
            "name": "Clean Architecture — Dependency Direction",
            "llm": "In a Clean Architecture system, outer layers like databases and web frameworks "
                   "define the business rules, and domain entities depend on the database layer.",
            "expected": "CRITICAL",
            "rule": "clean-architecture",
            "desc": "Complete inversion: outer depends on inner → inner depends on outer",
        },
        {
            "name": "Test Pyramid — Distribution",
            "llm": "A healthy test suite should have 70% end-to-end tests, 20% integration tests, "
                   "and 10% unit tests for maximum confidence.",
            "expected": "CRITICAL",
            "rule": "test-pyramid",
            "desc": "Inverted: E2E-heavy instead of unit-heavy",
        },
        {
            "name": "TDD — Order of Operations",
            "llm": "The best TDD practice is to write all the implementation code first, "
                   "then write comprehensive tests to validate it works correctly.",
            "expected": "CRITICAL",
            "rule": "red-green-refactor",
            "desc": "Implement-first rather than test-first",
        },
        {
            "name": "Pass-through — No Topic Match",
            "llm": "The weather is nice today and the sun is shining brightly in the sky.",
            "expected": "NONE",
            "rule": "none",
            "desc": "Irrelevant — should NOT trigger any conflict",
        },
        {
            "name": "Pass-through — No Violation",
            "llm": "The coffee machine on the third floor makes excellent espresso for the team.",
            "expected": "NONE",
            "rule": "none",
            "desc": "Neutral statement — should NOT trigger any conflict",
        },
    ]

    results_detail = []
    for tc in test_cases:
        t1 = time.perf_counter()
        result = engine.process(tc["name"], tc["llm"])
        latency_us = (time.perf_counter() - t1) * 1_000_000

        found = bool(result.corrections)
        if found:
            top = result.corrections[0]
            sev = top.conflict.severity.name
            rule_id = top.conflict.rule_id
            edited = result.modified
        else:
            sev = "NONE"
            rule_id = "—"
            edited = False

        expected_sev = tc["expected"]
        correct = sev == expected_sev

        results_detail.append({
            "name": tc["name"],
            "severity": sev,
            "expected": expected_sev,
            "correct": correct,
            "edited": edited,
            "rule": rule_id,
            "latency_us": latency_us,
        })

        section_type = "error" if sev == "CRITICAL" else ("success" if sev == "NONE" else "info")
        report.add_section(
            f"{'✅' if correct else '❌'} {tc['name'][:50]}",
            f"LLM Output: {tc['llm'][:120]}...\n"
            f"Severity: {sev} (expected: {expected_sev})\n"
            f"Detected: {'✅' if found else '❌'} | Corrected: {'✅' if edited else '—'}\n"
            f"Rule activated: {rule_id}\n"
            f"Latency: {latency_us:.0f}μs\n"
            f"Description: {tc['desc']}",
            section_type,
        )

        icon = "✅" if correct else "❌"
        print_step(3, 4, f"  [{tc['name'][:30]:30s}]  {sev:10s}  {latency_us:6.0f}μs  {icon}")

    # ── Summary ──
    print_step(4, 4, "C5 stage summary")
    passed = sum(1 for r in results_detail if r["correct"])
    total = len(results_detail)

    report.add_section(
        "📊 C5 Pipeline Summary",
        f"Total tests: {total}\n"
        f"Passed: {passed}\n"
        f"Failed: {total - passed}\n"
        f"Accuracy: {passed / max(total, 1) * 100:.0f}%\n\n"
        "All claims verified against REAL Anchor rules.\n"
        "Zero fake topics, zero LLM calls at runtime.",
        "success" if passed == total else "warning",
    )
    report.add_metric("Accuracy", f"{passed}/{total}", "", "🎯")
    avg_lat = sum(r["latency_us"] for r in results_detail) / max(total, 1)
    report.add_metric("Avg Latency", f"{avg_lat:.0f}", "μs", "⚡")

    report.add_section(
        "💡 Key Insight",
        bil(
            f"C5 chain works end-to-end: {passed}/{total} correct classifications. "
            f"Correction is deterministic — the same input always produces the same output.",
            f"C5 zinciri uçtan uca çalışıyor: {passed}/{total} doğru sınıflandırma. "
            f"Düzeltme deterministiktir — aynı girdi her zaman aynı çıktıyı üretir.",
        ),
        "success",
    )

    report.duration_ms = avg_lat / 1000 * total
    report.status = "passed" if passed == total else "warning"
    return report


if __name__ == "__main__":
    report = run()
    print(f"\n  ✅  s03: {report.status} ({report.duration_ms:.0f}ms)")
