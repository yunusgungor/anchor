"""
FactCheckMode — Anchor'ın A1-A4 pipeline'ını tam güçle kullanan mod.

Anchor'ın TÜM yeteneklerini sergiler:
  - A1: Sentence Segmentation + Negation-Aware Regex Detection
  - A2: Multi-Strategy Semantic Similarity (TF-IDF + Embedding + Fuzzy)
  - A3: Causal Conflict Tree (CCI heuristic + path analysis)
  - A4: Strategic Multi-Vector Rectification
  - 3-Phase Judge Pipeline (Quick → Guided → Review)
  - Dedup (seen_claims) — tekrar eden düzeltmeleri engeller
  - Cross-Rule Guard (birden çok rule çakışınca)
  - Word-Fallback (kısa claim'ler için embedding yerine regex)
"""

from typing import Any, Optional

from anchor.engine import RectificationResult


class FactCheckMode:
    """
    FactCheck Mode — Anchor'ın faktör doğrulama yeteneklerini full sergiler.
    
    Bu mod, Anchor'ın en güçlü olduğu alanı gösterir:
    gerçek hataları bulmak ve düzeltmek.
    """
    
    def __init__(self):
        self.name = "factcheck"
        self._stats = {"total_checks": 0, "total_corrections": 0}
    
    def post_process(
        self,
        query: str,
        raw: str,
        corrected: str,
        anchor_result: "RectificationResult | None" = None,
    ) -> dict:
        """
        Anchor sonrası FactCheck özel işleme.
        
        Burada yapılanlar:
          1. Anchor result'dan ek bilgiler çıkar
          2. Judge pipeline sonucu varsa ekle
          3. Loopback limit aşıldıysa uyar
          4. Negation-aware detection sonucu varsa raporla
        """
        result = {
            "mode": self.name,
            "judge_passed": None,
            "loopback_count": 0,
            "cross_rule_count": 0,
            "negation_count": 0,
        }
        
        if anchor_result:
            # Judge pipeline
            if hasattr(anchor_result, "judge_result"):
                result["judge_passed"] = anchor_result.judge_result.get("passed")
                result["judge_details"] = anchor_result.judge_result.get("details", {})
            
            # Loopback
            if hasattr(anchor_result, "loopback_count"):
                result["loopback_count"] = anchor_result.loopback_count
                if anchor_result.loopback_count >= 5:
                    result["loopback_warning"] = (
                        "⚠️ Loopback limit aşıldı (>=5). Cevap hala hatalı olabilir."
                    )
            
            # Cross-rule
            if hasattr(anchor_result, "cross_rule_conflicts"):
                result["cross_rule_count"] = len(anchor_result.cross_rule_conflicts)
            
            # Stats
            self._stats["total_checks"] += 1
            if anchor_result.modified:
                self._stats["total_corrections"] += 1
        
        return result
    
    def enrich_query(self, query: str, context_notes: str | None = None) -> str:
        """Query'yi ek context ile zenginleştir."""
        if context_notes:
            return f"{query}\n\n[Context]: {context_notes}"
        return query
    
    @property
    def stats(self) -> dict:
        return dict(self._stats)
