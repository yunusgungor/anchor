"""
Anchor v5.0 — Active Steering Tests.

Test Strategy:
  - Unit tests for each component (feedback, exhaustion, escalation, loop)
  - Integration tests with AnchorEngine
  - Edge cases: empty, no violations, all severity levels
"""

import pytest
from anchor import Conflict, Severity
from anchor.steering.feedback import (
    StructuredFeedback,
    FeedbackItem,
    GaaAFormatter,
    ContentType,
    classify_content,
)
from anchor.steering.exhaustion import (
    AdaptiveExhaustion,
    compute_violation_complexity,
    compute_max_stagnation,
)
from anchor.steering.escalation import (
    EscalationEngine,
    EscalationLevel,
)
from anchor.steering.loop import (
    SteeringRound,
    SteeringHistory,
)


# ══════════════════════════════════════════════
# Content Type Classification
# ══════════════════════════════════════════════

class TestClassifyContent:
    def test_educational_question(self):
        ct = classify_content(
            "TDD, Test Driven Development demektir. Örneğin önce RED test yazılır, "
            "ardından implementasyon yapılır. Bu şekilde döngü adım adım devam eder.",
            "TDD nedir?",
        )
        assert ct == ContentType.EDUCATIONAL

    def test_factual_output(self):
        ct = classify_content("NPX1, SKY130'da üretilir.", "NPX1 nedir?")
        assert ct == ContentType.FACTUAL

    def test_creative_output(self):
        ct = classify_content(
            "A magical story begins in a hidden valley full of wonder and adventure...",
            "bir hikaye yaz",
        )
        assert ct == ContentType.CREATIVE

    def test_creative_output_from_query_only(self):
        """Query'de creative marker varsa, output kısa olsa bile CREATIVE."""
        ct = classify_content("Short answer.", "bana bir şiir yaz")
        assert ct == ContentType.CREATIVE

    def test_procedural_output(self):
        ct = classify_content(
            "Önce A adımı yapılır. Sonra B adımı gelir. Ardından C kontrol edilir. "
            "Son olarak D uygulanır.",
            "",
        )
        assert ct == ContentType.PROCEDURAL

    def test_empty_output(self):
        ct = classify_content("", "")
        assert ct == ContentType.FACTUAL


# ══════════════════════════════════════════════
# Structured Feedback
# ══════════════════════════════════════════════

class TestFeedbackItem:
    def test_from_conflict_critical(self):
        conflict = Conflict(
            rule_id="tdd-cycle", topic="TDD",
            severity=Severity.CRITICAL,
            llm_claim="Önce kodu yaz, sonra test et.",
            kb_fact="Önce RED test yaz, sonra implement et.",
            confidence=0.92,
        )
        item = FeedbackItem.from_conflict(conflict)
        assert item.rule == "tdd-cycle"
        assert item.severity == "CRITICAL"
        assert item.confidence == 0.92
        assert "Önce RED test" in item.correction

    def test_from_conflict_info(self):
        conflict = Conflict(
            rule_id="clean-arch", topic="Clean Architecture",
            severity=Severity.INFO,
            llm_claim="Controller katmanı",
            kb_fact="Controller presentation katmanındadır.",
        )
        item = FeedbackItem.from_conflict(conflict)
        assert item.severity == "INFO"

    def test_gaaa_string_format(self):
        conflict = Conflict(
            rule_id="test-rule", topic="Test",
            severity=Severity.ERROR,
            llm_claim="Yanlış bilgi.",
            kb_fact="Doğru bilgi.",
            confidence=0.85,
        )
        item = FeedbackItem.from_conflict(conflict)
        text = item.to_gaaa_string()
        assert "test-rule" in text
        assert "Doğrusu:" in text
        assert "Severity:" in text
        assert "Güven:" in text


class TestStructuredFeedback:
    def test_empty_from_no_conflicts(self):
        fb = StructuredFeedback.from_conflicts([])
        assert fb.total_violations == 0
        assert fb.feedback_text == ""

    def test_dedup_same_rule_same_violation(self):
        c1 = Conflict(rule_id="r1", topic="t", severity=Severity.WARNING,
                      llm_claim="claim1", kb_fact="fact1", confidence=0.8)
        c2 = Conflict(rule_id="r1", topic="t", severity=Severity.WARNING,
                      llm_claim="claim1", kb_fact="fact1", confidence=0.8)
        fb = StructuredFeedback.from_conflicts([c1, c2])
        assert fb.total_violations == 1  # Dedup

    def test_multiple_different_rules(self):
        c1 = Conflict(rule_id="r1", topic="t1", severity=Severity.WARNING,
                      llm_claim="claim1", kb_fact="fact1")
        c2 = Conflict(rule_id="r2", topic="t2", severity=Severity.ERROR,
                      llm_claim="claim2", kb_fact="fact2")
        fb = StructuredFeedback.from_conflicts([c1, c2])
        assert fb.total_violations == 2
        assert fb.rule_count == 2

    def test_max_severity_critical(self):
        c1 = Conflict(rule_id="r1", topic="t", severity=Severity.INFO,
                      llm_claim="c1", kb_fact="f1")
        c2 = Conflict(rule_id="r2", topic="t", severity=Severity.CRITICAL,
                      llm_claim="c2", kb_fact="f2")
        fb = StructuredFeedback.from_conflicts([c1, c2])
        assert fb.max_severity == Severity.CRITICAL

    def test_severity_sorting(self):
        """Feedback text'te CRITICAL önce gelmeli."""
        c1 = Conflict(rule_id="r1", topic="t", severity=Severity.INFO,
                      llm_claim="info claim", kb_fact="info fact")
        c2 = Conflict(rule_id="r2", topic="t", severity=Severity.CRITICAL,
                      llm_claim="critical claim", kb_fact="critical fact")
        fb = StructuredFeedback.from_conflicts([c1, c2])
        text = fb.feedback_text
        # CRITICAL should appear before INFO
        crit_pos = text.index("CRITICAL")
        info_pos = text.index("INFO")
        assert crit_pos < info_pos


class TestGaaAFormatter:
    def test_empty_feedback(self):
        formatter = GaaAFormatter()
        fb = StructuredFeedback(feedback_text="")
        result = formatter.format_feedback(fb)
        assert result == ""

    def test_format_with_items(self):
        formatter = GaaAFormatter()
        c = Conflict(rule_id="tdd", topic="TDD", severity=Severity.ERROR,
                     llm_claim="wrong", kb_fact="correct", confidence=0.9)
        fb = StructuredFeedback.from_conflicts([c])
        result = formatter.format_feedback(fb)
        assert "düzeltme önerisi" in result
        assert "tdd" in result
        assert "correct" in result

    def test_format_to_dict(self):
        formatter = GaaAFormatter()
        c = Conflict(rule_id="r1", topic="t", severity=Severity.WARNING,
                     llm_claim="c1", kb_fact="f1", confidence=0.7)
        result = formatter.format_to_dict([c])
        assert len(result) == 1
        assert result[0]["rule"] == "r1"
        assert result[0]["severity"] == "WARNING"
        assert result[0]["confidence"] == 0.7


# ══════════════════════════════════════════════
# Adaptive Exhaustion
# ══════════════════════════════════════════════

class TestExhaustionHelpers:
    def test_compute_complexity(self):
        c = compute_violation_complexity({"CRITICAL": 2, "WARNING": 1}, 3)
        # (4*2 + 2*1) + 3 = 8 + 2 + 3 = 13
        assert c == 13

    def test_compute_complexity_empty(self):
        c = compute_violation_complexity({}, 0)
        assert c == 0

    def test_max_stagnation_base(self):
        assert compute_max_stagnation(0) == 2  # BASE_MAX_STAGNATION

    def test_max_stagnation_extra(self):
        assert compute_max_stagnation(10) == 2 + int(10 / 5)  # 10/5=2 extra
        assert compute_max_stagnation(10) == 4


class TestAdaptiveExhaustion:
    def test_initial_state(self):
        e = AdaptiveExhaustion()
        assert e.round_count == 0
        assert e.history == []

    def test_first_update_no_exhaustion(self):
        e = AdaptiveExhaustion()
        state = e.update({"INFO": 1}, 1)
        assert not state.is_exhausted
        assert state.round_number == 0
        assert state.stagnation_count == 0

    def test_improvement_resets_stagnation(self):
        e = AdaptiveExhaustion()
        # Round 0: 10 violations
        e.update({"ERROR": 3, "WARNING": 1}, 4)
        # Round 1: 1 violation (75% improvement → reset)
        state = e.update({"INFO": 1}, 1)
        assert state.stagnation_count == 0  # Reset because improvement > 15%

    def test_stagnation_increments(self):
        e = AdaptiveExhaustion()
        # Round 0: 5 violations
        e.update({"WARNING": 3}, 3)
        # Round 1: 5 violations (0% improvement → +1 stagnation)
        state = e.update({"WARNING": 3}, 3)
        assert state.stagnation_count == 1

    def test_exhaustion_trigger(self):
        e = AdaptiveExhaustion()
        # Round 0: 3 violations
        e.update({"WARNING": 3}, 3)  # stagnation=0
        # Round 1: 3 violations (same)
        e.update({"WARNING": 3}, 3)  # stagnation=1
        # Round 2: 3 violations (same)
        e.update({"WARNING": 3}, 3)  # stagnation=2
        # Round 3: 3 violations (same) — stagnation=3 >= max_stag(3)?
        state = e.update({"WARNING": 3}, 3)  # stagnation=3
        # complexity = (2*3)+3 = 9, max_stagnation = 2 + int(9/5) = 3
        # stagnation=3 >= 3 → exhausted
        assert state.is_exhausted

    def test_absolute_max_rounds(self):
        e = AdaptiveExhaustion(absolute_max_rounds=3)
        # 3 rounds max
        for i in range(3):
            e.update({"WARNING": 2}, 2)
        # Round 3 should be exhausted due to absolute max
        state = e.update({"WARNING": 2}, 2)
        assert state.is_exhausted
        assert "Maksimum" in state.reason

    def test_complexity_extra_rounds(self):
        """High complexity violations get more rounds before exhaustion."""
        e = AdaptiveExhaustion()
        # High complexity: 10 violations + CRITICAL×2 = (4*2)*2 + 10? Let me calculate...
        # compute_violation_complexity({"CRITICAL": 2}, 2) = (4*2) + 2 = 10
        # max_stagnation = 2 + int(10/5) = 4
        # So we need 5 consecutive rounds without improvement to exhaust
        for i in range(5):
            e.update({"CRITICAL": 2}, 2)
        state = e.update({"CRITICAL": 2}, 2)
        assert state.is_exhausted

    def test_reset(self):
        e = AdaptiveExhaustion()
        e.update({"WARNING": 3}, 3)
        e.update({"WARNING": 3}, 3)
        assert e.round_count == 2
        e.reset()
        assert e.round_count == 0
        assert e.history == []

    def test_summary_empty(self):
        e = AdaptiveExhaustion()
        assert "Henüz" in e.summary()

    def test_summary_with_rounds(self):
        e = AdaptiveExhaustion()
        e.update({"WARNING": 1}, 1)
        summary = e.summary()
        assert "Toplam" in summary or "Tur" in summary


# ══════════════════════════════════════════════
# Escalation
# ══════════════════════════════════════════════

class TestEscalationEngine:
    def test_start_at_advise(self):
        eng = EscalationEngine()
        assert eng.current_level == EscalationLevel.ADVISE

    def test_first_round_info(self):
        eng = EscalationEngine()
        dec = eng.decide(max_severity=Severity.INFO, round_number=0)
        # INFO → minimum ADVISE
        assert dec.level.value >= EscalationLevel.ADVISE.value

    def test_first_round_critical(self):
        eng = EscalationEngine()
        dec = eng.decide(max_severity=Severity.CRITICAL, round_number=0)
        # CRITICAL → minimum CORRECT (level 4)
        assert dec.level.value >= EscalationLevel.CORRECT.value

    def test_exhaustion_escalates(self):
        eng = EscalationEngine()
        dec = eng.decide(max_severity=Severity.WARNING, round_number=0)
        level_before = dec.level

        # Simulate exhaustion
        from anchor.steering.exhaustion import ExhaustionState
        exhausted = ExhaustionState(
            round_number=1, violation_count=5, complexity=10,
            improvement_rate=0.0, stagnation_count=3,
            max_stagnation=2, is_exhausted=True,
            reason="Test exhaustion",
        )
        dec2 = eng.decide(
            max_severity=Severity.WARNING,
            exhaustion=exhausted,
            round_number=1,
        )
        # Should have bumped up at least one level
        assert dec2.level.value >= level_before.value

    def test_escalation_to_escalate(self):
        """Repeated exhaustion should eventually reach ESCALATE."""
        eng = EscalationEngine()

        # First exhaustion at ADVISE
        from anchor.steering.exhaustion import ExhaustionState

        for r in range(5):
            exhausted = ExhaustionState(
                round_number=r, violation_count=5, complexity=10,
                improvement_rate=0.0, stagnation_count=3,
                max_stagnation=2, is_exhausted=True,
                reason=f"Exhaustion round {r}",
            )
            dec = eng.decide(
                max_severity=Severity.WARNING,
                exhaustion=exhausted,
                round_number=r,
            )

        # Should eventually reach ESCALATE
        assert dec.level == EscalationLevel.ESCALATE or dec.fallback

    def test_reset(self):
        eng = EscalationEngine()
        eng.decide(max_severity=Severity.ERROR, round_number=0)
        eng.reset()
        assert eng.current_level == EscalationLevel.ADVISE
        assert eng.rounds_at_level == 0

    def test_reset_with_custom_start(self):
        eng = EscalationEngine()
        eng.decide(max_severity=Severity.ERROR, round_number=0)
        eng.reset(start_from=EscalationLevel.CORRECT)
        assert eng.current_level == EscalationLevel.CORRECT


# ══════════════════════════════════════════════
# Steering History
# ══════════════════════════════════════════════

class TestSteeringHistory:
    def test_empty_history(self):
        h = SteeringHistory()
        assert h.total_rounds == 0
        assert not h.is_converged

    def test_converged(self):
        h = SteeringHistory()
        # Add a clean round
        fb = StructuredFeedback(feedback_text="")
        round0 = SteeringRound(
            round_number=0,
            llm_output="test",
            corrected="test",
            conflicts=[],
            feedback=fb,
            correction_count=0,
            max_severity=Severity.NONE,
            latency_us=100,
        )
        h.rounds.append(round0)
        assert h.is_converged
        assert h.final_violation_count == 0

    def test_not_converged(self):
        h = SteeringHistory()
        c = Conflict(rule_id="r1", topic="t", severity=Severity.ERROR,
                     llm_claim="c1", kb_fact="f1")
        fb = StructuredFeedback.from_conflicts([c])
        round0 = SteeringRound(
            round_number=0,
            llm_output="test",
            corrected="corrected",
            conflicts=[c],
            feedback=fb,
            correction_count=1,
            max_severity=Severity.ERROR,
            latency_us=200,
        )
        h.rounds.append(round0)
        assert not h.is_converged
        assert h.initial_violation_count == 1
