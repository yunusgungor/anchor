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

[v4.5+] Enhanced Features:
  - Claim Highlighting: Hatalı kısımları metinde işaretleme
  - Severity Analysis: Her düzeltme için ayrıntılı ciddiyet analizi
  - Highlight Legend: Terminal için renk/emoji lejantı
"""

import re
from typing import Any, Optional

from anchor.engine import RectificationResult


# Severity emoji/renk haritası
SEVERITY_MAP = {
    "CRITICAL": {"emoji": "🔴", "label": "Critical", "color": "\033[91m"},
    "ERROR": {"emoji": "❌", "label": "Error", "color": "\033[93m"},
    "WARNING": {"emoji": "⚠️", "label": "Warning", "color": "\033[93m"},
    "INFO": {"emoji": "ℹ️", "label": "Info", "color": "\033[94m"},
}
RESET = "\033[0m"


class FactCheckMode:
    """
    FactCheck Mode — Anchor'ın faktör doğrulama yeteneklerini full sergiler.

    Bu mod, Anchor'ın en güçlü olduğu alanı gösterir:
    gerçek hataları bulmak ve düzeltmek.

    Yeni Yetenekler:
      - Claim Highlighting: Hatalı claim'leri metinde highlight et
      - Severity Dashboard: CRITICAL/ERROR/WARNING/INFO özeti
      - Dedup Log: seen_claims nedeniyle atlanan düzeltmeleri göster
    """

    def __init__(self):
        self.name = "factcheck"
        self._stats = {"total_checks": 0, "total_corrections": 0, "dedup_skipped": 0}

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
          2. Claim highlighting — hatalı kısımları metinde işaretle
          3. Severity analysis — CRITICAL/ERROR/WARNING/INFO dağılımı
          4. Judge pipeline sonucu varsa ekle
          5. Loopback limit aşıldıysa uyar
          6. Dedup log — seen_claims nedeniyle atlananları göster
        """
        result = {
            "mode": self.name,
            "judge_passed": None,
            "loopback_count": 0,
            "cross_rule_count": 0,
            "negation_count": 0,
            "severity_breakdown": {},
            "highlighted_output": corrected,
            "claim_highlights": [],
            "dedup_skipped_count": 0,
        }

        if anchor_result:
            # --- Claim Highlighting ---
            highlights = self._build_highlights(anchor_result)
            result["claim_highlights"] = highlights
            result["highlighted_output"] = self._apply_highlights(corrected, highlights)

            # --- Severity Breakdown ---
            severity_breakdown = self._severity_breakdown(anchor_result)
            result["severity_breakdown"] = severity_breakdown

            # --- Judge pipeline ---
            if hasattr(anchor_result, "judge_result"):
                result["judge_passed"] = anchor_result.judge_result.get("passed")
                result["judge_details"] = anchor_result.judge_result.get("details", {})

            # --- Loopback ---
            if hasattr(anchor_result, "loopback_count"):
                result["loopback_count"] = anchor_result.loopback_count
                if anchor_result.loopback_count >= 5:
                    result["loopback_warning"] = (
                        "⚠️ Loopback limit aşıldı (>=5). Cevap hala hatalı olabilir."
                    )

            # --- Cross-rule ---
            if hasattr(anchor_result, "cross_rule_conflicts"):
                result["cross_rule_count"] = len(anchor_result.cross_rule_conflicts)

            # --- Dedup (seen_claims) ---
            dedup_skipped = getattr(anchor_result, "_dedup_skipped", 0)
            result["dedup_skipped_count"] = dedup_skipped
            self._stats["dedup_skipped"] += dedup_skipped

            # --- Negation ---
            if hasattr(anchor_result, "negation_hits"):
                result["negation_count"] = len(anchor_result.negation_hits)

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

    # ---------------------------------------------------------------- #
    # Highlighting Engine
    # ---------------------------------------------------------------- #

    def _build_highlights(self, anchor_result) -> list[dict]:
        """
        Her düzeltme için highlight bilgisi oluştur.

        Returns:
            [{
                "original": "hatalı metin",
                "corrected": "düzeltilmiş metin",
                "severity": "ERROR",
                "topic": "Clean Architecture",
                "index": int,
            }, ...]
        """
        highlights = []
        for i, corr in enumerate(anchor_result.corrections or []):
            sev = corr.conflict.severity.name if hasattr(corr.conflict, 'severity') else "INFO"
            topic = corr.conflict.topic if hasattr(corr.conflict, 'topic') else "unknown"
            highlights.append({
                "index": i + 1,
                "original": corr.original_text,
                "corrected": corr.corrected_text,
                "severity": sev,
                "topic": topic,
                "edit_distance": corr.edit_distance if hasattr(corr, 'edit_distance') else 0,
                "confidence": corr.conflict.confidence if hasattr(corr.conflict, 'confidence') else 0,
            })
        return highlights

    @staticmethod
    def _apply_highlights(text: str, highlights: list[dict]) -> str:
        """
        Metindeki hatalı claim'leri highlight işaretçileriyle sar.

        Örnek:
            Girdi: "NPX1 bir GPU'dur ve 5nm ile üretilmiştir."
            Çıktı: "NPX1 bir GPU'dur ve [❌5nm] ile üretilmiştir."
        """
        if not highlights:
            return text

        highlighted = text
        for h in highlights:
            sev_info = SEVERITY_MAP.get(h["severity"], SEVERITY_MAP["INFO"])
            original = h["original"]
            if original and original in highlighted:
                marker = f"{sev_info['emoji']}[{original}]"
                highlighted = highlighted.replace(original, marker, 1)
        return highlighted

    @staticmethod
    def _severity_breakdown(anchor_result) -> dict:
        """
        Düzeltmelerin ciddiyet dağılımını çıkar.

        Returns:
            {
                "CRITICAL": count,
                "ERROR": count,
                "WARNING": count,
                "INFO": count,
                "total": count,
                "most_severe": "ERROR",
            }
        """
        breakdown = {"CRITICAL": 0, "ERROR": 0, "WARNING": 0, "INFO": 0, "total": 0}
        most_severe = "INFO"
        severity_order = ["CRITICAL", "ERROR", "WARNING", "INFO"]

        for corr in anchor_result.corrections or []:
            sev = corr.conflict.severity.name if hasattr(corr.conflict, 'severity') else "INFO"
            breakdown[sev] = breakdown.get(sev, 0) + 1
            breakdown["total"] += 1
            if severity_order.index(sev) < severity_order.index(most_severe):
                most_severe = sev

        breakdown["most_severe"] = most_severe
        return breakdown

    @staticmethod
    def format_highlight_legend() -> str:
        """Highlight lejantı — terminal çıktısında kullanılır."""
        lines = ["\n📋 Highlight Lejantı:"]
        for sev, info in SEVERITY_MAP.items():
            lines.append(f"   {info['emoji']} {sev:<10} → {info['label']}")
        return "\n".join(lines)

    @property
    def stats(self) -> dict:
        return dict(self._stats)
