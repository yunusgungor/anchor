r"""
SafeLLM Agent — Anchor ile korunmuş LLM agent'ı.

Mantık:
  1. Kullanıcı sorusunu al
  2. LLM'den ham cevap al
  3. Anchor ile düzelt
  4. Düzeltilmiş cevabı + raporu sun

Özellikler:
  - Çoklu LLM desteği (OpenAI, Claude, Ollama)
  - Streaming düzeltme
  - Batch işleme
  - Confidence scoring
  - Fallback mechanism
  - Otomatik rule önerisi

Kullanım:
    from anchor.agent import SafeLLMAgent
    
    agent = SafeLLMAgent(
        rules_path="rules/",
        llm_provider="openai",
        llm_api_key="sk-..."
    )
    
    result = agent.ask("NPX1 nedir?")
    print(result["corrected"])
    print(result["report"])
"""

import time
from dataclasses import dataclass
from typing import Optional

from anchor.engine_v2 import AnchorEngineV2
from anchor.agent.llm_client import LLMClient


@dataclass
class AgentResult:
    """Agent yanıtı."""
    query: str
    raw: str                          # LLM'in ham cevabı
    corrected: str                    # Anchor ile düzeltilmiş
    modified: bool                    # Düzeltme yapıldı mı?
    confidence: float                 # Düzeltme güven skoru (0-1)
    corrections: list                 # Yapılan düzeltmeler listesi
    latency_ms: float                 # Toplam latency
    topics: list                      # Bulunan topic'ler
    rules_activated: list             # Aktive edilen rule'lar
    report: str                       # İnsan-okunabilir rapor


class SafeLLMAgent:
    """
    Anchor-guarded LLM Agent.
    
    Her LLM çağrısını Anchor rectification katmanından geçirir.
    """
    
    def __init__(
        self,
        rules_path: str,
        llm_provider: str = "openai",
        llm_api_key: Optional[str] = None,
        llm_model: Optional[str] = None,
        index_path: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        Agent oluştur.
        
        Args:
            rules_path: Anchor rules dizini
            llm_provider: "openai", "anthropic", "ollama"
            llm_api_key: API key (None ise env var'dan alınır)
            llm_model: Model ismi (None ise default)
            index_path: Anchor binary index yolu
            system_prompt: LLM'e verilecek sistem prompt'u
        """
        # Anchor engine
        self.engine = AnchorEngineV2(rules_path, index_path)
        self.engine.build()
        
        # LLM client
        kwargs = {}
        if llm_api_key:
            kwargs["api_key"] = llm_api_key
        if llm_model:
            kwargs["model"] = llm_model
        
        self.llm = LLMClient(provider=llm_provider, **kwargs)
        self.system_prompt = system_prompt
        
        # İstatistik
        self._total_queries = 0
        self._total_modified = 0
    
    def ask(self, question: str) -> AgentResult:
        """
        Tek soru sor, düzeltilmiş cevap al.
        
        Pipeline:
          1. LLM'den ham cevap al
          2. Anchor ile düzelt
          3. Rapor oluştur
        """
        t0 = time.perf_counter()
        
        # 1. LLM çağrısı
        try:
            raw_response = self.llm.chat(question, system=self.system_prompt)
        except Exception as e:
            return AgentResult(
                query=question,
                raw=f"[LLM HATASI: {e}]",
                corrected=f"[LLM HATASI: {e}]",
                modified=False,
                confidence=0.0,
                corrections=[],
                latency_ms=0.0,
                topics=[],
                rules_activated=[],
                report="LLM bağlantı hatası.",
            )
        
        # 2. Anchor düzeltme
        anchor_result = self.engine.process(question, raw_response)
        
        # 3. Confidence hesapla
        confidence = self._calculate_confidence(anchor_result)
        
        # 4. Rapor oluştur
        report = self._generate_report(question, anchor_result)
        
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000
        
        self._total_queries += 1
        if anchor_result.modified:
            self._total_modified += 1
        
        return AgentResult(
            query=question,
            raw=raw_response,
            corrected=anchor_result.corrected,
            modified=anchor_result.modified,
            confidence=confidence,
            corrections=[
                {
                    "original": corr.original_text,
                    "corrected": corr.corrected_text,
                    "severity": corr.conflict.severity.name,
                }
                for corr in anchor_result.corrections
            ],
            latency_ms=latency_ms,
            topics=[t.name for t in anchor_result.topics_found],
            rules_activated=anchor_result.rules_activated,
            report=report,
        )
    
    def ask_stream(self, question: str):
        """
        Streaming soru — LLM chunk'larını anlık düzelt.
        
        NOT: Tam streaming düzeltme için tüm metin gerekli.
        Bu versiyon: LLM bitince Anchor düzeltir.
        Gerçek anlık düzeltme için ChunkBuffer gerekli.
        """
        # LLM stream'ini topla
        chunks = []
        for chunk in self.llm.stream_chat(question, system=self.system_prompt):
            chunks.append(chunk)
            yield {"type": "chunk", "content": chunk}
        
        raw = "".join(chunks)
        
        # Anchor düzelt
        result = self.engine.process(question, raw)
        
        yield {
            "type": "final",
            "raw": raw,
            "corrected": result.corrected,
            "modified": result.modified,
            "topics": [t.name for t in result.topics_found],
        }
    
    def batch_ask(self, questions: list[str]) -> list[AgentResult]:
        """Birden fazla soruyu toplu işle."""
        results = []
        for q in questions:
            results.append(self.ask(q))
        return results
    
    def _calculate_confidence(self, anchor_result) -> float:
        """Düzeltme güven skoru hesapla (0-1)."""
        if not anchor_result.modified:
            return 1.0  # Değişiklik yok = tam güven
        
        # Correction sayısı ve severity'ye göre
        total_weight = 0
        penalty = 0
        
        for corr in anchor_result.corrections:
            sev = corr.conflict.severity
            if sev.name == "CRITICAL":
                penalty += 0.3
            elif sev.name == "ERROR":
                penalty += 0.2
            elif sev.name == "WARNING":
                penalty += 0.1
            else:
                penalty += 0.05
            total_weight += 1
        
        # Daha fazla düzeltme = daha düşük güven
        base_confidence = max(0.0, 1.0 - penalty)
        return round(base_confidence, 2)
    
    def _generate_report(self, question: str, anchor_result) -> str:
        """İnsan-okunabilir rapor oluştur."""
        lines = []
        lines.append(f"Soru: {question}")
        lines.append(f"Topic'ler: {[t.name for t in anchor_result.topics_found]}")
        
        if anchor_result.modified:
            lines.append(f"Düzeltme: {len(anchor_result.corrections)} adet")
            for i, corr in enumerate(anchor_result.corrections, 1):
                lines.append(f"  {i}. [{corr.conflict.severity.name}] {corr.conflict.topic}")
                lines.append(f"     Yanlış: {corr.original_text[:60]}...")
                lines.append(f"     Doğru:  {corr.corrected_text[:60]}...")
        else:
            lines.append("Düzeltme: Gerekmedi")
        
        lines.append(f"Latency: {anchor_result.latency_us.get('total', 0) / 1000:.1f}ms")
        
        return "\n".join(lines)
    
    @property
    def stats(self) -> dict:
        """Agent istatistikleri."""
        return {
            "total_queries": self._total_queries,
            "total_modified": self._total_modified,
            "modification_rate": self._total_modified / max(self._total_queries, 1),
            "anchor_stats": self.engine.stats,
        }
