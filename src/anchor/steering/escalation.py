"""
Anchor v5.0 — Graduated Escalation Ladder.

ATLAS-RTC (arxiv 2603.27905) graduated intervention konsepti:

  Level 0: No-op          → Hiç violation yok
  Level 1: Advise         → Structured feedback ile LLM'e bildir
  Level 2: Regenerate     → LLM feedback ile yeniden üret
  Level 3: Strong Advise  → Daha güçlü feedback (örneklerle)
  Level 4: Correct        → Direkt corrective replacement (Anchor v4.x)
  Level 5: Escalate       → Kullanıcıya bildir / insan onayı

Her seviye için tetikleyici koşullar ve aksiyonlar tanımlıdır.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from anchor import Severity
from anchor.steering.exhaustion import ExhaustionState

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    """Müdahale seviyesi — artan müdahale yoğunluğu.

    ATLAS-RTC ladder'dan esinlenmiştir:
      0: No-op — response temiz, müdahale gerekmez
      1: Advise — structured feedback ile LLM bilgilendirilir
      2: Regenerate — LLM feedback ile yeniden üretir
      3: Strong Advise — daha güçlü feedback (örnekler + context)
      4: Correct — Anchor direkt corrective replacement uygular
      5: Escalate — insan onayı/devreye girmesi gerekir
    """
    NOOP = 0
    ADVISE = 1
    REGENERATE = 2
    STRONG_ADVISE = 3
    CORRECT = 4
    ESCALATE = 5


# Severity → minimum escalation level mapping
SEVERITY_MIN_LEVEL: dict[Severity, EscalationLevel] = {
    Severity.INFO: EscalationLevel.ADVISE,
    Severity.WARNING: EscalationLevel.REGENERATE,
    Severity.ERROR: EscalationLevel.REGENERATE,
    Severity.CRITICAL: EscalationLevel.CORRECT,
}


@dataclass
class EscalationDecision:
    """Bir escalation kararını temsil eder.

    Attributes:
        level:          Seçilen escalation seviyesi
        reason:         Karar gerekçesi
        round_number:   Hangi turda karar verildi
        fallback:       Bir üst seviyeye geçme sinyali var mı?
        fallback_reason: Neden bir üst seviyeye geçilmeli?
    """
    level: EscalationLevel
    reason: str
    round_number: int = 0
    fallback: bool = False
    fallback_reason: str = ""


class EscalationEngine:
    """Graduated escalation ladder — doğru müdahale seviyesini seç.

    Strategiler:
      1. İlk tur: severity'ye göre minimum seviye belirlenir
      2. Tekrarlanan turlar: stagnation arttıkça bir üst seviyeye geç
      3. CRITICAL violations: direkt CORRECT seviyesinden başla
      4. Exhaustion: otomatik olarak bir üst seviyeye geç
    """

    def __init__(self, start_from: EscalationLevel = EscalationLevel.ADVISE):
        self._start_from = start_from
        self._current_level = start_from
        self._rounds_at_level: int = 0

    @property
    def current_level(self) -> EscalationLevel:
        return self._current_level

    @property
    def rounds_at_level(self) -> int:
        return self._rounds_at_level

    def decide(
        self,
        max_severity: Severity,
        exhaustion: Optional[ExhaustionState] = None,
        round_number: int = 0,
        has_workflow_violations: bool = False,
    ) -> EscalationDecision:
        """Hangi escalation seviyesinin kullanılacağına karar ver.

        Args:
            max_severity:   Tespit edilen en yüksek severity
            exhaustion:     Mevcut exhaustion state (varsa)
            round_number:   Mevcut tur numarası
            has_workflow_violations: Workflow ihlali var mı?

        Returns:
            EscalationDecision
        """
        # First round: severity-based
        if round_number == 0:
            min_level = SEVERITY_MIN_LEVEL.get(max_severity, EscalationLevel.ADVISE)
            self._current_level = max(self._start_from, min_level, key=lambda x: x.value)
            self._rounds_at_level = 1

            reason = f"Başlangıç seviyesi (max_severity={max_severity.name})"
            decision = EscalationDecision(
                level=self._current_level,
                reason=reason,
                round_number=round_number,
            )
            return decision

        # Subsequent rounds: check exhaustion + escalation
        if exhaustion and exhaustion.is_exhausted:
            # Move up one level
            new_level = self._bump_level(self._current_level)
            self._rounds_at_level = 0

            if new_level.value > self._current_level.value:
                self._current_level = new_level
                reason = f"Tükenme → {new_level.name} seviyesine yükseltildi"
            else:
                # Already at max
                reason = f"Tükenme, zaten en üst seviyede ({new_level.name})"

            decision = EscalationDecision(
                level=self._current_level,
                reason=reason,
                round_number=round_number,
                fallback=(new_level == EscalationLevel.ESCALATE),
                fallback_reason=(
                    "Anchor tüm seviyeleri denedi — insan müdahalesi gerekli"
                    if new_level == EscalationLevel.ESCALATE
                    else ""
                ),
            )
            return decision

        # Stagnation-based escalation: CRITICAL violations that persist
        if max_severity == Severity.CRITICAL and self._current_level.value < EscalationLevel.CORRECT.value:
            self._current_level = EscalationLevel.CORRECT
            self._rounds_at_level = 1
            decision = EscalationDecision(
                level=EscalationLevel.CORRECT,
                reason="Kalıcı CRITICAL violation → corrective mode",
                round_number=round_number,
            )
            return decision

        # Stay at current level
        self._rounds_at_level += 1
        decision = EscalationDecision(
            level=self._current_level,
            reason=f"Mevcut seviyede devam ({self._current_level.name}, tur {round_number})",
            round_number=round_number,
        )
        return decision

    def _bump_level(self, current: EscalationLevel) -> EscalationLevel:
        """Bir üst escalation seviyesine geç."""
        order = [
            EscalationLevel.NOOP,
            EscalationLevel.ADVISE,
            EscalationLevel.REGENERATE,
            EscalationLevel.STRONG_ADVISE,
            EscalationLevel.CORRECT,
            EscalationLevel.ESCALATE,
        ]
        idx = order.index(current)
        if idx < len(order) - 1:
            return order[idx + 1]
        return current  # already at max

    def reset(self, start_from: Optional[EscalationLevel] = None):
        """Escalation durumunu sıfırla (yeni loop)."""
        if start_from:
            self._start_from = start_from
        self._current_level = self._start_from
        self._rounds_at_level = 0

    def summary(self) -> str:
        """Mevcut escalation durumunu özetle."""
        return (
            f"Escalation: {self._current_level.name} "
            f"(başlangıç: {self._start_from.name}, "
            f"{self._rounds_at_level} tur bu seviyede)"
        )
