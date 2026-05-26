"""
Anchor v5.0 — Active Steering Loop Orchestrator.

CAI-style self-critique + revision döngüsü:
  LLM → Anchor → [violations] → StructuredFeedback → LLM → Anchor → ...

Pipeline:
  1. LLM generates response
  2. Anchor analyzes, produces structured feedback
  3. If violations == 0 → return response (DONE)
  4. Package feedback for LLM
  5. LLM re-generates with feedback context
  6. Go to step 2
  7. If exhaustion → apply fallback strategy
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from anchor import (
    Conflict, Severity, Correction,
    RectificationResult,
)
from anchor.engine import AnchorEngine
from anchor.rectify import PatchEngine
from anchor.steering.feedback import (
    StructuredFeedback,
    FeedbackItem,
    GaaAFormatter,
    ContentType,
    classify_content,
)
from anchor.steering.exhaustion import (
    ExhaustionState,
    AdaptiveExhaustion,
    compute_violation_complexity,
)
from anchor.steering.escalation import (
    EscalationLevel,
    EscalationEngine,
    EscalationDecision,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Steering Round
# ──────────────────────────────────────────────


@dataclass
class SteeringRound:
    """A single iteration of the steering loop.

    Attributes:
        round_number:   0-indexed round number
        llm_output:     LLM output for this round
        corrected:      Corrected output (after Anchor processing)
        conflicts:      Detected conflicts
        feedback:       Structured feedback (GaaA format)
        correction_count: Number of corrections applied
        max_severity:    Highest severity in this round
        latency_us:     Round duration in microseconds
        escalation:     Escalation decision for this round
        exhaustion:     Exhaustion state after this round
    """
    round_number: int
    llm_output: str
    corrected: str
    conflicts: list[Conflict]
    feedback: StructuredFeedback
    correction_count: int
    max_severity: Severity
    latency_us: float
    escalation: Optional[EscalationDecision] = None
    exhaustion: Optional[ExhaustionState] = None

    @property
    def is_clean(self) -> bool:
        """Round sonunda hiç violation kalmamış mı?"""
        return self.correction_count == 0


@dataclass
class SteeringHistory:
    """Steering loop'un tüm turlarının geçmişi."""
    rounds: list[SteeringRound] = field(default_factory=list)

    @property
    def total_rounds(self) -> int:
        return len(self.rounds)

    @property
    def initial_violation_count(self) -> int:
        if not self.rounds:
            return 0
        return self.rounds[0].correction_count

    @property
    def final_violation_count(self) -> int:
        if not self.rounds:
            return 0
        return self.rounds[-1].correction_count

    @property
    def is_converged(self) -> bool:
        """Loop başarıyla temiz bir output'a ulaştı mı?"""
        if not self.rounds:
            return False
        return self.rounds[-1].is_clean

    def summary(self) -> str:
        """Steering loop özeti."""
        if not self.rounds:
            return "Henüz tur kaydı yok."

        lines = [
            f"Steering Loop: {len(self.rounds)} tur, "
            f"{self.initial_violation_count} → {self.final_violation_count} violation"
        ]
        for r in self.rounds:
            status = "✓ TEMİZ" if r.is_clean else f"✗ {r.correction_count} violation"
            sev_name = r.max_severity.name if r.max_severity else "NONE"
            lines.append(
                f"  Tur {r.round_number}: [{sev_name}] "
                f"{r.correction_count} düzeltme, "
                f"%{r.latency_us / 1000:.1f}ms {status}"
            )
            if r.escalation:
                lines.append(f"    → Escalation: {r.escalation.level.name}")
            if r.exhaustion and r.exhaustion.is_exhausted:
                lines.append(f"    → ⛔ TÜKENDİ: {r.exhaustion.reason}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Steering Loop — Core Logic
# ──────────────────────────────────────────────


class LLMGeneratorProtocol:
    """Protocol for LLM generation callback.

    The actual LLM integration is done by the caller (Hermes plugin, API, etc.).
    This abstract protocol defines the interface.
    """

    def generate(self, prompt: str, context: str = "") -> str:
        """Generate LLM response with optional feedback context.

        Args:
            prompt:  Original user query / prompt
            context: Additional context (structured feedback, anchor info)

        Returns:
            Generated LLM response text
        """
        raise NotImplementedError


class SteeringLoop:
    """Active steering loop — interleaved refinement.

    Kullanım:
        loop = SteeringLoop(engine, generator=my_llm_generator)
        result = loop.run(user_query, llm_output)

    Veya (manuel):
        loop = SteeringLoop(engine)
        result = loop.run_posthoc(user_query, llm_output)
        # Inspect result.feedback, result.history, etc.
    """

    def __init__(
        self,
        engine: AnchorEngine,
        generator: Optional[LLMGeneratorProtocol] = None,
        escalate_on_persistent: bool = True,
    ):
        self.engine = engine
        self.generator = generator
        self.escalate_on_persistent = escalate_on_persistent
        self.formatter = GaaAFormatter()
        self.exhaustion = AdaptiveExhaustion()
        self.escalation = EscalationEngine()
        self.history = SteeringHistory()

    def run(
        self,
        user_query: str,
        llm_output: str,
        max_rounds: int = 5,
        skip_workflow_rules: bool = False,
    ) -> SteeringHistory:
        """Tam otomatik sinyal + feedback döngüsü.

        LLMGeneratorProtocol.generate() gerektirir.
        Generator yoksa run_posthoc() kullanılmalıdır.

        Pipeline:
          1. Anchor analyze
          2. if clean → return
          3. Structured feedback → LLM re-generate
          4. repeat from 1
          5. if exhaustion → corrective fallback

        Args:
            user_query:     Kullanıcı sorgusu
            llm_output:     İlk LLM çıktısı
            max_rounds:     Maksimum tur sayısı
            skip_workflow_rules: Workflow rule'ları atlansın mı?

        Returns:
            SteeringHistory — tüm turların geçmişi
        """
        if not self.generator:
            raise ValueError(
                "SteeringLoop.run() requires a generator (LLMGeneratorProtocol). "
                "Use run_posthoc() for manual/corrective-only mode."
            )

        # Reset state
        self.exhaustion.reset()
        self.escalation.reset()
        self.history = SteeringHistory()

        current_output = llm_output
        content_type = classify_content(current_output, user_query)

        for round_num in range(max_rounds):
            # 1. Anchor analysis
            import time
            t0 = time.perf_counter()

            result = self.engine.process(
                user_query=user_query,
                llm_output=current_output,
                skip_workflow_rules=(
                    skip_workflow_rules or content_type == ContentType.EDUCATIONAL
                ),
            )

            # 2. Structured feedback
            feedback = StructuredFeedback.from_conflicts(
                result.corrections,  # Contains Correction objects
                content_type=content_type,
            ) if result.corrections else StructuredFeedback(feedback_text="")

            # Map corrections to conflicts
            conflicts = [c.conflict for c in result.corrections] if hasattr(result, 'corrections') else []

            latency = (time.perf_counter() - t0) * 1_000_000

            # 3. Exhaustion state
            severity_counts = {}
            for c in result.corrections:
                sev_name = c.conflict.severity.name if hasattr(c.conflict, 'severity') else "INFO"
                severity_counts[sev_name] = severity_counts.get(sev_name, 0) + 1

            exhaustion_state = self.exhaustion.update(
                severity_counts=severity_counts or {"NONE": 0},
                total_violations=len(result.corrections),
            )

            # 4. Escalation decision
            max_sev = max(
                (c.conflict.severity for c in result.corrections),
                default=Severity.NONE,
            )
            esc_decision = self.escalation.decide(
                max_severity=max_sev,
                exhaustion=exhaustion_state,
                round_number=round_num,
            )

            # 5. Record round
            steering_round = SteeringRound(
                round_number=round_num,
                llm_output=current_output,
                corrected=result.corrected if result.modified else current_output,
                conflicts=conflicts,
                feedback=feedback,
                correction_count=len(result.corrections),
                max_severity=max_sev,
                latency_us=latency,
                escalation=esc_decision,
                exhaustion=exhaustion_state,
            )
            self.history.rounds.append(steering_round)

            # 6. Check: clean → converged
            if not result.modified or len(result.corrections) == 0:
                logger.info(
                    "Anchor steering converged at round %d — clean response",
                    round_num,
                )
                break

            # 7. Check: exhaustion → corrective fallback
            if exhaustion_state.is_exhausted:
                logger.info(
                    "Anchor steering exhausted at round %d: %s",
                    round_num, exhaustion_state.reason,
                )
                # Apply corrective mode as fallback
                if esc_decision.level.value >= EscalationLevel.CORRECT.value and result.modified:
                    current_output = result.corrected
                break

            # 8. Prepare feedback for LLM and re-generate
            feedback_text = self.formatter.format_feedback(feedback)
            if not feedback_text:
                break

            # Build the re-generation prompt
            regen_prompt = self._build_regen_prompt(
                user_query, current_output, feedback_text,
                round_num,
            )

            # Call LLM
            current_output = self.generator.generate(
                prompt=user_query,
                context=regen_prompt,
            )

        return self.history

    def run_posthoc(
        self,
        user_query: str,
        llm_output: str,
        skip_workflow_rules: bool = False,
    ) -> tuple[str, StructuredFeedback, SteeringHistory]:
        """Post-hoc mod — sadece Anchor tek tur analizi + feedback.

        LLM yeniden üretimi yapılmaz. Mevcut output üzerinde çalışır.

        Returns:
            (corrected_output, structured_feedback, history)
        """
        self.exhaustion.reset()
        self.escalation.reset()
        self.history = SteeringHistory()

        content_type = classify_content(llm_output, user_query)

        result = self.engine.process(
            user_query=user_query,
            llm_output=llm_output,
            skip_workflow_rules=(
                skip_workflow_rules or content_type == ContentType.EDUCATIONAL
            ),
        )

        # Map corrections to conflicts
        corrections = result.corrections if hasattr(result, 'corrections') else []
        conflicts = [c.conflict for c in corrections]

        feedback = StructuredFeedback.from_conflicts(
            conflicts,
            content_type=content_type,
        ) if conflicts else StructuredFeedback(feedback_text="")

        # Round 0 record
        max_sev = max(
            (c.conflict.severity for c in corrections),
            default=Severity.NONE,
        )
        severity_counts = {}
        for c in corrections:
            sev_name = c.conflict.severity.name if hasattr(c.conflict, 'severity') else "INFO"
            severity_counts[sev_name] = severity_counts.get(sev_name, 0) + 1

        exhaustion_state = self.exhaustion.update(
            severity_counts=severity_counts or {"NONE": 0},
            total_violations=len(corrections),
        )
        esc_decision = self.escalation.decide(
            max_severity=max_sev,
            exhaustion=exhaustion_state,
            round_number=0,
        )

        self.history.rounds.append(SteeringRound(
            round_number=0,
            llm_output=llm_output,
            corrected=result.corrected if result.modified else llm_output,
            conflicts=conflicts,
            feedback=feedback,
            correction_count=len(corrections),
            max_severity=max_sev,
            latency_us=result.latency_us.get('total', 0),
            escalation=esc_decision,
            exhaustion=exhaustion_state,
        ))

        return result.corrected, feedback, self.history

    def _build_regen_prompt(
        self,
        user_query: str,
        current_output: str,
        feedback_text: str,
        round_number: int,
    ) -> str:
        """LLM'in yeniden üretimi için prompt'u hazırla.

        Format:
          [Original Query]
          
          [Previous Response]
          
          === Anchor Düzeltme Önerileri ===
          [Structured Feedback]
          
          Lütfen yanıtınızı bu düzeltme önerilerine göre düzenleyin.
        """
        parts = [
            f"## Kullanıcı Sorusu\n{user_query}",
            "",
            f"## Önceki Yanıtınız (Tur {round_number})",
            current_output,
            "",
            "=== ⚓ Anchor Düzeltme Önerileri ===",
            feedback_text,
            "",
            (
                "Yukarıdaki düzeltme önerilerini dikkate alarak "
                "yanıtınızı yeniden yazın. "
                "Önerilerdeki tüm düzeltmeleri uygulayın, "
                "ancak yanıtınızın doğal akışını koruyun. "
                "Anchor notlarını yanıta eklemeyin — yanıtınızı bizzat düzeltin."
            ),
        ]
        return "\n".join(parts)

    def summary(self) -> str:
        """Steering loop özeti."""
        return self.history.summary()
