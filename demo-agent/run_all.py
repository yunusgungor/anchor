#!/usr/bin/env python3
"""
Anchor Demo — Comprehensive Capability Showcase 🚀

Runs all 7 scenarios and generates a beautiful HTML report.

Usage:
    python demo-agent/run_all.py              # Full run with real LLM
    python demo-agent/run_all.py --skip-llm   # Skip LLM-dependent scenarios

Output:
    demo-agent/report.html  — Interactive HTML report
    Console output          — Live progress with emoji indicators
"""

import importlib
import os
import sys
import time
from pathlib import Path

# Ensure anchor is importable
sys.path.insert(0, str(Path(__file__).parent / ".." / "src"))
sys.path.insert(0, str(Path(__file__).parent))

# ── Color / Emoji helpers ──
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def color(status: str, text: str) -> str:
    colors = {"passed": GREEN, "failed": RED, "skipped": YELLOW, "running": CYAN}
    c = colors.get(status, RESET)
    return f"{c}{text}{RESET}"


def print_banner():
    banner = f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════╗
║              ⚓  ANCHOR ENGINE DEMO  ⚓              ║
║     Comprehensive Capability Showcase — 7 Scenarios    ║
╚══════════════════════════════════════════════════════════╝{RESET}
    """
    print(banner)


def print_summary(report):
    status_icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}
    icon = status_icon.get(report.status, "❓")
    title = report.title_en[:55]
    print(f"  {icon}  {color(report.status, f'{report.status.upper():8s}')}  "
          f"{title:55s}  ⚡{report.duration_ms:8.1f}ms")


# ── Scenario registry ──
SCENARIOS = [
    ("s01_core_engine",      "s01", "Core Engine Pipeline"),
    ("s02_conflict_detection","s02", "Conflict Detection"),
    ("s03_c5_autofix",       "s03", "C5 Auto-Fix Chain"),
    ("s04_workflow_governor","s04", "Workflow Governor"),
    ("s05_llm_integration",  "s05", "LLM Integration"),
    ("s06_batch_benchmark",  "s06", "Batch Benchmark"),
    ("s07_judge_pipeline",   "s07", "Judge Pipeline"),
]


def main():
    skip_llm = "--skip-llm" in sys.argv
    rules_path = str(Path(__file__).parent / ".." / "rules")

    print_banner()
    print(f"  📂  Rules: {rules_path}")
    print(f"  🏠  CWD:   {Path.cwd()}\n")
    print(f"  {'='*70}")

    # Count rules
    rules_count = 0
    for p in Path(rules_path).rglob("*.md"):
        if not p.name.startswith("_"):
            rules_count += 1
    print(f"  📚  Rules found: {rules_count}\n")

    all_reports = []
    start_time = time.perf_counter()

    for module_name, scenario_id, title in SCENARIOS:
        # Skip LLM scenarios if --skip-llm
        if skip_llm and scenario_id in ("s05",):
            from report import DemoReport
            report = DemoReport(
                scenario_id=scenario_id,
                title_en=f"{title} (skipped)",
                title_tr=f"{title} (atlandı)",
                status="skipped",
                duration_ms=0,
            )
            all_reports.append(report)
            print_summary(report)
            continue

        print(f"\n  {CYAN}──▶  [{scenario_id}] {title}...{RESET}")

        try:
            mod = importlib.import_module(module_name)
            t1 = time.perf_counter()

            # Each scenario has a run() function that returns a DemoReport
            if hasattr(mod, "run"):
                report = mod.run(rules_path=rules_path)
            else:
                raise AttributeError(f"{module_name} has no run() function")

            report.duration_ms = max(report.duration_ms, (time.perf_counter() - t1) * 1000)

        except Exception as e:
            from report import DemoReport
            report = DemoReport(
                scenario_id=scenario_id,
                title_en=f"{title} (errored)",
                title_tr=f"{title} (hata)",
                status="failed",
                duration_ms=0,
            )
            report.add_section(
                "💥 Scenario Crashed",
                f"Error: {type(e).__name__}: {e}\n\n"
                f"This indicates a code issue — the scenario runner caught the error "
                f"gracefully so other scenarios can continue.",
                "error",
            )
            import traceback
            report.add_section("Traceback", traceback.format_exc(), "code")

        all_reports.append(report)
        print_summary(report)

    # ── Final Summary ──
    total_time = (time.perf_counter() - start_time) * 1000
    passed = sum(1 for r in all_reports if r.status == "passed")
    failed = sum(1 for r in all_reports if r.status == "failed")
    skipped = sum(1 for r in all_reports if r.status == "skipped")

    print(f"\n  {'='*70}")
    print(f"  {BOLD}SUMMARY{RESET}")
    print(f"  ✅  Passed:  {passed}")
    print(f"  ❌  Failed:  {failed}")
    print(f"  ⏭️  Skipped: {skipped}")
    print(f"  ⏱️  Total:   {total_time:.0f}ms")
    print(f"  📊  Report:  demo-agent/report.html")
    print(f"  {'='*70}\n")

    # ── Generate HTML Report ──
    try:
        from report import save_report
        output_path = str(Path(__file__).parent / "report.html")
        save_report(all_reports, output_path, rules_count=rules_count)
        print(f"  📊  HTML rapor: {output_path}")
        print(f"  🔗  Dosya boyutu: {os.path.getsize(output_path):,} bytes")
    except Exception as e:
        print(f"  ❌  HTML report generation failed: {e}")
        import traceback
        traceback.print_exc()

    # Exit code
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
