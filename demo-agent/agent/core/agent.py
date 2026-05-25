"""
AnchorAgent — Anchor'ın tüm yeteneklerini birleştiren AI Agent.

Bu agent, Anchor'ın insanlara tanıtılması için tasarlanmıştır.
Tüm Anchor kabiliyetlerini tek bir arayüzde toplar:

  🔍 FactCheck Mode → A1-A4 pipeline + Negation + Judge
  ⚙️  Workflow Mode  → Workflow Governor + Step Validation
  🎨 Creative Mode   → C5 Constraint Engine + Format Enforcement

Kullanım:
    agent = AnchorAgent(rules_path="rules/", llm_provider="openai")
    
    # Tek sorgu
    result = agent.ask("NPX1 nedir?")
    
    # Multi-turn chat
    result = agent.chat("NPX1 bir GPU'dur")
    
    # Streaming
    for chunk in agent.stream_ask("Anchor nedir?"):
        print(chunk)
"""

import time
from typing import Generator, Optional

from anchor.agent.safe_llm import SafeLLMAgent, AgentResult
from anchor.agent.llm_client import LLMClient

from .classifier import TaskClassifier
from .context import ContextManager
from .reporter import Reporter

from ..modes.factcheck import FactCheckMode
from ..modes.workflow import WorkflowMode
from ..modes.creative import CreativeMode
from ..templates.system_prompts import get_system_prompt


class AnchorAgent:
    """
    Anchor Agent — unified interface to all Anchor capabilities.
    
    SafeLLMAgent'i kompoze eder (miras almaz) çünkü:
      1. Mode routing logic'i ekler
      2. Multi-turn context yönetir
      3. Mode-specific post-processing ekler
      4. Daha zengin raporlama sunar
    
    Pipeline:
        Query → TaskClassifier → Mode Selection → LLM Call
        → Anchor Pipeline → Mode Post-Processing → Report
    """
    
    def __init__(
        self,
        rules_path: str,
        llm_provider: str = "openai",
        llm_api_key: str | None = None,
        llm_model: str | None = None,
        llm_base_url: str | None = None,
        system_prompt: str | None = None,
        index_path: str | None = None,
        llm_client: LLMClient | None = None,
    ):
        # --- Core SafeLLMAgent ---
        self._safe = SafeLLMAgent(
            rules_path=rules_path,
            llm_provider=llm_provider,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            index_path=index_path,
            llm_client=llm_client,
            system_prompt=system_prompt,
        )
        
        # --- Components ---
        self.classifier = TaskClassifier()
        self.context = ContextManager()
        self.reporter = Reporter()
        
        # --- Modes ---
        self._modes = {
            "factcheck": FactCheckMode(),
            "workflow": WorkflowMode(),
            "creative": CreativeMode(),
        }
        
        # --- Runtime state ---
        self._total_queries = 0
        self._total_modified = 0
        self._total_mode_breakdown: dict[str, int] = {
            "factcheck": 0, "workflow": 0, "creative": 0
        }
    
    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    
    def ask(
        self,
        query: str,
        mode: str | None = None,
        verbose: bool = False,
    ) -> AgentResult:
        """
        Tek soru sor, düzeltilmiş cevap al.
        
        Pipeline:
          1. Mode classification
          2. Context enrichment
          3. LLM call (mode-specific system prompt)
          4. Anchor Engine rectification
          5. Mode-specific post-processing
          6. Context update
          7. Report generation
        
        Args:
            query: Kullanıcı sorusu
            mode: Zorla mode ("factcheck"/"workflow"/"creative" / None=auto)
            verbose: Detaylı rapor üret
            
        Returns:
            AgentResult
        """
        t0 = time.perf_counter()
        
        # 1. Classify mode
        actual_mode = self.classifier.classify(query, mode)
        
        # 2. Get mode handler + system prompt
        mode_handler = self._modes[actual_mode]
        
        rules_info = self._get_rules_info()
        system_prompt = get_system_prompt(actual_mode, rules_info)
        
        # 3. Enrich query with context
        context_notes = self.context.format_for_llm(max_tokens=500)
        enriched_query = mode_handler.enrich_query(query, context_notes)
        
        # 4. LLM call
        try:
            raw_response = self._safe.llm.chat(enriched_query, system=system_prompt)
        except Exception as e:
            return AgentResult(
                query=query,
                raw=f"[LLM HATASI: {e}]",
                corrected=f"[LLM Hatası: {e}]",
                modified=False,
                confidence=0.0,
                corrections=[],
                latency_ms=0.0,
                topics=[],
                rules_activated=[],
                report=f"LLM bağlantı hatası: {e}",
            )
        
        # 5. Anchor pipeline
        anchor_result = self._safe.engine.process(enriched_query, raw_response)
        
        # 6. Mode-specific post-processing
        mode_result = mode_handler.post_process(
            query=query,
            raw=raw_response,
            corrected=anchor_result.corrected,
            anchor_result=anchor_result,
        )
        
        # 7. Calculate confidence
        confidence = self._calculate_confidence(anchor_result)
        
        # 8. Build corrections list
        corrections = []
        for corr in anchor_result.corrections:
            corrections.append({
                "original": corr.original_text,
                "corrected": corr.corrected_text,
                "severity": corr.conflict.severity.name,
                "topic": corr.conflict.topic,
            })
        
        # 9. Update context
        self.context.add_message("user", query, mode=actual_mode)
        self.context.add_message(
            "assistant", anchor_result.corrected,
            mode=actual_mode,
            modified=anchor_result.modified,
            correction_count=len(anchor_result.corrections),
        )
        self.context.add_claims(
            [c.original_text for c in anchor_result.corrections]
        )
        
        # 10. Build report
        report = self._build_report(
            query=query,
            mode=actual_mode,
            anchor_result=anchor_result,
            mode_result=mode_result,
            corrections=corrections,
            confidence=confidence,
        )
        
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000
        
        # 11. Build result
        result = AgentResult(
            query=query,
            raw=raw_response,
            corrected=anchor_result.corrected,
            modified=anchor_result.modified,
            confidence=confidence,
            corrections=corrections,
            latency_ms=latency_ms,
            topics=[t.name for t in anchor_result.topics_found],
            rules_activated=anchor_result.rules_activated,
            report=report,
        )
        
        # Stash extra data for rich rendering
        self._stash_extra(result, actual_mode, mode_result)
        
        # Stats
        self._total_queries += 1
        self._total_mode_breakdown[actual_mode] += 1
        if anchor_result.modified:
            self._total_modified += 1
        
        return result
    
    def chat(self, message: str, mode: str | None = None) -> AgentResult:
        """
        Multi-turn conversation.
        
        ContextManager üzerinden konuşma geçmişini korur.
        Seen claims dedup ile Anchor'ın aynı hatayı tekrar
        tekrar düzeltmesini önler.
        """
        return self.ask(message, mode)
    
    def stream_ask(
        self, query: str, mode: str | None = None
    ) -> Generator[dict, None, None]:
        """
        Streaming soru — LLM chunk'ları + final düzeltme.
        
        Önce LLM stream'i gelir, bitince Anchor düzeltir.
        """
        # 1. Classify mode
        actual_mode = self.classifier.classify(query, mode)
        system_prompt = get_system_prompt(actual_mode, self._get_rules_info())
        
        # 2. Stream LLM
        chunks = []
        for chunk in self._safe.llm.stream_chat(query, system=system_prompt):
            chunks.append(chunk)
            yield {"type": "chunk", "content": chunk, "mode": actual_mode}
        
        raw = "".join(chunks)
        
        # 3. Anchor pipeline
        anchor_result = self._safe.engine.process(query, raw)
        
        # 4. Yield final
        yield {
            "type": "final",
            "raw": raw,
            "corrected": anchor_result.corrected,
            "modified": anchor_result.modified,
            "topics": [t.name for t in anchor_result.topics_found],
            "mode": actual_mode,
            "corrections": [
                {
                    "original": c.original_text,
                    "corrected": c.corrected_text,
                    "severity": c.conflict.severity.name,
                }
                for c in anchor_result.corrections
            ],
        }
    
    def batch_ask(
        self, queries: list[str], mode: str | None = None
    ) -> list[AgentResult]:
        """
        Toplu sorgu işleme.
        
        Her sorguyu sırayla işler. Paralel değil —
        context paylaşıldığı için sıralı olmalı.
        """
        results = []
        for q in queries:
            results.append(self.ask(q, mode))
        return results
    
    def reset_conversation(self) -> None:
        """Konuşma geçmişini sıfırla."""
        self.context.reset()
    
    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    
    @property
    def stats(self) -> dict:
        """Agent istatistikleri."""
        return {
            "total_queries": self._total_queries,
            "total_modified": self._total_modified,
            "modification_rate": round(
                self._total_modified / max(self._total_queries, 1), 3
            ),
            "mode_breakdown": dict(self._total_mode_breakdown),
            "anchor_engine": self._safe.engine.stats,
            "context": self.context.stats,
            "mode_stats": {
                name: handler.stats
                for name, handler in self._modes.items()
            },
        }
    
    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    
    def _calculate_confidence(self, anchor_result) -> float:
        """Düzeltme güven skoru (0-1)."""
        if not anchor_result.modified:
            return 1.0
        
        total_penalty = 0
        for corr in anchor_result.corrections:
            sev = corr.conflict.severity
            if sev.name == "CRITICAL":
                total_penalty += 0.3
            elif sev.name == "ERROR":
                total_penalty += 0.2
            elif sev.name == "WARNING":
                total_penalty += 0.1
            else:
                total_penalty += 0.05
        
        return round(max(0.0, 1.0 - total_penalty), 2)
    
    def _build_report(
        self,
        query: str,
        mode: str,
        anchor_result,
        mode_result: dict,
        corrections: list,
        confidence: float,
    ) -> str:
        """İnsan-okunabilir rapor oluştur."""
        lines = []
        lines.append(f"Mode: {mode.upper()}")
        lines.append(f"Query: {query}")
        
        # Anchor result
        if anchor_result.modified:
            lines.append(f"Corrections: {len(anchor_result.corrections)}")
            for i, corr in enumerate(anchor_result.corrections, 1):
                lines.append(
                    f"  {i}. [{corr.conflict.severity.name}] "
                    f"{corr.original_text[:50]} → {corr.corrected_text[:50]}"
                )
        else:
            lines.append("Corrections: None — Anchor approved")
        
        # Mode-specific extras
        if mode_result.get("judge_passed") is not None:
            lines.append(f"Judge: {'PASS' if mode_result['judge_passed'] else 'FAIL'}")
        
        if mode_result.get("loopback_warning"):
            lines.append(mode_result["loopback_warning"])
        
        if mode_result.get("steps_missing"):
            lines.append(f"Missing steps: {', '.join(mode_result['steps_missing'])}")
        
        if mode_result.get("violations"):
            for v in mode_result["violations"]:
                lines.append(f"Constraint violation: {v}")
        
        lines.append(f"Confidence: {confidence:.0%}")
        lines.append(f"Latency: {anchor_result.latency_us.get('total', 0) / 1000:.0f}ms")
        
        return "\n".join(lines)
    
    def _get_rules_info(self) -> str:
        """Anchor engine'den kural bilgisi al."""
        try:
            topics = self._safe.engine.get_topics()
            topic_names = [t.name for t in topics]
            if topic_names:
                return f"Kurallar: {', '.join(topic_names)}"
        except Exception:
            pass
        return "çeşitli kurallar"
    
    @staticmethod
    def _stash_extra(result: AgentResult, mode: str, mode_result: dict) -> None:
        """Result objesine ekstra metadata ekle."""
        result._mode = mode
        result._mode_result = mode_result
