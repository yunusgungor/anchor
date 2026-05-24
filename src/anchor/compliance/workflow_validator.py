"""
Anchor Workflow Governor — Step extraction, order/completeness validation.

Components:
  StepExtractor:        Extract which steps were executed from LLM output
  OrderValidator:       Validate step execution order
  CompletenessValidator: Validate mandatory steps are present and complete
  WorkflowIntegrator:   Connect to conflict detection, convert StepViolation → Conflict
"""

import logging
import re
from typing import Optional

from anchor import (
    Conflict, Step, StepViolation, Severity, ViolationType,
)

logger = logging.getLogger(__name__)


class StepExtractor:
    """
    Extract which steps were executed from LLM output.

    For each defined step, check if step.title or step.id appears in the output.
    Also detect ORDER: record the position where each matched step appears.
    """

    def __init__(self):
        self._total_calls = 0
        self._total_latency_us = 0

    def extract(self, llm_output: str, defined_steps: list[Step]) -> list[tuple[str, float, int]]:
        """
        Extract executed steps from LLM output.

        Args:
            llm_output: The raw LLM output text.
            defined_steps: List of Step definitions from the rule.

        Returns:
            List of (step_id, match_confidence, position) tuples,
            sorted by position in the text.
        """
        import time
        t0 = time.perf_counter()
        self._total_calls += 1

        if not defined_steps:
            return []

        output_lower = llm_output.lower()
        results: list[tuple[str, float, int]] = []

        for step in defined_steps:
            # Try matching by step.id first (e.g., "step-1")
            id_lower = step.id.lower()
            # Try matching by step.title
            title_lower = step.title.lower()

            best_pos = -1
            best_confidence = 0.0

            # Check step title
            if title_lower in output_lower:
                pos = output_lower.index(title_lower)
                confidence = min(1.0, 0.5 + len(title_lower.split()) * 0.15)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_pos = pos

            # Check step id (weaker signal)
            if id_lower in output_lower and len(id_lower) >= 3:
                pos = output_lower.index(id_lower)
                confidence = 0.4  # IDs are weaker match
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_pos = pos

            # Check if step title words appear adjacent or near each other
            if best_confidence < 0.7 and len(title_lower.split()) > 1:
                words = title_lower.split()
                # Find first occurrence where most words appear nearby
                first_word_idx = -1
                all_found = True
                positions = []
                for w in words:
                    if len(w) < 3:
                        continue
                    idx = output_lower.find(w)
                    if idx < 0:
                        all_found = False
                        break
                    positions.append(idx)
                if all_found and len(positions) >= 2:
                    # Words found but maybe scattered — still a match
                    avg_pos = sum(positions) / len(positions)
                    span = max(positions) - min(positions)
                    if span < 100:  # Within reasonable distance
                        confidence = 0.5 + (0.3 * (1.0 - min(1.0, span / 100.0)))
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_pos = min(positions)

            if best_confidence > 0.0:
                results.append((step.id, best_confidence, best_pos))

        # Sort by position in text
        results.sort(key=lambda x: x[2])

        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000

        return results

    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls


class OrderValidator:
    """
    Validate step execution order.

    Check if step A depends on step B, A must appear after B in the output.
    Generates ORDER_VIOLATION violations with expected_order and actual_order.
    """

    def validate(
        self,
        executed_steps: list[tuple[str, float, int]],
        defined_steps: list[Step],
    ) -> list[StepViolation]:
        """
        Validate the order of executed steps.

        Args:
            executed_steps: List of (step_id, confidence, position) from StepExtractor.
            defined_steps: List of Step definitions from the rule.

        Returns:
            List of StepViolation for order violations.
        """
        if not executed_steps or not defined_steps:
            return []

        violations: list[StepViolation] = []

        # Build lookup maps
        step_map: dict[str, Step] = {s.id: s for s in defined_steps}
        exec_map: dict[str, int] = {sid: pos for sid, _, pos in executed_steps}
        exec_positions: dict[str, int] = {}
        for idx, (sid, _, pos) in enumerate(executed_steps):
            exec_positions[sid] = idx

        # Check depends_on constraints
        for step_id, _, position in executed_steps:
            step = step_map.get(step_id)
            if not step or not step.depends_on:
                continue

            for dep_id in step.depends_on:
                if dep_id in exec_map:
                    dep_position = exec_map[dep_id]
                    if position < dep_position:
                        # Step appears BEFORE its dependency
                        step_obj = step_map.get(step_id)
                        dep_obj = step_map.get(dep_id)
                        violations.append(StepViolation(
                            violation_type=ViolationType.ORDER_VIOLATION,
                            step_id=step_id,
                            step_title=step_obj.title if step_obj else step_id,
                            severity=Severity.ERROR,
                            message=(
                                f"Adım '{step_id}' ({step_obj.title if step_obj else ''}) "
                                f"'{dep_id}' adımından önce gelmiş, "
                                f"fakat '{dep_id}' adımına bağımlı."
                            ),
                            fix_suggestion=(
                                f"'{step_id}' adımını '{dep_id}' adımından sonraya taşı."
                            ),
                            expected_order=dep_position,
                            actual_order=position,
                            confidence=0.9,
                        ))

        return violations

    @property
    def avg_latency_us(self) -> float:
        return 0  # Pure computation


class CompletenessValidator:
    """
    Validate mandatory steps are present and complete.

    Checks:
      - All mandatory steps are present → MISSING_STEP violations
      - Steps with checks — each check keyword should appear in LLM output
        matched to that step → INCOMPLETE_STEP violations
    """

    def validate(
        self,
        executed_steps: list[tuple[str, float, int]],
        defined_steps: list[Step],
        llm_output: str,
    ) -> list[StepViolation]:
        """
        Validate completeness of executed steps.

        Args:
            executed_steps: List of (step_id, confidence, position) from StepExtractor.
            defined_steps: List of Step definitions from the rule.
            llm_output: The raw LLM output text.

        Returns:
            List of StepViolation for missing/incomplete steps.
        """
        if not defined_steps:
            return []

        violations: list[StepViolation] = []
        executed_ids = {sid for sid, _, _ in executed_steps}
        output_lower = llm_output.lower()
        step_map: dict[str, Step] = {s.id: s for s in defined_steps}

        for step in defined_steps:
            if step.mandatory and step.id not in executed_ids:
                # Missing mandatory step
                violations.append(StepViolation(
                    violation_type=ViolationType.MISSING_STEP,
                    step_id=step.id,
                    step_title=step.title,
                    severity=Severity.ERROR,
                    message=f"Zorunlu adım '{step.title}' ({step.id}) LLM çıktısında bulunamadı.",
                    fix_suggestion=f"Lütfen '{step.title}' adımını ekleyin.",
                    confidence=0.95,
                ))
                continue

            # Check step completeness (checks)
            if step.id in executed_ids and step.checks:
                missing_checks = []
                for check in step.checks:
                    check_lower = check.lower().strip()
                    # Look for check keyword in the vicinity of the step match
                    # For simplicity, search entire output
                    if check_lower not in output_lower:
                        missing_checks.append(check)

                if missing_checks:
                    violations.append(StepViolation(
                        violation_type=ViolationType.INCOMPLETE_STEP,
                        step_id=step.id,
                        step_title=step.title,
                        severity=Severity.WARNING,
                        message=(
                            f"Adım '{step.title}' eksik uygulanmış. "
                    f"Eksik kontroller: {', '.join(missing_checks)}"
                        ),
                        fix_suggestion=(
                            f"'{step.title}' adımında şu kontrolleri ekleyin: "
                            f"{', '.join(missing_checks)}"
                        ),
                        confidence=0.85,
                    ))

        return violations


class WorkflowIntegrator:
    """
    Connects workflow validation to conflict detection.

    Wraps StepExtractor + OrderValidator + CompletenessValidator,
    converts StepViolation to Conflict objects.
    """

    def __init__(self):
        self.extractor = StepExtractor()
        self.order_validator = OrderValidator()
        self.completeness_validator = CompletenessValidator()
        self._last_step_violations: list[StepViolation] = []

    @property
    def last_step_violations(self) -> list[StepViolation]:
        return self._last_step_violations

    def validate(
        self,
        llm_output: str,
        rule,
    ) -> tuple[list[Conflict], list[StepViolation]]:
        """
        Run full workflow validation and return both conflicts and step violations.

        Args:
            llm_output: The raw LLM output text.
            rule: Rule object with .steps attribute (list[Step]).

        Returns:
            (conflicts, step_violations) tuple.
        """
        defined_steps: list[Step] = getattr(rule, 'steps', []) or []
        if not defined_steps:
            return [], []

        # 1. Extract executed steps from LLM output
        executed_steps = self.extractor.extract(llm_output, defined_steps)

        # 2. Validate order
        order_violations = self.order_validator.validate(executed_steps, defined_steps)

        # 3. Validate completeness
        completeness_violations = self.completeness_validator.validate(
            executed_steps, defined_steps, llm_output
        )

        # Combine all step violations
        all_violations = order_violations + completeness_violations
        self._last_step_violations = all_violations

        # 4. Convert StepViolation to Conflict objects
        conflicts = []
        for sv in all_violations:
            severity = sv.severity
            conflict = Conflict(
                rule_id=rule.id if hasattr(rule, 'id') else 'workflow',
                topic=rule.topic if hasattr(rule, 'topic') else 'workflow',
                severity=severity,
                llm_claim=f"[{sv.violation_type.value}] {sv.step_title}: {sv.message}",
                kb_fact=sv.fix_suggestion,
                patch_position=0,
                confidence=sv.confidence,
                violation_type=sv.violation_type,
                step_violation=sv,
            )
            conflicts.append(conflict)

        return conflicts, all_violations
