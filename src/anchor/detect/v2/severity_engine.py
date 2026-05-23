r"""
Severity Engine v2 — Distance → Severity mapping.

$$S(d) = \begin{cases}
\text{INFO} & \text{if } d \in [0.0, 0.2) \\
\text{WARNING} & \text{if } d \in [0.2, 0.5) \\
\text{ERROR} & \text{if } d \in [0.5, 0.8) \\
\text{CRITICAL} & \text{if } d \in [0.8, 1.0]
\end{cases}$$

Ek kural:
  - D_neg > 0.5 (olumsuzlaştırma varsa) → minimum WARNING
  - D_edit > 0.7 ve D_sem > 0.7 → CRITICAL
"""

from anchor import Severity

from .fact_matcher import MatchResult


class SeverityEngine:
    """
    Bir MatchResult'ın distance değerlerini Severity'ye dönüştürür.
    """
    
    # Threshold'lar (düzenlenebilir)
    INFO_THRESHOLD = 0.2
    WARNING_THRESHOLD = 0.5
    ERROR_THRESHOLD = 0.8
    
    def compute(self, match: MatchResult) -> Severity:
        """
        MatchResult'ı severity'e dönüştür.
        
        Args:
            match: FactMatcher'dan gelen sonuç
            
        Returns:
            Severity (INFO, WARNING, ERROR, CRITICAL)
        """
        d = match.combined_distance
        
        # Özel kural: Olumsuzlaştırma varsa minimum WARNING
        if match.negative_distance > 0.3:
            if d >= self.ERROR_THRESHOLD:
                return Severity.CRITICAL
            # max(WARNING, _from_distance) — integer olarak karşılaştır
            base_sev = self._from_distance(d)
            if base_sev.value < Severity.WARNING.value:
                return Severity.WARNING
            return base_sev
        
        # Özel kural: Hem edit hem semantic çok yüksekse CRITICAL
        if match.edit_distance > 0.7 and match.semantic_distance > 0.7:
            return Severity.CRITICAL
        
        return self._from_distance(d)
    
    def _from_distance(self, d: float) -> Severity:
        """Pure distance → severity mapping."""
        if d < self.INFO_THRESHOLD:
            return Severity.INFO
        elif d < self.WARNING_THRESHOLD:
            return Severity.WARNING
        elif d < self.ERROR_THRESHOLD:
            return Severity.ERROR
        else:
            return Severity.CRITICAL
    
    def confidence(self, match: MatchResult) -> float:
        """
        Çelişki tespitinin güven skoru.
        
        Returns:
            0.0-1.0, 1.0 = kesin çelişki
        """
        return match.combined_distance
