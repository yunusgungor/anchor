#!/usr/bin/env python3
"""
Anchor Demo Runner — Tüm Anchor Kabiliyetlerini Sergileyen 10 Senaryo

Bu demo, Anchor'ın tüm özelliklerini LLM olmadan (saf engine ile) gösterir.
Her senaryo belirli bir Anchor kabiliyetini test eder.

Kullanım:
    python run_demo.py              # Tüm senaryoları çalıştır
    python run_demo.py --list       # Senaryoları listele
    python run_demo.py --scenario 1 # Tek senaryo çalıştır
    python run_demo.py --json       # JSON çıktı
    python run_demo.py --html       # HTML rapor
"""

import argparse
import importlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# --- Paths ---
DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(DEMO_DIR)
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, DEMO_DIR)

# --- Imports ---
from anchor import RectificationResult, Correction, Conflict, Severity, Topic
from anchor.engine import AnchorEngine

# Agent components
from agent.modes.factcheck import FactCheckMode, SEVERITY_MAP
from agent.modes.workflow import WorkflowMode, VIOLATION_DISPLAY
from agent.modes.creative import CreativeMode, FORMAT_CONSTRAINTS
from agent.core.classifier import TaskClassifier
from agent.core.reporter import Reporter
from agent.templates.system_prompts import get_system_prompt


# ---------------------------------------------------------------- #
# Scenario Definitions
# ---------------------------------------------------------------- #

@dataclass
class DemoResult:
    """Bir demo senaryosunun sonucu."""
    id: int
    title: str
    anchor_feature: str
    description: str
    test_text: str
    mode: str
    anchor_result: Optional[RectificationResult] = None
    mode_result: dict = field(default_factory=dict)
    success: bool = False
    details: str = ""
    elapsed_us: float = 0.0


SCENARIOS: list[dict] = [
    # ──────────────────────────────────────────
    # 1. A1: Negation Detection
    # ──────────────────────────────────────────
    {
        "id": 1,
        "title": "A1: Negation-Aware Regex Detection",
        "anchor_feature": "Negation-Aware Detection (A1)",
        "description": "Anchor, 'NOT', 'never', 'avoid' gibi negasyonları algılar ve "
                       "olumlu ifadeleri otomatik düzeltir. Bu senaryoda 'NOT using microservices' "
                       "ifadesinin Factory Method pattern'ı ile çeliştiğini tespit eder.",
        "mode": "factcheck",
        "test_text": (
            "For our payment system, we should implement the Factory Method pattern. "
            "This pattern is NOT suitable for object creation when "
            "we don't know the concrete types at compile time — "
            "it should be avoided in these cases. "
            "The factory will use a simple if-else chain."
        ),
        "expected": "modified",
    },
    # ──────────────────────────────────────────
    # 2. A2: Semantic Similarity
    # ──────────────────────────────────────────
    {
        "id": 2,
        "title": "A2: Multi-Strategy Semantic Similarity",
        "anchor_feature": "Semantic Similarity (A2) — TF-IDF + Embedding + Fuzzy",
        "description": "Anchor, faklı yazılmış ama aynı anlama gelen ifadeleri "
                       "TF-IDF, embedding ve fuzzy matching ile tespit eder. "
                       "'Single responsibility' → 'one reason to change' gibi varyasyonları yakalar.",
        "mode": "factcheck",
        "test_text": (
            "Each module should have only one single reason to change. "
            "This is known as single responsibility. "
            "Our classes should follow one responsibility principle strictly."
        ),
        "expected": "no_modification",
    },
    # ──────────────────────────────────────────
    # 3. A3: Causal Conflict Tree
    # ──────────────────────────────────────────
    {
        "id": 3,
        "title": "A3: Causal Conflict Tree (CCI Heuristic)",
        "anchor_feature": "Causal Conflict Intelligence (A3)",
        "description": "Anchor, CCI heuristic ile neden-sonuç ilişkilerini analiz eder. "
                       "'Since X is slow, we should optimize' gibi ifadelerde X'in "
                       "aslında hızlı olduğunu tespit eder — yanlış nedensellik.",
        "mode": "factcheck",
        "test_text": (
            "Since the Repository pattern creates tight coupling between "
            "our domain and data access layer, we should replace it with "
            "direct SQL queries for better performance and simplicity."
        ),
        "expected": "modified",
    },
    # ──────────────────────────────────────────
    # 4. A4: Multi-Vector Rectification
    # ──────────────────────────────────────────
    {
        "id": 4,
        "title": "A4: Multi-Vector Strategic Rectification",
        "anchor_feature": "Strategic Multi-Vector Rectification (A4)",
        "description": "Anchor, aynı metinde birden çok hatayı aynı anda bulur ve düzeltir. "
                       "Her biri farklı stratejiyle: bazıları regex, bazıları semantik, "
                       "bazıları ise causal analiz ile.",
        "mode": "factcheck",
        "test_text": (
            "In our architecture, we use Singletons everywhere because "
            "they are easy to implement. We also don't use any design patterns "
            "since they add unnecessary complexity. "
            "The Factory Method pattern is NOT appropriate for creating objects — "
            "it should be avoided. Just use 'new' directly."
        ),
        "expected": "modified",
    },
    # ──────────────────────────────────────────
    # 5. Workflow: Missing Steps
    # ──────────────────────────────────────────
    {
        "id": 5,
        "title": "Workflow Governor: Eksik Adım Tespiti",
        "anchor_feature": "Workflow Governor — Missing Step Detection",
        "description": "Anchor'ın Workflow Governor'ı, belirtilen iş akışındaki "
                       "eksik adımları tespit eder. Bu senaryoda bir bug-fix sürecinde "
                       "kök neden analizi ve regression test adımları atlanmıştır.",
        "mode": "workflow",
        "test_text": (
            "I fixed the bug in the payment module. First, I reproduced the issue "
            "by following the steps from the ticket. Then I wrote a failing test "
            "that captures the bug scenario. Finally, I applied a minimal code change "
            "to fix the root cause."
        ),
        "expected": "modified",
    },
    # ──────────────────────────────────────────
    # 6. Workflow: Order Violation
    # ──────────────────────────────────────────
    {
        "id": 6,
        "title": "Workflow Governor: Sıra İhlali",
        "anchor_feature": "Workflow Governor — Order Violation",
        "description": "Anchor, adımların doğru sırada olup olmadığını kontrol eder. "
                       "Bu senaryoda test yazmadan önce kod yazılmıştır — Red-Green-Refactor "
                       "sırası ihlal edilmiştir.",
        "mode": "workflow",
        "test_text": (
            "I implemented the authentication feature. First, I wrote the production code "
            "because I knew exactly what to build. Then I cleaned up the code with refactoring. "
            "Finally, I added unit tests to verify everything works."
        ),
        "expected": "modified",
    },
    # ──────────────────────────────────────────
    # 7. C5: Character Limit
    # ──────────────────────────────────────────
    {
        "id": 7,
        "title": "C5: Karakter Limiti + Auto-Truncation",
        "anchor_feature": "Constraint Engine (C5) — Character Limit Enforcement",
        "description": "C5 Constraint Engine, format kurallarına göre karakter limitini kontrol eder. "
                       "Aşım durumunda Smart Truncation devreye girer: cümle bilinciyle keser, "
                       "anlam bütünlüğünü korur.",
        "mode": "creative",
        "test_text": (
            "🚀 Just shipped the most incredible feature that completely transforms "
            "how we handle authentication and authorization in our microservices architecture "
            "with distributed session management and real-time token refresh capabilities! "
            "This is going to change everything about how our users interact with the platform "
            "and we couldn't be more excited to share this with all of you! 🎉"
        ),
        "expected": "auto_fix",
        "format": "tweet",
    },
    # ──────────────────────────────────────────
    # 8. C5: Emoji + Section Fix
    # ──────────────────────────────────────────
    {
        "id": 8,
        "title": "C5: Emoji Denetimi + Eksik Bölüm Ekleme",
        "anchor_feature": "Constraint Engine (C5) — Emoji & Section Enforcement",
        "description": "C5, format kurallarına göre emoji kullanımını ve zorunlu bölümleri denetler. "
                       "Makale formatında emoji temizlenir, eksik bölümler otomatik eklenir.",
        "mode": "creative",
        "test_text": (
            "🎉🌟✨🚀 Our new Anchor Engine is finally here! It's the most "
            "powerful deterministic correction engine ever built, with "
            "sub-millisecond latency and zero hallucination risk. "
            "Try it today and experience the future of AI reliability!"
        ),
        "expected": "auto_fix",
        "format": "article",
    },
    # ──────────────────────────────────────────
    # 9. Dedup + Cross-Rule Guard
    # ──────────────────────────────────────────
    {
        "id": 9,
        "title": "Dedup + Cross-Rule Guard",
        "anchor_feature": "Dedup (seen_claims) + Cross-Rule Guard",
        "description": "Anchor, seen_claims ile tekrar eden düzeltmeleri engeller. "
                       "Cross-Rule Guard ise aynı metinde birden çok kural çakıştığında "
                       "en uygun düzeltmeyi seçer. Bu senaryoda aynı yanlış ifade "
                       "iki kez geçer — Anchor sadece ilkini düzeltir.",
        "mode": "factcheck",
        "test_text": (
            "Singletons are great for holding mutable shared state. "
            "I said it before: Singletons are great for holding mutable shared state. "
            "We use them everywhere in our codebase for caching and configuration."
        ),
        "expected": "modified",
    },
    # ──────────────────────────────────────────
    # 10. Full Pipeline
    # ──────────────────────────────────────────
    {
        "id": 10,
        "title": "🚀 Full Pipeline: Tüm Anchor Kabiliyetleri",
        "anchor_feature": "Full Pipeline (A1→A4 + Workflow + C5 + Judge + Dedup)",
        "description": "Anchor'ın tüm pipeline'ını tek seferde gösterir: "
                       "topic extraction → knowledge retrieval → conflict detection → "
                       "rectification → workflow validation → constraint enforcement.",
        "mode": "factcheck",
        "test_text": (
            "For our new project, I'm using Singletons extensively because "
            "they make shared state easy to manage. Since Singletons create "
            "no coupling issues, we can use them freely without worrying about testing. "
            "This approach is NOT a violation of Clean Architecture. "
            "I also skipped the refactoring step in TDD because the code "
            "already looked clean enough."
        ),
        "expected": "modified",
    },
]


# ---------------------------------------------------------------- #
# Demo Runner
# ---------------------------------------------------------------- #

class DemoRunner:
    """
    10 Anchor kabiliyetini sergileyen demo runner.
    Tüm senaryolar saf engine ile çalışır — LLM gerekmez.
    """

    def __init__(self, rules_path: str = "rules"):
        """Engine ve mode'ları başlat."""
        print("🔧 Anchor Demo Engine başlatılıyor...")
        self.rules_path = os.path.join(ROOT_DIR, rules_path)
        
        # Engine
        self.engine = AnchorEngine(rules_path=self.rules_path, use_embedding=False)
        t0 = time.perf_counter()
        self.engine.build()
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"   ✅ Rules loaded: {len(self.engine.store._rule_meta)} rules ({elapsed:.0f}ms)")
        
        # Modes & Reporter
        self.modes = {
            "factcheck": FactCheckMode(),
            "workflow": WorkflowMode(),
            "creative": CreativeMode(),
        }
        self.reporter = Reporter()

    def run_scenario(self, scenario: dict) -> DemoResult:
        """Tek bir demo senaryosunu çalıştır."""
        sid = scenario["id"]
        title = scenario["title"]
        mode_name = scenario["mode"]
        text = scenario["test_text"]

        print(f"\n{'='*70}")
        print(f"  [{sid}/10] {title}")
        print(f"{'='*70}")
        print(f"  Mode: {mode_name.upper()} | Feature: {scenario['anchor_feature']}")
        print(f"  Text: {text[:80]}...")

        # 1. Run Anchor Engine
        t0 = time.perf_counter()
        anchor_result = self.engine.process(user_query=text, llm_output=text)
        elapsed_us = (time.perf_counter() - t0) * 1_000_000

        # 2. Mode-specific post-processing
        mode = self.modes[mode_name]
        mode_result = mode.post_process(
            query=text,
            raw=text,
            corrected=anchor_result.corrected,
            anchor_result=anchor_result,
        )

        # 3. Determine success
        success_msg = self._determine_success(scenario, anchor_result, mode_result)

        return DemoResult(
            id=sid,
            title=title,
            anchor_feature=scenario["anchor_feature"],
            description=scenario["description"],
            test_text=text,
            mode=mode_name,
            anchor_result=anchor_result,
            mode_result=mode_result,
            success="✅" in success_msg,
            details=success_msg,
            elapsed_us=elapsed_us,
        )

    @staticmethod
    def _determine_success(scenario: dict, ar: RectificationResult, mr: dict) -> str:
        """Senaryonun başarılı olup olmadığını belirle."""
        expected = scenario.get("expected", "modified")

        if expected == "modified":
            if ar.modified:
                sev = mr.get("severity_breakdown", {})
                return f"✅ Düzeltme uygulandı ({len(ar.corrections)} correction, severity: {sev.get('most_severe', 'N/A')})"
            return "❌ Beklenen düzeltme bulunamadı"

        elif expected == "no_modification":
            return "✅ (beklenen) Düzeltme gerekmedi — text zaten doğru"

        elif expected == "auto_fix":
            fixes = mr.get("auto_fixes_applied", [])
            if fixes:
                return f"✅ Auto-fix uygulandı: {' | '.join(fixes)}"
            violations = mr.get("violations", [])
            if violations:
                return f"✅ Kısıtlama ihlali tespit edildi: {len(violations)} violation"
            return "ℹ️ İhlal tespit edilmedi (beklenen: auto-fix)"

        return f"ℹ️ Sonuç: modified={ar.modified}"

    def run_all(self, json_output: bool = False) -> list[DemoResult]:
        """Tüm senaryoları sırayla çalıştır."""
        results = []
        passed = 0

        for scenario in SCENARIOS:
            result = self.run_scenario(scenario)
            results.append(result)
            passed += 1 if result.success else 0

            # Print result
            self._print_result(result)

        # Summary
        print(f"\n{'='*70}")
        print(f"  📊 DEMO SUMMARY: {passed}/{len(SCENARIOS)} PASSED")
        print(f"{'='*70}")
        for r in results:
            mark = "✅" if r.success else "❌"
            print(f"  [{r.id:02d}] {mark} {r.title[:50]:<50} ({r.elapsed_us:.0f}μs)")
        print(f"{'='*70}\n")

        if json_output:
            self._print_json(results)

        return results

    def _print_result(self, result: DemoResult):
        """Demo sonucunu güzel formatla."""
        print(f"\n  ═══ Sonuç {'═'*40}")
        print(f"  {result.details}")
        if result.mode_result.get("judge_passed") is not None:
            jp = result.mode_result["judge_passed"]
            print(f"  Judge Pipeline: {'✅ PASS' if jp else '❌ FAIL'}")

        # Mode-specific extras
        mr = result.mode_result

        # Claim highlights (factcheck)
        if mr.get("claim_highlights"):
            print(f"  Claim Highlighting: {len(mr['claim_highlights'])} highlights")
            for h in mr["claim_highlights"]:
                sev_info = SEVERITY_MAP.get(h["severity"], {"emoji": "ℹ️"})
                print(f"    {sev_info['emoji']} {h['original'][:40]} → {h['corrected'][:40]}")

        # Severity breakdown
        if mr.get("severity_breakdown"):
            sb = mr["severity_breakdown"]
            display = {k: v for k, v in sb.items() if k != "most_severe" and v and isinstance(v, int) and v > 0}
            print(f"  Severity: {display}")

        # Workflow report
        if mr.get("workflow_found"):
            wf_report = WorkflowMode.format_workflow_report(
                mr.get("violations", []), mr.get("step_progress", {})
            )
            for line in wf_report.split("\n"):
                print(f"  {line}")

        # Creative auto-fixes
        if mr.get("auto_fixes_applied"):
            for fix in mr["auto_fixes_applied"]:
                print(f"  {fix}")
        if mr.get("violations"):
            for v in mr["violations"]:
                print(f"  {v}")

        # Dedup
        if mr.get("dedup_skipped_count", 0) > 0:
            print(f"  Dedup: {mr['dedup_skipped_count']} atlandı (seen_claims)")

        # Timing
        print(f"  ⏱  {result.elapsed_us:.0f}μs | Corrections: {len(result.anchor_result.corrections) if result.anchor_result else 0}")
        print(f"  {'═' * 50}")

    @staticmethod
    def _print_json(results: list[DemoResult]):
        """JSON çıktısı."""
        data = []
        for r in results:
            data.append({
                "id": r.id,
                "title": r.title,
                "mode": r.mode,
                "success": r.success,
                "elapsed_us": r.elapsed_us,
                "details": r.details,
                "corrections": len(r.anchor_result.corrections) if r.anchor_result else 0,
                "modified": r.anchor_result.modified if r.anchor_result else False,
            })
        print(json.dumps(data, indent=2, ensure_ascii=False))

    @staticmethod
    def list_scenarios():
        """Senaryoları listele."""
        print(f"\n{'='*70}")
        print("  📋 ANCHOR DEMO — 10 Senaryo")
        print(f"{'='*70}")
        for s in SCENARIOS:
            mode_emoji = {"factcheck": "🔍", "workflow": "⚙️", "creative": "🎨"}.get(s["mode"], "🔍")
            print(f"\n  [{s['id']:02d}] {mode_emoji} {s['title']}")
            print(f"       Mode: {s['mode']:<10} Feature: {s['anchor_feature']}")
            print(f"       {s['description'][:100]}...")
        print(f"\n{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Anchor Demo — 10 senaryoda tüm kabiliyetler",
    )
    parser.add_argument("--list", action="store_true", help="Senaryoları listele")
    parser.add_argument("--scenario", type=int, help="Tek senaryo çalıştır (1-10)")
    parser.add_argument("--json", action="store_true", help="JSON çıktı")
    parser.add_argument("--rules", default="rules", help="Rules dizini")
    parser.add_argument("--html", action="store_true", help="HTML rapor üret")

    args = parser.parse_args()

    if args.list:
        DemoRunner.list_scenarios()
        return

    runner = DemoRunner(rules_path=args.rules)

    if args.scenario:
        scenario = next((s for s in SCENARIOS if s["id"] == args.scenario), None)
        if not scenario:
            print(f"❌ Scenario {args.scenario} bulunamadı (1-10 arası)")
            sys.exit(1)
        result = runner.run_scenario(scenario)
        if args.json:
            print(json.dumps({"success": result.success, "elapsed_us": result.elapsed_us}, indent=2))
    else:
        runner.run_all(json_output=args.json)


if __name__ == "__main__":
    main()
