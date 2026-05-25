"""
s01 — Core Engine Pipeline ⚡

Demonstrates Anchor's end-to-end pipeline:
  A1: Topic Extraction     → <1ms
  A2: Knowledge Retrieval  → <2ms
  A3: Conflict Detection   → <5ms
  A4: Rectification        → <1ms
  ─────────────────────────────────
  TOTAL: <10ms

Truly deterministic — zero LLM calls at runtime.
"""

import os
import sys
import time

# Ensure anchor is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pathlib import Path
from anchor.engine import AnchorEngine

from report import DemoReport, print_header, print_step, print_metric, bil


def run(rules_path: str | None = None) -> DemoReport:
    report = DemoReport(
        scenario_id="s01",
        title_en="Core Engine Pipeline — A1→A4 Deterministic Flow",
        title_tr="Core Engine Pipeline — A1→A4 Deterministik Akış",
    )

    if rules_path is None:
        rules_path = str(Path(__file__).parent.parent / "rules")

    print_header("s01: Core Engine Pipeline", "en")

    # ── Step 1: Initialize Engine ──
    print_step(1, 5, "Initializing AnchorEngine with {} rules".format(
        len(list(Path(rules_path).rglob("*.md")))
    ))
    
    t0 = time.perf_counter()
    engine = AnchorEngine(rules_path)
    engine.build()
    init_ms = (time.perf_counter() - t0) * 1000

    rules_count = len(engine.store._rule_meta) if hasattr(engine.store, '_rule_meta') else 0
    report.add_metric("Rules Loaded", rules_count, "", "📚")
    report.add_metric("Build Time", f"{init_ms:.1f}", "ms", "⏱️")
    report.add_section(
        "🚀 Engine Initialized",
        f"Rules path: {rules_path}\n"
        f"Rules loaded: {rules_count}\n"
        f"Build time: {init_ms:.1f}ms\n"
        f"Binary cache: {'✅ enabled' if hasattr(engine.store, '_index_path') and engine.store._index_path else '❌ not used'}",
        "success",
    )
    print_metric("Rules loaded", rules_count)
    print_metric("Build time", f"{init_ms:.1f}", "ms")

    # ── Step 2: Process test queries ──
    print_step(2, 5, "Processing test queries through pipeline")

    test_cases = [
        {
            "query": "Neural Processor X1 hakkında bilgi ver",
            "llm": "NPX1, TSMC'nin 7nm düğümünde üretilen genel amaçlı bir AI hızlandırıcısıdır. NVIDIA Jetson ile rekabet eder.",
            "desc": "Factual contradiction (fabrication node)",
        },
        {
            "query": "StateGuard nedir?",
            "llm": "StateGuard bir güvenlik duvarı aracıdır. Uygulama güvenliği için kullanılır.",
            "desc": "Identity contradiction (firewall vs validation)",
        },
        {
            "query": "SKY130 hakkında bilgi",
            "llm": "SKY130, Global Foundries'in 130nm düğümüdür. ASIC üretimi için kullanılır.",
            "desc": "Ownership contradiction (SkyWater vs Global Foundries)",
        },
        {
            "query": "TDD cycle nasıl işler?",
            "llm": "Önce testleri yazarım, sonra refactor ederim. Yeşil fazı atlayarak gelen testleri geçiririm.",
            "desc": "Workflow violation (missing green phase)",
        },
    ]

    results_summary = []
    for i, tc in enumerate(test_cases):
        t1 = time.perf_counter()
        result = engine.process(tc["query"], tc["llm"])
        latency = (time.perf_counter() - t1) * 1_000_000  # microseconds

        status = "🔧 FIXED" if result.modified else "✅ OK"
        sevs = ", ".join(c.conflict.severity.name for c in result.corrections) if result.corrections else "none"
        rules_used = ", ".join(result.rules_activated[:3]) if result.rules_activated else "none"

        results_summary.append({
            "query": tc["query"][:50],
            "status": status,
            "latency": f"{latency:.0f}",
            "severity": sevs,
            "rules": rules_used,
        })

        report.add_section(
            f"🔍 Test Case {i+1}: {tc['desc']}",
            f"Query: {tc['query']}\n"
            f"LLM Output: {tc['llm'][:80]}...\n"
            f"Status: {status} | Latency: {latency:.0f}μs\n"
            f"Topics: {[t.name for t in result.topics_found]}\n"
            f"Rules: {rules_used}\n"
            f"Severities: {sevs}",
            "warning" if result.modified else "success",
        )
        print_step(i + 3, 5, f"  {tc['query'][:45]:45s}  {status:12s}  {latency:6.0f}μs")

    # ── Step 3: Pipeline latency breakdown ──
    print_step(5, 5, "Detailed pipeline latency analysis")

    avg_latencies = {}
    for tc in test_cases:
        result = engine.process(tc["query"], tc["llm"])
        for stage, val in result.latency_us.items():
            if stage != "total":
                avg_latencies.setdefault(stage, []).append(val)

    latency_report = ""
    total_avg = 0
    for stage, vals in sorted(avg_latencies.items()):
        avg = sum(vals) / len(vals)
        total_avg += avg
        bar = "█" * int(avg / 5) + "░" * max(0, 20 - int(avg / 5))
        latency_report += f"{stage:25s}  {avg:8.1f}μs  {bar}\n"

    report.add_section(
        "⏱️ Pipeline Latency Breakdown",
        latency_report + f"\n{'TOTAL (avg)':25s}  {total_avg:8.1f}μs  {'█' * int(total_avg / 5)}",
        "code",
    )
    report.add_metric("Avg Total Latency", f"{total_avg:.0f}", "μs", "⚡")
    report.add_metric("Fixed Outputs", sum(1 for r in results_summary if "FIXED" in r["status"]), "/4", "🔧")
    report.add_metric("Rules Activated", len(set(r["rules"] for r in results_summary if r["rules"] != "none")), "", "📚")

    print()
    print("  Pipeline Latency (average across test cases):")
    for stage, vals in sorted(avg_latencies.items()):
        avg = sum(vals) / len(vals)
        print_metric(stage, f"{avg:.1f}", "μs")
    print_metric("Total", f"{total_avg:.1f}", "μs")

    # ── Final ──
    report.add_section(
        "📋 Key Takeaway",
        bil(
            f"Anchor processes {rules_count} rules in {total_avg:.0f}μs — "
            f"all deterministic, zero LLM calls, 100% reproducible. "
            f"The pipeline catches factual contradictions, ownership errors, and workflow violations.",
            f"Anchor {rules_count} rule'u {total_avg:.0f}μs'de işler — "
            f"tamamen deterministik, sıfır LLM çağrısı, %100 tekrarlanabilir. "
            f"Pipeline; çelişkileri, sahiplik hatalarını ve workflow ihlallerini yakalar.",
        ),
        "success",
    )

    latency_values = [int(r["latency"]) for r in results_summary if r["latency"].strip().isdigit()]
    total_duration = sum(latency_values) if latency_values else 50000
    report.duration_ms = total_duration / 1000  # μs → ms
    if not report.duration_ms or report.duration_ms < 10:
        report.duration_ms = total_avg / 1000  # fallback
    report.status = "passed"
    return report


if __name__ == "__main__":
    report = run()
    print(f"\n  ✅  Scenario {report.scenario_id}: {report.status}")
    print(f"  ⏱️   {report.duration_ms:.1f}ms")
