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
from difflib import SequenceMatcher
from typing import Optional

from anchor import (
    Conflict, Step, StepViolation, Severity, ViolationType,
)
from anchor.config import (
    WF_ALIAS_CONFIDENCE,
    WF_TERM_MAP_CONFIDENCE,
    WF_SEMANTIC_CONFIDENCE_MIN,
    WF_SEMANTIC_SENTENCE_MIN_LEN,
    WF_CHECK_FUZZY_MAX_DISTANCE,
    WF_COMPOUND_CHECK_MIN_WORDS,
)

logger = logging.getLogger(__name__)


STEP_TERM_MAP: dict[str, list[str]] = {
    "pr'yi incele": ['review pr', 'review pull request', 'examine diff', 'pull request review', 'reviewed the pr'],
    'iş mantığı ve doğruluk kontrolü': ['business logic', 'correctness', 'edge case review', 'boundary checks', 'checked business logic'],
    'kod kalitesi ve standartlar': ['code quality', 'style', 'naming', 'complexity', 'solid', 'maintainability'],
    'güvenlik taraması': ['security review', 'security scan', 'auth review', 'xss', 'injection', 'reviewed security implications'],
    'test kapsamı doğrulama': ['test coverage', 'coverage review', 'tests checked', 'assertions reviewed', 'validated test coverage'],
    'onayla veya değişiklik iste': ['approve', 'request changes', 'lgtm', 'commented changes', 'approved the changes'],
    'kök neden analizi': ['root cause', '5 whys', 'traceback analysis', 'analyzed the root cause'],
    'postmortem yaz ve önlem al': ['postmortem', 'blameless retro', 'action items', 'prevent recurrence', 'wrote a postmortem with action items'],
    'kırmızı: başarısız test yaz': ['write failing test', 'red phase', 'failing spec', 'started with a failing test'],
    'yeşil: geçmesi için minimal kod yaz': ['minimal code', 'green phase', 'make test pass', 'wrote minimal code'],
    'refactor': ['refactor', 'eliminate duplication', 'simplify design', 'improve structure', 'refactored to simplify the design'],
    "story'i anla": ['understand story', 'acceptance criteria', 'definition of done', 'read the story and acceptance criteria'],
    'test planı oluştur': ['test plan', 'test strategy', 'scenarios', 'edge cases', 'created a test plan'],
    'pull request oluştur': ['open pr', 'create pr', 'submit pull request', 'opened a pr'],
    'versiyon numarasını güncelle': ['version bump', 'semver', 'update version', 'bumped the version'],
    'git tag oluştur': ['git tag', 'annotated tag', 'signed tag', 'tagged the release'],
    'production dağıtımı': ['production deploy', 'deploy to prod', 'canary rollout', 'deployed to production'],
    'ihlali tespit et ve bildir': ['detect incident', 'alert fired', 'incident reported', 'detected the production incident'],
    'etkiyi ve şiddeti değerlendir': ['assess severity', 'sev1', 'sev2', 'impact analysis', 'assessed severity'],
    'etkiyi azalt': ['mitigate', 'rollback', 'hotfix', 'stop the bleed', 'rolled back to mitigate'],
}

CHECK_ALIAS_MAP: dict[str, list[str]] = {
    'pull request': ['pr', 'pull request'],
    'pr': ['pr', 'pull request'],
    'continuous integration': ['ci', 'continuous integration'],
    'ci': ['ci', 'continuous integration'],
    'architecture decision record': ['adr', 'architecture decision record'],
    'adr': ['adr', 'architecture decision record'],
    'end-to-end': ['e2e', 'end-to-end', 'smoke'],
    'e2e': ['e2e', 'end-to-end', 'smoke'],
    'root cause': ['root cause', 'kök neden'],
    'kök neden': ['root cause', 'kök neden'],
    'postmortem': ['postmortem', 'post-mortem', 'retro'],
    'rollback': ['rollback', 'roll back'],
    'sign-off': ['sign-off', 'signoff', 'approval'],
    'release notes': ['release notes', 'changelog'],
}


def _normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s/-]', ' ', text.lower())).strip()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            ins = curr[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (ca != cb)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]


def _expand_check_aliases(check: str) -> list[str]:
    check_lower = check.lower().strip()
    expanded = [check_lower]
    for key, vals in CHECK_ALIAS_MAP.items():
        if check_lower == key or check_lower in vals:
            for v in vals:
                if v not in expanded:
                    expanded.append(v)
    return expanded


def _match_check_variant(output_lower: str, variant: str) -> bool:
    variant = _normalize_text(variant)
    if not variant:
        return False
    if re.search(r'\b' + re.escape(variant) + r'\b', output_lower):
        return True
    if len(variant) >= 3 and re.search(r'\b' + re.escape(variant) + r'[a-z]*\b', output_lower, re.IGNORECASE):
        return True
    if ' ' in variant and len(variant.split()) >= WF_COMPOUND_CHECK_MIN_WORDS:
        parts = [p for p in variant.split() if len(p) >= 2]
        return all(re.search(r'\b' + re.escape(p) + r'[a-z]*\b', output_lower, re.IGNORECASE) for p in parts)
    return False


def _match_check_fuzzy(output_lower: str, variant: str) -> bool:
    words = re.findall(r'\b\w+[/-]?\w*\b', output_lower)
    target = _normalize_text(variant)
    if not target:
        return False
    if ' ' in target:
        candidates = [' '.join(words[i:i + len(target.split())]) for i in range(max(0, len(words) - len(target.split()) + 1))]
    else:
        candidates = words
    for cand in candidates:
        if _levenshtein(target, cand) <= WF_CHECK_FUZZY_MAX_DISTANCE:
            return True
        if SequenceMatcher(None, target, cand).ratio() >= 0.88:
            return True
    return False


class StepExtractor:
    """
    Extract which steps were executed from LLM output.

    For each defined step, check if step.title or step.id appears in the output.
    Also detect ORDER: record the position where each matched step appears.
    """

    def __init__(self):
        self._total_calls = 0
        self._total_latency_us = 0

    def _semantic_match(self, llm_output: str, candidates: list[str]) -> tuple[float, int]:
        best_conf = 0.0
        best_pos = -1
        if len(llm_output) < WF_SEMANTIC_SENTENCE_MIN_LEN:
            return best_conf, best_pos
        sentences = [s.strip() for s in re.split(r'[.!?\n]+', llm_output) if len(s.strip()) >= WF_SEMANTIC_SENTENCE_MIN_LEN]
        for cand in candidates:
            cand_norm = _normalize_text(cand)
            if not cand_norm:
                continue
            for sent in sentences:
                sent_norm = _normalize_text(sent)
                ratio = SequenceMatcher(None, cand_norm, sent_norm).ratio()
                if ratio >= WF_SEMANTIC_CONFIDENCE_MIN and ratio > best_conf:
                    best_conf = ratio
                    best_pos = llm_output.lower().find(sent.lower())
        return best_conf, best_pos

    def extract(self, llm_output: str, defined_steps: list[Step]) -> list[tuple[str, float, int]]:
        import time
        t0 = time.perf_counter()
        self._total_calls += 1

        if not defined_steps:
            return []

        output_lower = _normalize_text(llm_output)
        results: list[tuple[str, float, int]] = []

        for step in defined_steps:
            id_lower = _normalize_text(step.id)
            title_lower = _normalize_text(step.title)

            best_pos = -1
            best_confidence = 0.0

            if title_lower in output_lower:
                pos = output_lower.index(title_lower)
                confidence = min(1.0, 0.5 + len(title_lower.split()) * 0.15)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_pos = pos

            if id_lower in output_lower and len(id_lower) >= 3:
                pos = output_lower.index(id_lower)
                confidence = 0.4
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_pos = pos

            for alias in getattr(step, 'aliases', []) or []:
                alias_lower = _normalize_text(alias)
                if alias_lower and alias_lower in output_lower:
                    pos = output_lower.index(alias_lower)
                    confidence = WF_ALIAS_CONFIDENCE
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_pos = pos

            title_norm = title_lower
            for key, vals in STEP_TERM_MAP.items():
                if key in title_norm or title_norm in key:
                    for variant in vals:
                        variant_norm = _normalize_text(variant)
                        if variant_norm and variant_norm in output_lower:
                            pos = output_lower.index(variant_norm)
                            confidence = WF_TERM_MAP_CONFIDENCE
                            if confidence > best_confidence:
                                best_confidence = confidence
                                best_pos = pos

            if best_confidence < 0.7 and len(title_lower.split()) > 1:
                words = title_lower.split()
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
                    span = max(positions) - min(positions)
                    if span < 100:
                        confidence = 0.5 + (0.3 * (1.0 - min(1.0, span / 100.0)))
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_pos = min(positions)

            if best_confidence < 0.5 and step.checks:
                check_words_found = 0.0
                for check in step.checks:
                    matched = False
                    for variant in _expand_check_aliases(check):
                        if _match_check_variant(output_lower, variant):
                            matched = True
                            check_words_found += 1.0
                            break
                        if _match_check_fuzzy(output_lower, variant):
                            matched = True
                            check_words_found += 0.75
                            break
                coverage = check_words_found / max(1, len(step.checks))
                if coverage >= 0.34:
                    confidence = 0.35 + (0.45 * min(1.0, coverage))
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_pos = 0 if best_pos < 0 else best_pos

            if best_confidence < WF_SEMANTIC_CONFIDENCE_MIN:
                semantic_candidates = [step.title] + list(getattr(step, 'aliases', []) or [])
                for key, vals in STEP_TERM_MAP.items():
                    if key in title_norm or title_norm in key:
                        semantic_candidates.extend(vals)
                sem_conf, sem_pos = self._semantic_match(llm_output, semantic_candidates)
                if sem_conf > best_confidence:
                    best_confidence = sem_conf
                    best_pos = sem_pos

            if best_confidence > 0.0:
                results.append((step.id, best_confidence, best_pos))

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
    def validate(
        self,
        executed_steps: list[tuple[str, float, int]],
        defined_steps: list[Step],
    ) -> list[StepViolation]:
        if not executed_steps or not defined_steps:
            return []

        violations: list[StepViolation] = []
        step_map: dict[str, Step] = {s.id: s for s in defined_steps}
        exec_map: dict[str, int] = {sid: pos for sid, _, pos in executed_steps}

        for step_id, _, position in executed_steps:
            step = step_map.get(step_id)
            if not step or not step.depends_on:
                continue
            for dep_id in step.depends_on:
                if dep_id in exec_map:
                    dep_position = exec_map[dep_id]
                    if position < dep_position:
                        step_obj = step_map.get(step_id)
                        violations.append(StepViolation(
                            violation_type=ViolationType.ORDER_VIOLATION,
                            step_id=step_id,
                            step_title=step_obj.title if step_obj else step_id,
                            severity=Severity.ERROR,
                            message=(
                                f"Adım '{step_id}' ({step_obj.title if step_obj else ''}) "
                                f"'{dep_id}' adımından önce gelmiş, fakat '{dep_id}' adımına bağımlı."
                            ),
                            fix_suggestion=f"'{step_id}' adımını '{dep_id}' adımından sonraya taşı.",
                            expected_order=dep_position,
                            actual_order=position,
                            confidence=0.9,
                        ))
        return violations

    @property
    def avg_latency_us(self) -> float:
        return 0


class CompletenessValidator:
    def validate(
        self,
        executed_steps: list[tuple[str, float, int]],
        defined_steps: list[Step],
        llm_output: str,
    ) -> list[StepViolation]:
        if not defined_steps:
            return []

        violations: list[StepViolation] = []
        executed_ids = {sid for sid, _, _ in executed_steps}
        output_lower = _normalize_text(llm_output)

        for step in defined_steps:
            if step.mandatory and step.id not in executed_ids:
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

            if step.id in executed_ids and step.checks:
                missing_checks = []
                matched_score = 0.0
                for check in step.checks:
                    matched = False
                    for variant in _expand_check_aliases(check):
                        if _match_check_variant(output_lower, variant):
                            matched = True
                            matched_score += 1.0
                            break
                        if _match_check_fuzzy(output_lower, variant):
                            matched = True
                            matched_score += 0.75
                            break
                    if not matched:
                        missing_checks.append(check)

                coverage = matched_score / max(1, len(step.checks))
                if missing_checks and coverage < 0.8:
                    severity = Severity.WARNING if coverage >= 0.5 else Severity.ERROR
                    confidence = 0.7 if coverage >= 0.5 else 0.85
                    violations.append(StepViolation(
                        violation_type=ViolationType.INCOMPLETE_STEP,
                        step_id=step.id,
                        step_title=step.title,
                        severity=severity,
                        message=(
                            f"Adım '{step.title}' eksik uygulanmış. "
                            f"Eksik kontroller: {', '.join(missing_checks)}"
                        ),
                        fix_suggestion=(
                            f"'{step.title}' adımında şu kontrolleri ekleyin: "
                            f"{', '.join(missing_checks)}"
                        ),
                        confidence=confidence,
                    ))
        return violations


class WorkflowIntegrator:
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
        diagram_flows: list[list[str]] | None = None,
    ) -> tuple[list[Conflict], list[StepViolation]]:
        defined_steps: list[Step] = getattr(rule, 'steps', []) or []

        if not defined_steps and diagram_flows:
            synthetic_steps = []
            step_id_counter = 0
            for flow in diagram_flows:
                for node in flow:
                    step_id_counter += 1
                    synthetic_steps.append(Step(
                        id=f"diagram-step-{step_id_counter}",
                        title=node,
                        mandatory=True,
                    ))
            if synthetic_steps:
                defined_steps = synthetic_steps
                logger.debug("Created %d synthetic steps from diagram flows", len(synthetic_steps))

        if not defined_steps:
            return [], []

        executed_steps = self.extractor.extract(llm_output, defined_steps)
        order_violations = self.order_validator.validate(executed_steps, defined_steps)
        completeness_violations = self.completeness_validator.validate(executed_steps, defined_steps, llm_output)

        all_violations = order_violations + completeness_violations
        self._last_step_violations = all_violations

        conflicts = []
        for sv in all_violations:
            conflict = Conflict(
                rule_id=rule.id if hasattr(rule, 'id') else 'workflow',
                topic=rule.topic if hasattr(rule, 'topic') else 'workflow',
                severity=sv.severity,
                llm_claim=f"[{sv.violation_type.value}] {sv.step_title}: {sv.message}",
                kb_fact=sv.fix_suggestion,
                patch_position=0,
                confidence=sv.confidence,
                violation_type=sv.violation_type,
                step_violation=sv,
            )
            conflicts.append(conflict)

        step_index_map = {s.id: i for i, s in enumerate(defined_steps)}
        conflicts.sort(key=lambda c: (
            -c.severity.value,
            -(step_index_map.get(c.step_violation.step_id if c.step_violation else '', 0)
              if c.violation_type and c.violation_type in (ViolationType.MISSING_STEP, ViolationType.INCOMPLETE_STEP)
              else 0),
            -(c.step_violation.expected_order if c.step_violation else 0),
        ))

        return conflicts, all_violations
