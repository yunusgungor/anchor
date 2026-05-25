"""
s05 — Multi-Provider LLM Integration 🤖

Demonstrates Anchor's LLM integration capabilities:
  • ask()       — Single Q&A with automatic Anchor guarding
  • ask_stream() — Real-time streaming with async correction
  • batch_ask() — Efficient multi-query processing
  • Multi-provider support (OpenAI, Anthropic, OpenRouter, Ollama)
  • Confidence scoring — per-correction reliability metrics
  • Raw vs Corrected comparison
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from report import (
    DemoReport,
    print_header,
    print_step,
    print_metric,
    print_table,
    bil,
)


def run(rules_path: str | None = None) -> DemoReport:
    report = DemoReport(
        scenario_id="s05",
        title_en="Multi-Provider LLM Integration — ask · batch_ask · confidence · providers",
        title_tr="Çoklu Sağlayıcı LLM Entegrasyonu — ask · batch_ask · güven · sağlayıcılar",
    )

    if rules_path is None:
        rules_path = str(Path(__file__).parent.parent / "rules")

    print_header("s05: Multi-Provider LLM Integration", "en")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # Check if key is set in shell but not passed to Python (sandbox restriction)
        shell_check = os.popen('echo "${OPENAI_API_KEY:+SET}" 2>/dev/null').read().strip()
        if shell_check == "SET":
            report.status = "skipped"
            report.add_section(
                "⏭️ LLM Integration — Environment Restricted",
                "OPENAI_API_KEY is set in the shell environment but is not passed to "
                "Python subprocesses due to environment sanitization.\n\n"
                "This scenario demonstrates SafeLLMAgent with real LLM calls:\n"
                "  • ask() — Single Q&A with Anchor guarding\n"
                "  • batch_ask() — Multi-query processing\n"
                "  • ask_stream() — Real-time streaming\n"
                "  • Confidence scoring\n"
                "  • Raw vs Corrected comparison\n\n"
                "Run locally with 'python demo-agent/run_all.py' to execute with API access.",
                "warning",
            )
            report.duration_ms = 0
            return report

        report.status = "skipped"
        report.add_section(
            "⏭️ LLM Integration Skipped",
            "OPENAI_API_KEY not set. Set it to run this scenario with real LLM calls.",
            "warning",
        )
        report.duration_ms = 0
        return report

    # ── Step 1: Initialize with OpenAI ──
    print_step(1, 5, "Initializing SafeLLMAgent with OpenAI provider")
    t0 = time.perf_counter()
    try:
        from anchor.agent import SafeLLMAgent

        agent = SafeLLMAgent(
            rules_path=rules_path,
            llm_provider="openai",
            llm_api_key=api_key,
            llm_model="gpt-4o-mini",
        )
        init_ms = (time.perf_counter() - t0) * 1000
        print_metric("Init time", f"{init_ms:.1f}", "ms")
        report.add_metric("Init Time", f"{init_ms:.1f}", "ms", "⏱️")
        report.add_section(
            "🚀 Agent Initialized",
            f"Provider: OpenAI\n"
            f"Model: gpt-4o-mini\n"
            f"Rules: {rules_path}\n"
            f"Init time: {init_ms:.1f}ms",
            "success",
        )
    except Exception as e:
        report.status = "failed"
        report.add_section(
            "❌ Agent Init Failed",
            f"Could not initialize SafeLLMAgent: {e}",
            "error",
        )
        report.duration_ms = 0
        return report

    # ── Step 2: ask() — Single query with anchor guarding ──
    print_step(2, 5, "ask() — Single query through Anchor-guarded LLM")

    test_questions = [
        "Neural Processor X1 nedir? Hangi teknoloji ile üretilir?",
        "What is StateGuard and what does it do?",
        "RISC-V mimarisinin avantajları nelerdir?",
    ]

    ask_results = []
    for i, q in enumerate(test_questions):
        t1 = time.perf_counter()
        try:
            result = agent.ask(q)
            lat_ms = (time.perf_counter() - t1) * 1000

            ask_results.append({
                "query": q[:50],
                "raw": result.raw[:60],
                "corrected": result.corrected[:60],
                "modified": result.modified,
                "confidence": result.confidence,
                "latency": f"{lat_ms:.1f}ms",
                "topics": result.topics,
                "corrections": result.corrections,
            })

            report.add_section(
                f"🤖 ask() #{i + 1}: {q[:45]}",
                f"Query: {q}\n"
                f"Raw LLM: {result.raw[:120]}...\n"
                f"Anchor-corrected: {result.corrected[:120]}...\n"
                f"Modified: {'✅ Yes' if result.modified else '❌ No'} | "
                f"Confidence: {result.confidence:.2f}\n"
                f"Topics: {', '.join(result.topics) or 'general'}\n"
                f"Latency: {lat_ms:.1f}ms\n"
                + (f"Corrections: {len(result.corrections)}"
                   + "".join(f"\n  • [{c['severity']}] {c['original'][:50]} → {c['corrected'][:50]}"
                             for c in result.corrections)
                   if result.corrections else "No corrections needed"),
                "warning" if result.modified else "success",
            )

            print_step(3, 5, f"  [{i+1}/3] {q[:45]:45s}  {'🔧' if result.modified else '✅':4s}  confidence={result.confidence:.2f}  {lat_ms:.1f}ms  topics={result.topics[:2]}")

        except Exception as e:
            report.add_section(
                f"❌ ask() #{i + 1}: {q[:40]}",
                f"Error: {e}",
                "error",
            )
            ask_results.append({"query": q[:50], "error": str(e)})

    # ── Step 3: batch_ask() — Multi-query ──
    print_step(3, 5, "batch_ask() — Multi-query processing")
    batch_questions = [
        "What is the RISC-V instruction set architecture?",
        "Explain SKY130 open source PDK",
        "What are the advantages of open source hardware?",
    ]

    t_batch_start = time.perf_counter()
    try:
        batch_results = agent.batch_ask(batch_questions)
        batch_ms = (time.perf_counter() - t_batch_start) * 1000

        modified_count = sum(1 for r in batch_results if r.modified)
        total_conf = sum(r.confidence for r in batch_results) / max(len(batch_results), 1)

        report.add_section(
            "📦 batch_ask() Results",
            f"Queries: {len(batch_questions)}\n"
            f"Total time: {batch_ms:.1f}ms\n"
            f"Avg time/query: {batch_ms / len(batch_questions):.1f}ms\n"
            f"Modified: {modified_count}/{len(batch_questions)}\n"
            f"Avg confidence: {total_conf:.2f}",
            "info",
        )
        report.add_metric("Batch Size", len(batch_questions), "", "📦")
        report.add_metric("Batch Total", f"{batch_ms:.1f}", "ms", "⏱️")
        report.add_metric("Avg Confidence", f"{total_conf:.2f}", "", "🎯")

        for i, (q, r) in enumerate(zip(batch_questions, batch_results)):
            print(f"     [{i+1}] {q[:45]:45s}  confidence={r.confidence:.2f}  modified={'✅' if r.modified else '❌'}")
            report.add_section(
                f"   Batch #{i + 1}: {r.confidence:.2f} conf",
                f"Q: {q}\nModified: {r.modified}\nConfidence: {r.confidence}\nTopics: {r.topics}",
                "warning" if r.modified else "success",
            )

    except Exception as e:
        report.add_section("❌ batch_ask() Failed", f"Error: {e}", "error")

    # ── Step 4: Multi-provider comparison ──
    print_step(4, 5, "Multi-provider integration overview")
    provider_info = """```mermaid
graph LR
    subgraph Providers
        OAI[OpenAI<br/>GPT-4 / GPT-4o]
        ANT[Anthropic<br/>Claude 3 / 4]
        OR[OpenRouter<br/>Multi-model]
        OLL[Ollama<br/>Local LLMs]
    end

    subgraph Agent
        SLM[SafeLLMAgent<br/>LLM + Anchor Guard]
    end

    subgraph Anchor
        ENG[AnchorEngine<br/>Deterministic]
        RU[Rules<br/>Facts + Workflows]
    end

    subgraph Output
        RAW[Raw LLM]
        COR[Corrected]
        REP[+ Report]
    end

    OAI --> SLM
    ANT --> SLM
    OR --> SLM
    OLL --> SLM
    SLM --> RAW --> ENG --> COR
    RU --> ENG
    ENG --> REP
```

**Supported Providers:**
| Provider | Key | Client Class |
|----------|-----|-------------|
| OpenAI | `openai` | `OpenAIClient` |
| Anthropic | `anthropic` | `AnthropicClient` |
| OpenRouter | `openai-compatible` | `OpenAICompatibleClient` |
| Ollama | `ollama` | `OllamaClient` |
| Custom | `openai-compatible` | `OpenAICompatibleClient` |

**Key Diff: With vs Without Anchor**
| Aspect | Raw LLM | SafeLLMAgent |
|--------|---------|-------------|
| Factual accuracy | Unchecked | ✅ Rule-verified |
| Workflow compliance | Unchecked | ✅ Governor-validated |
| Contradiction handling | None | ✅ C5 auto-fix |
| Confidence metric | None | ✅ 0-1 score per response |
| Latency overhead | Baseline | +<10μs (deterministic) |"""

    report.add_section(
        "🌐 Multi-Provider Architecture",
        provider_info.strip(),
        "info",
    )

    # ── Step 5: Confidence scoring ──
    print_step(5, 5, "Confidence scoring analysis")
    confidence_info = ""
    for res in ask_results:
        if "error" not in res:
            confidence_info += (
                f"  • {res['query'][:40]:42s}  "
                f"confidence={res['confidence']:.2f}  "
                f"modified={'✅' if res['modified'] else '❌'}  "
                f"topics={str(res['topics'][:2])}\n"
            )

    report.add_section(
        "🎯 Confidence Scoring",
        confidence_info.strip() or "No LLM results available.",
        "info",
    )

    report.add_section(
        "💡 Key Insight",
        bil(
            "Anchor's LLM integration provides a safety net for any LLM output. "
            "The SafeLLMAgent wraps ANY provider (OpenAI, Claude, local models) and "
            "automatically runs the C5 pipeline on every response. The confidence score "
            "tells users when to trust vs verify — all with <10μs deterministic overhead.",
            "Anchor'un LLM entegrasyonu herhangi bir LLM çıktısı için güvenlik ağı sağlar. "
            "SafeLLMAgent herhangi bir sağlayıcıyı (OpenAI, Claude, yerel modeller) sarar ve "
            "her yanıtta otomatik olarak C5 pipeline'ını çalıştırır. Güven skoru, kullanıcıya "
            "ne zaman güvenip ne zaman doğrulaması gerektiğini söyler — tümü <10μs deterministik ek yük ile.",
        ),
        "success",
    )

    report.status = "passed"
    if ask_results:
        avg_lat = sum(float(r.get("latency", "0").replace("ms", "")) for r in ask_results if "latency" in r)
        report.duration_ms = avg_lat / len([r for r in ask_results if "latency" in r]) if ask_results else 2000
        report.add_metric("Avg Latency", f"{report.duration_ms:.0f}", "ms", "⚡")
        report.add_metric("Queries", len(ask_results), "", "💬")
        modified = sum(1 for r in ask_results if r.get("modified"))
        report.add_metric("Modified", modified, f"/{len(ask_results)}", "🔧")

    return report


if __name__ == "__main__":
    report = run()
    print(f"\n  ✅  s05: {report.status}")
