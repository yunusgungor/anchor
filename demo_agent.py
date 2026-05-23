"""
Anchor Agent — Gerçek Akış Demo

Bu script, Anchor AI Agent'ın tam akışını gösterir:
  1. LLM'den ham cevap al (mock)
  2. Anchor ile düzelt
  3. Rapor üret
  4. Karşılaştır

Senaryolar:
  A. Yanlış bilgi → CRITICAL override
  B. Eksik bilgi → WARNING ekleme
  C. Doğru bilgi → Değişiklik yok
  D. Batch işleme
  E. Streaming simülasyonu
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from anchor.agent import SafeLLMAgent, AgentResult
from anchor.agent.llm_client import BaseLLMClient


class DemoLLMClient(BaseLLMClient):
    """Demo için mock LLM — senaryolara göre farklı cevaplar."""
    
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.responses = {
            "yanlis": "NPX1, genel amaçlı bir AI hızlandırıcısıdır ve TSMC 7nm'de üretilir. NVIDIA Jetson ile rekabet eder.",
            "eksik": "NPX1, RISC-V mimarili bir işlemcidir.",
            "dogru": "NPX1, edge AI işlemcisidir. SKY130 (130nm) açık kaynak PDK'da üretilir. Tarım ve güvenlik uygulamaları için tasarlanmıştır.",
            "stateguard_yanlis": "StateGuard, pasif bir güvenlik aracıdır. Uygulama güvenliği için kullanılır.",
            "stateguard_dogru": "StateGuard, LLM operatörü ve orkestratörüdür. Kullanıcı adına LLM'ye prompt yönetir.",
        }
    
    def chat(self, prompt: str, system=None) -> str:
        for key, value in self.responses.items():
            if key in self.scenario:
                return value
        return f"Demo cevap: {prompt}"
    
    def stream_chat(self, prompt: str, system=None):
        text = self.chat(prompt, system)
        for word in text.split():
            yield word + " "


def print_banner(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(result: AgentResult, show_raw: bool = True):
    """Sonucu güzel formatla yazdır."""
    if show_raw:
        print(f"\n🤖 LLM (Ham):")
        print(f"   {result.raw[:120]}...")
    
    print(f"\n🔧 Düzeltilmiş:")
    print(f"   {result.corrected[:200]}...")
    
    print(f"\n📊 Meta:")
    print(f"   Topic'ler: {result.topics}")
    print(f"   Düzeltildi mi: {'✅ Evet' if result.modified else '❌ Hayır'}")
    print(f"   Güven: {result.confidence:.2f}")
    print(f"   Latency: {result.latency_ms:.1f}ms")
    
    if result.corrections:
        print(f"\n📋 Düzeltmeler ({len(result.corrections)} adet):")
        for i, corr in enumerate(result.corrections, 1):
            sev = corr.get("severity", "?")
            print(f"   {i}. [{sev}]")
            print(f"      Önce: {corr['original'][:80]}...")
            print(f"      Sonra: {corr['corrected'][:80]}...")
    
    print(f"\n📝 Rapor:")
    for line in result.report.split("\n"):
        print(f"   {line}")


def main():
    RULES_PATH = str(Path(__file__).parent / "rules")
    INDEX_PATH = str(Path(__file__).parent / ".anchor_demo.idx")
    
    print_banner("ANCHOR AI AGENT — GERÇEK AKIŞ DEMO")
    print(f"Rules dizini: {RULES_PATH}")
    print(f"Index: {INDEX_PATH}")
    
    # ============================================================
    # SENARYO A: Yanlış bilgi → CRITICAL override
    # ============================================================
    print_banner("SENARYO A: YANLIŞ BİLGİ → CRITICAL OVERRIDE")
    print("Soru: NPX1 nedir?")
    print("LLM'in söylediği: 'Genel amaçlı AI hızlandırıcı, TSMC 7nm'de'")
    print("Doğrusu: 'Edge AI, SKY130 130nm'de'")
    
    agent = SafeLLMAgent(
        rules_path=RULES_PATH,
        llm_provider="openai",
        llm_api_key="mock",
        index_path=INDEX_PATH,
    )
    agent.llm._client = DemoLLMClient("yanlis")
    
    result = agent.ask("NPX1 nedir?")
    print_result(result)
    
    # ============================================================
    # SENARYO B: Eksik bilgi → WARNING ekleme
    # ============================================================
    print_banner("SENARYO B: EKSİK BİLGİ → WARNING EKLEME")
    print("Soru: NPX1 mimarisi nedir?")
    print("LLM'in söylediği: 'RISC-V mimarili'")
    print("Eksik: Systolic Array NPU, Edge AI amacı, üretim detayları")
    
    agent.llm._client = DemoLLMClient("eksik")
    result = agent.ask("NPX1 mimarisi nedir?")
    print_result(result)
    
    # ============================================================
    # SENARYO C: Doğru bilgi → Değişiklik yok
    # ============================================================
    print_banner("SENARYO C: DOĞRU BİLGİ → DEĞİŞİKLİK YOK")
    print("Soru: NPX1 nedir?")
    print("LLM'in söylediği: 'Edge AI, SKY130, tarım/güvenlik'")
    
    agent.llm._client = DemoLLMClient("dogru")
    result = agent.ask("NPX1 nedir?")
    print_result(result)
    
    # ============================================================
    # SENARYO D: StateGuard — farklı domain
    # ============================================================
    print_banner("SENARYO D: FARKLI DOMAIN (StateGuard)")
    print("Soru: StateGuard nedir?")
    print("LLM'in söylediği: 'Pasif güvenlik aracı'")
    print("Doğrusu: 'LLM operatörü / orkestratör'")
    
    agent.llm._client = DemoLLMClient("stateguard_yanlis")
    result = agent.ask("StateGuard nedir?")
    print_result(result)
    
    # ============================================================
    # SENARYO E: Batch işleme
    # ============================================================
    print_banner("SENARYO E: BATCH İŞLEME (3 soru)")
    
    questions = [
        "NPX1 nedir?",
        "StateGuard nedir?",
        "SKY130 PDK nedir?",
    ]
    
    # Her soru için farklı mock
    mocks = [
        DemoLLMClient("yanlis"),
        DemoLLMClient("stateguard_yanlis"),
        DemoLLMClient("dogru"),
    ]
    
    for q, mock in zip(questions, mocks):
        agent.llm._client = mock
        result = agent.ask(q)
        print(f"\n  ❓ {q}")
        print(f"     {'🔧 Düzeltildi' if result.modified else '✅ Doğru'} | "
              f"Güven: {result.confidence:.2f} | "
              f"Latency: {result.latency_ms:.1f}ms")
    
    # ============================================================
    # SENARYO F: Streaming
    # ============================================================
    print_banner("SENARYO F: STREAMING")
    print("Soru: NPX1 nedir?")
    print("LLM stream ediyor...")
    
    agent.llm._client = DemoLLMClient("yanlis")
    chunks = []
    for item in agent.ask_stream("NPX1 nedir?"):
        if item["type"] == "chunk":
            chunks.append(item["content"])
            print(item["content"], end="", flush=True)
        elif item["type"] == "final":
            print(f"\n\n✅ Stream tamamlandı")
            print(f"   Ham: {item['raw'][:80]}...")
            print(f"   Düzeltilmiş: {item['corrected'][:80]}...")
    
    # ============================================================
    # İSTATİSTİKLER
    # ============================================================
    print_banner("AGENT İSTATİSTİKLERİ")
    stats = agent.stats
    print(f"  Toplam sorgu: {stats['total_queries']}")
    print(f"  Düzeltilen: {stats['total_modified']}")
    print(f"  Düzeltme oranı: {stats['modification_rate']:.1%}")
    
    print("\n" + "=" * 70)
    print("  DEMO TAMAMLANDI")
    print("=" * 70)


if __name__ == "__main__":
    main()
