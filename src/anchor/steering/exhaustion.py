"""
Anchor v5.0 — Adaptive Exhaustion Detection.

Amaç:
  Sabit iteration limit yerine, violation'ların complexity'sine ve
  improvement rate'ine göre dinamik tükenme kararı.

Algoritma:
  1. Her turda violation sayısı ve complexity (ağırlıklı severity) kaydedilir
  2. Improvement rate = (prev_count - curr_count) / prev_count
  3. Stagnation counter: eğer improvement > %15 ise sıfırlanır
  4. Max stagnation threshold: complexity arttıkça yükselir
  5. Exhausted = stagnation >= max_stagnation

Complexity hesaplaması:
  - CRITICAL:  4 puan
  - ERROR:     3 puan
  - WARNING:   2 puan
  - INFO:      1 puan
  - Her violation: 1 taban puan
  - Toplam complexity = sum(severity_weights) + violation_count
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from anchor import Severity

logger = logging.getLogger(__name__)

# Severity weight map
SEVERITY_WEIGHT: dict[Severity, int] = {
    Severity.NONE: 0,
    Severity.INFO: 1,
    Severity.WARNING: 2,
    Severity.ERROR: 3,
    Severity.CRITICAL: 4,
}

# Min improvement rate to reset stagnation
STAGNATION_RESET_THRESHOLD = 0.15  # %15

# Base stagnation limit before complexity adjustment
BASE_MAX_STAGNATION = 2

# Extra rounds per N complexity points
COMPLEXITY_EXTRA_ROUND_STEP = 5

# Absolute max rounds to prevent infinite loops
ABSOLUTE_MAX_ROUNDS = 10


def compute_violation_complexity(
    severity_counts: dict[str, int],
    total_violations: int,
) -> int:
    """Violation complexity'sini hesapla.

    Args:
        severity_counts: {severity_name: count} dict
            Örn: {"CRITICAL": 2, "WARNING": 1}
        total_violations: Toplam violation sayısı

    Returns:
        Complexity skoru (≥ 0)
    """
    severity_map = {
        "CRITICAL": 4, "ERROR": 3,
        "WARNING": 2, "INFO": 1,
    }
    weighted = sum(
        severity_map.get(name, 1) * count
        for name, count in severity_counts.items()
    )
    return weighted + total_violations


def compute_max_stagnation(complexity: int) -> int:
    """Complexity'ye göre maksimum stagnation limiti.

    Daha karmaşık violation set'i daha fazla tur alabilir.
    """
    extra = int(complexity / COMPLEXITY_EXTRA_ROUND_STEP)
    return BASE_MAX_STAGNATION + extra


@dataclass
class ExhaustionState:
    """Bir tur sonundaki tükenme durumu.

    Attributes:
        round_number:       Tur numarası (0-indexed)
        violation_count:    Bu turdaki violation sayısı
        complexity:         Ağırlıklı complexity skoru
        improvement_rate:   Bir önceki tura göre iyileşme oranı (0-1)
        stagnation_count:   Ardışık iyileşmesiz tur sayısı
        max_stagnation:     İzin verilen maksimum stagnation
        is_exhausted:       Tükenme durumu (loop devam edebilir mi?)
        reason:             Tükenme sebebi (varsa)
    """
    round_number: int = 0
    violation_count: int = 0
    complexity: int = 0
    improvement_rate: float = 0.0
    stagnation_count: int = 0
    max_stagnation: int = BASE_MAX_STAGNATION
    is_exhausted: bool = False
    reason: str = ""


class AdaptiveExhaustion:
    """Adaptive exhaustion detector — loop kontrolü.

    Kullanım:
        exhaustion = AdaptiveExhaustion()
        
        # Her tur sonunda:
        state = exhaustion.update(severity_counts, total_violations)
        if state.is_exhausted:
            break
    """

    def __init__(self, absolute_max_rounds: int = ABSOLUTE_MAX_ROUNDS):
        self._history: list[ExhaustionState] = []
        self._absolute_max = absolute_max_rounds

    @property
    def history(self) -> list[ExhaustionState]:
        """Tüm tur geçmişi (read-only)."""
        return list(self._history)

    @property
    def round_count(self) -> int:
        return len(self._history)

    def update(
        self,
        severity_counts: dict[str, int],
        total_violations: int,
    ) -> ExhaustionState:
        """Yeni bir tur ekle ve tükenme durumunu hesapla.

        Args:
            severity_counts: {severity_name: count}
                Örn: {"CRITICAL": 1, "WARNING": 2}
            total_violations: Toplam violation sayısı

        Returns:
            Güncel ExhaustionState
        """
        round_num = len(self._history)
        prev_state = self._history[-1] if self._history else None

        # Complexity
        complexity = compute_violation_complexity(
            severity_counts, total_violations,
        )

        # Improvement rate
        if prev_state and prev_state.violation_count > 0:
            improvement = (
                (prev_state.violation_count - total_violations)
                / prev_state.violation_count
            )
        else:
            improvement = 0.0

        # Stagnation: reset if meaningful progress, else increment
        if improvement >= STAGNATION_RESET_THRESHOLD:
            stagnation = 0
        else:
            stagnation = (prev_state.stagnation_count + 1) if prev_state else 0

        # Max stagnation (dynamic — complexity-aware)
        max_stag = compute_max_stagnation(complexity)

        # Absolute max check FIRST
        if round_num >= self._absolute_max:
            state = ExhaustionState(
                round_number=round_num,
                violation_count=total_violations,
                complexity=complexity,
                improvement_rate=improvement,
                stagnation_count=stagnation,
                max_stagnation=max_stag,
                is_exhausted=True,
                reason=f"Maksimum tur sayısına ulaşıldı ({self._absolute_max})",
            )
            self._history.append(state)
            return state

        # Is exhausted?
        is_exhausted = stagnation >= max_stag
        reason = ""
        if is_exhausted:
            reason = (
                f"Stagnasyon: {stagnation} >= {max_stag} "
                f"(complexity={complexity}, improvement=%{improvement * 100:.0f})"
            )

        state = ExhaustionState(
            round_number=round_num,
            violation_count=total_violations,
            complexity=complexity,
            improvement_rate=improvement,
            stagnation_count=stagnation,
            max_stagnation=max_stag,
            is_exhausted=is_exhausted,
            reason=reason,
        )

        self._history.append(state)

        if is_exhausted:
            logger.info("Anchor exhaustion: %s", reason)

        return state

    def reset(self):
        """Geçmişi temizle (yeni bir loop başlatırken)."""
        self._history.clear()

    def summary(self) -> str:
        """Tüm tur geçmişini özetle."""
        if not self._history:
            return "Henüz tur kaydı yok."

        lines = [f"Toplam tur: {len(self._history)}"]
        for s in self._history:
            status = "⛔ TÜKENDİ" if s.is_exhausted else "✓ devam"
            lines.append(
                f"  Tur {s.round_number}: {s.violation_count} violation "
                f"(compx={s.complexity}, imp=%{s.improvement_rate * 100:.0f}, "
                f"stagnation={s.stagnation_count}/{s.max_stagnation}) {status}"
            )
        return "\n".join(lines)
