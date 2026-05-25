#!/usr/bin/env python3
"""
Anchor Agent Demo — Kullanım ve çalıştırma.

Kullanım:
    # Doğrudan
    python run.py ask "NPX1 nedir?"
    python run.py ask "How to set up Anchor?" --mode workflow
    python run.py ask "Write a tweet about AI safety" --mode creative
    
    # Chat modu
    python run.py chat
    
    # API sunucusu
    python run.py serve --port 8080
    
    # Batch
    python run.py batch queries.txt
    
    # Modları listele
    python run.py modes
    
    # İstatistikler
    python run.py stats
    
    # Test query (örnek)
    python run.py demo
"""

import sys
import os

# Anchor path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.cli import main, build_parser
from agent.core.agent import AnchorAgent


def demo():
    """Demo queries — Anchor'ın tüm modlarını göster."""
    import time
    
    print("\n" + "=" * 60)
    print(" 🔍  ANCHOR AGENT DEMO")
    print("    Tüm yeteneklerin eksiksiz gösterimi")
    print("=" * 60)
    
    # Agent
    agent = AnchorAgent(
        rules_path=os.environ.get("ANCHOR_RULES_PATH", "rules"),
        llm_provider=os.environ.get("ANCHOR_LLM_PROVIDER", "openai"),
        llm_api_key=os.environ.get("ANCHOR_LLM_API_KEY"),
    )
    
    reporter = agent.reporter
        
    demo_queries = [
        ("factcheck", "🔍 Gerçek Doğrulama", 
         "What is NPX1? Is it a GPU or an AI accelerator?"),
        ("workflow", "⚙️  İş Akışı", 
         "How to implement the Anchor fact-checking pipeline step by step?"),
        ("creative", "🎨 Yaratıcı İçerik", 
         "Write a tweet about Anchor's deterministic correction engine"),
    ]
    
    for mode_name, mode_title, query in demo_queries:
        print(f"\n\n{'─' * 60}")
        print(f" {mode_title}  [{mode_name}]")
        print(f" Query: {query[:70]}...")
        print(f"{'─' * 60}")
        
        t0 = time.perf_counter()
        result = agent.ask(query, mode=mode_name)
        elapsed = (time.perf_counter() - t0) * 1000
        
        print(f"\n Response ({elapsed:.0f}ms):")
        print(f" {result.corrected}")
        
        if result.modified:
            print(f"\n ✏️  Düzeltmeler ({len(result.corrections)}):")
            for c in result.corrections:
                sev = c.get("severity", "INFO")
                print(f"    [{sev}] {c.get('original', '')[:60]} → {c.get('corrected', '')[:60]}")
        else:
            print(f"\n ✅ Anchor onaylı — düzeltme gerekmedi")
        
        print(f"\n   Toplam süre: {elapsed:.0f}ms | Güven: {result.confidence:.0%}")
    
    print(f"\n\n{'=' * 60}")
    print(" ✅  DEMO COMPLETE")
    print(f" {'='*60}\n")


if __name__ == "__main__":
    # Check for demo command
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    else:
        main()
