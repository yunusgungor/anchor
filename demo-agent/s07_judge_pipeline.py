"""
s07 — Judge Pipeline ⚖️ (Real Rules)

Demonstrates advanced evaluation layers using ONLY real Anchor rules/workflows:
  • Similarity scoring between canonical rule facts and claims
  • Engine-as-Judge deterministic verdicts
  • Rule enrichment concept grounded in real rules
  • Response-cache hot path analysis
"""

import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from anchor.engine import AnchorEngine
from report import DemoReport, print_header, print_step, print_metric, print_table, bil


STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "are", "be",
    "bu", "bir", "ve", "veya", "ile", "için", "gibi", "olan", "olarak", "da", "de", "to", "then",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9_-]+", text.lower()) if t not in STOPWORDS]


def semantic_similarity(text1: str, text2: str) -> float:
    s1 = set(tokenize(text1))
    s2 = set(tokenize(text2))
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def cosine_similarity_text(text1: str, text2: str) -> float:
    def tf(tokens):
        return Counter(tokens)

    def cosine(v1, v2):
        import math
        all_words = set(v1.keys()) | set(v2.keys())
        dot = sum(v1.get(w, 0) * v2.get(w, 0) for w in all_words)
        n1 = math.sqrt(sum(v ** 2 for v in v1.values()))
        n2 = math.sqrt(sum(v ** 2 for v in v2.values()))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    return cosine(tf(tokenize(text1)), tf(tokenize(text2)))


def pct_label(expected: str, combined: float) -> str:
    if expected.startswith(">"):
        threshold = float(expected[1:])
        return "✅" if combined >= threshold else "⚠️"
    threshold = float(expected[1:])
    return "✅" if combined <= threshold else "⚠️"


def run(rules_path: str | None = None) -> DemoReport:
    report = DemoReport(
        scenario_id="s07",
        title_en="Judge Pipeline — Real Rules · Similarity · Deterministic Judge · Cache",
        title_tr="Judge Pipeline — Gerçek Kurallar · Benzerlik · Deterministik Yargıç · Önbellek",
    )

    if rules_path is None:
        rules_path = str(Path(__file__).parent.parent / "rules")

    print_header("s07: Judge Pipeline (real rules only)", "en")

    print_step(1, 5, "Initializing AnchorEngine")
    engine = AnchorEngine(rules_path)
    engine.build()

    print_step(2, 5, "Semantic similarity: canonical fact vs claim")
    similarity_pairs = [
        {
            "a": "TDD follows the order red, green, then refactor.",
            "b": "TDD means write a failing test, make it pass, then clean up the design.",
            "label": "TDD canonical vs paraphrase",
            "expected": ">0.30",
        },
        {
            "a": "Dependencies in Clean Architecture point inward.",
            "b": "In Clean Architecture, inner layers should depend on frameworks and databases.",
            "label": "Clean Architecture truth vs inversion",
            "expected": "<0.45",
        },
        {
            "a": "The test pyramid should contain many unit tests and fewer end-to-end tests.",
            "b": "A healthy test suite should mostly consist of end-to-end tests.",
            "label": "Test Pyramid truth vs inversion",
            "expected": "<0.45",
        },
        {
            "a": "Code review should check correctness, tests, security, and maintainability.",
            "b": "A proper review examines correctness, test coverage, security, and maintainability.",
            "label": "Code Review canonical vs paraphrase",
            "expected": ">0.35",
        },
        {
            "a": "Secrets must not be committed to source control.",
            "b": "API keys are safe to hardcode if the repository is private.",
            "label": "Secure Coding truth vs violation",
            "expected": "<0.35",
        },
        {
            "a": "Incident response includes assessment, containment, recovery, and postmortem.",
            "b": "Postmortem should be done immediately and assessment can be skipped.",
            "label": "Incident Response truth vs workflow break",
            "expected": "<0.40",
        },
    ]

    sim_rows = []
    sim_report_parts = []
    for sp in similarity_pairs:
        jaccard = semantic_similarity(sp["a"], sp["b"])
        cosine_sim = cosine_similarity_text(sp["a"], sp["b"])
        combined = (jaccard + cosine_sim) / 2
        color = pct_label(sp["expected"], combined)
        sim_rows.append([sp["label"][:34], f"{jaccard:.3f}", f"{cosine_sim:.3f}", f"{combined:.3f}", color])
        sim_report_parts.append(
            f"{sp['label']}: Jaccard={jaccard:.3f} | Cosine={cosine_sim:.3f} | Combined={combined:.3f} | Expected {sp['expected']} {color}"
        )
    print_table(sim_rows, ["Pair", "Jaccard", "Cosine", "Combined", ""])
    report.add_section(
        "🔤 Semantic Similarity",
        "Method: token overlap + cosine frequency similarity on real rule statements\n\n" + "\n".join(sim_report_parts),
        "info",
    )
    report.add_metric("Similarity Pairs", len(similarity_pairs), "", "🔤")

    print_step(3, 5, "Engine-as-Judge deterministic verdicts")
    judge_cases = [
        {
            "query": "Explain TDD workflow",
            "llm_output": "The best TDD workflow is implementation first, then tests later.",
            "expect_conflict": True,
        },
        {
            "query": "What is the weather like today?",
            "llm_output": "The weather is nice today with clear skies.",
            "expect_conflict": False,
        },
        {
            "query": "How do you make coffee?",
            "llm_output": "The quick brown fox jumps over the lazy dog.",
            "expect_conflict": False,
        },
        {
            "query": "How should secrets be stored?",
            "llm_output": "Hardcode secrets into the app and rely on repository privacy.",
            "expect_conflict": True,
        },
    ]

    judge_rows = []
    judge_correct = 0
    for jc in judge_cases:
        t1 = time.perf_counter()
        result = engine.process(jc["query"], jc["llm_output"])
        latency_us = (time.perf_counter() - t1) * 1_000_000
        got_conflict = bool(result.corrections)
        ok = got_conflict == jc["expect_conflict"]
        judge_correct += int(ok)
        severity = result.corrections[0].conflict.severity.name if result.corrections else "NONE"
        rule = result.corrections[0].conflict.rule_id if result.corrections else "—"
        judge_rows.append([
            jc["query"][:28],
            "conflict" if got_conflict else "pass",
            severity,
            rule[:18],
            f"{latency_us:.0f}μs",
            "✅" if ok else "❌",
        ])
    print_table(judge_rows, ["Query", "Verdict", "Severity", "Rule", "Latency", ""])
    report.add_section(
        "⚖️ Engine-as-Judge Results",
        "\n".join(
            f"• {row[0]} → {row[1]} | severity={row[2]} | rule={row[3]} | latency={row[4]} {row[5]}"
            for row in judge_rows
        ),
        "success" if judge_correct == len(judge_cases) else "warning",
    )
    report.add_metric("Judge Correct", f"{judge_correct}/{len(judge_cases)}", "", "🎯")

    print_step(4, 5, "Rule Enricher concept grounded in actual rules")
    enricher_demo = """Rule Enricher Concept — grounded in current Anchor rules

Canonical rule facts can be expanded into semantically nearby phrasings:

TDD rule:
  • Canonical: "Red → Green → Refactor"
  • Paraphrase: "Write a failing test, make it pass, then improve the code"
  • Paraphrase: "Test-first, pass the test, then clean up design"

Clean Architecture rule:
  • Canonical: "Dependencies point inward"
  • Paraphrase: "Outer layers must not drive domain logic"
  • Paraphrase: "Frameworks depend on the core, not the reverse"

Secure Coding rule:
  • Canonical: "Do not commit secrets"
  • Paraphrase: "API keys must stay out of source control"
  • Paraphrase: "Secrets belong in runtime configuration, not code"

Purpose:
  • Increase semantic recall
  • Preserve deterministic rule identity
  • Reduce false negatives on paraphrased LLM output
"""
    report.add_section("🧩 Rule Enricher Concept", enricher_demo.strip(), "code")
    report.add_metric("Matching Strategies", "keyword + fuzzy + overlap", "", "🧩")

    print_step(5, 5, "Response Cache hot-path analysis")
    cache_queries = [
        ("TDD cycle", "Implementation first, then tests later."),
        ("Clean Architecture", "Dependencies point inward through architectural boundaries."),
        ("Code Review", "Review only formatting; tests are optional."),
        ("Incident Response", "Assess, contain, recover, then write the postmortem."),
    ]
    cold_times = []
    warm_times = []
    cache_rows = []
    for query, answer in cache_queries:
        t1 = time.perf_counter()
        engine.process(query, answer)
        cold = (time.perf_counter() - t1) * 1_000_000
        t2 = time.perf_counter()
        engine.process(query, answer)
        warm = (time.perf_counter() - t2) * 1_000_000
        cold_times.append(cold)
        warm_times.append(warm)
        improvement = ((cold - warm) / cold * 100) if cold else 0.0
        cache_rows.append([query[:26], f"{cold:.0f}μs", f"{warm:.0f}μs", f"{improvement:.0f}%"])
    print_table(cache_rows, ["Query", "Cold", "Warm", "Improvement"])
    report.add_section(
        "📦 Response Cache (Hot Path)",
        "\n".join(f"• {row[0]:26s}  cold {row[1]:>8s} → warm {row[2]:>8s}  ({row[3]})" for row in cache_rows),
        "success",
    )
    avg_impr = sum(((c - w) / c * 100) for c, w in zip(cold_times, warm_times) if c) / len(cache_queries)
    report.add_metric("Avg Cache Improvement", f"{avg_impr:.0f}", "%", "🔥")
    report.add_metric("Cache Entries", len(cache_queries), "", "📦")

    report.add_section(
        "💡 Key Insight",
        bil(
            "This judge pipeline is now fully anchored in real rules. Similarity scoring, deterministic verdicting, enrichment concepts, and cache behavior are all demonstrated on actual Anchor topics rather than synthetic domains.",
            "Bu judge pipeline artık tamamen gerçek kurallara dayanıyor. Benzerlik skoru, deterministik karar verme, zenginleştirme fikri ve önbellek davranışı; sentetik alanlar yerine gerçek Anchor konuları üstünde gösteriliyor.",
        ),
        "success",
    )

    report.status = "passed" if judge_correct == len(judge_cases) else "warning"
    report.duration_ms = max(sum(cold_times) / 1000, 1.0)
    report.add_metric("Semantic Pairs", len(similarity_pairs), "", "🔤")
    report.add_metric("Cache Improvement", f"{avg_impr:.0f}", "%", "🔥")
    return report


if __name__ == "__main__":
    report = run()
    print(f"\n  ✅  s07: {report.status}")
