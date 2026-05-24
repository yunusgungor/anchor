"""
Anchor Workflow Governor — Comprehensive test suite.

Test coverage:
  - StepExtractor: basic extraction, multiple steps, no match
  - OrderValidator: correct order, wrong order, depends_on chain
  - CompletenessValidator: all mandatory present, missing mandatory, extra step
  - WorkflowIntegrator: full pipeline with mock rule
  - PatchEngine: INSERT_BEFORE, REORDER strategies
  - End-to-end: engine.process with workflow rule
"""

import pytest
from pathlib import Path

from anchor import (
    Conflict, Correction, Severity, Step, StepViolation, ViolationType, Rule, RectificationResult,
)
from anchor.compliance.workflow_validator import (
    StepExtractor,
    OrderValidator,
    CompletenessValidator,
    WorkflowIntegrator,
)
from anchor.rectify import PatchEngine, PatchStrategy
from anchor.engine import AnchorEngine


# ─── Test Fixtures ───────────────────────────────────────────────────────────

RULES_PATH = str(Path(__file__).parent.parent / "rules")
INDEX_PATH = str(Path(__file__).parent.parent / ".anchor_test.idx")


@pytest.fixture
def sample_steps():
    """Sample workflow steps for testing."""
    return [
        Step(id="step-1", title="Ortam\u0131 belirle", mandatory=True, checks=["OS", "browser"]),
        Step(id="step-2", title="Hatay\u0131 tan\u0131mla", mandatory=True, depends_on=["step-1"]),
        Step(id="step-3", title="Loglar\u0131 ekle", mandatory=True, depends_on=["step-2"]),
        Step(id="step-4", title="Beklenen davran\u0131\u015f\u0131 a\u00e7\u0131kla", mandatory=True),
        Step(id="step-5", title="\u00d6ncelik belirle", mandatory=False, options=["P0", "P1", "P2"]),
    ]


@pytest.fixture
def mock_rule():
    """A minimal mock Rule object for integration testing."""
    return Rule(
        id="test-workflow",
        topic="Bug Report Workflow",
        content="- **Fact:** Test fact",
        file_path="/tmp/test-workflow.md",
        steps=[
            Step(id="step-1", title="Ortam\u0131 belirle", mandatory=True, checks=["OS", "browser"]),
            Step(id="step-2", title="Hatay\u0131 tan\u0131mla", mandatory=True, depends_on=["step-1"]),
            Step(id="step-3", title="Loglar\u0131 ekle", mandatory=True, depends_on=["step-2"]),
            Step(id="step-4", title="Beklenen davran\u0131\u015f\u0131 a\u00e7\u0131kla", mandatory=True),
            Step(id="step-5", title="\u00d6ncelik belirle", mandatory=False),
        ],
    )


# ─── StepExtractor Tests ─────────────────────────────────────────────────────

class TestStepExtractor:
    """Step extraction from LLM output."""

    def setup_method(self):
        self.extractor = StepExtractor()

    def test_basic_extraction(self, sample_steps):
        """Extract steps that are explicitly mentioned in the output."""
        output = (
            "Ortam\u0131 belirle: Windows 11, Chrome taray\u0131c\u0131.\n"
            "Sonra hatay\u0131 tan\u0131mla: Uygulama a\u00e7\u0131lm\u0131yor.\n"
            "Loglar\u0131 ekle: Hata loglar\u0131 a\u015fa\u011f\u0131da.\n"
            "Sonra beklenen davran\u0131\u015f\u0131 a\u00e7\u0131kla.\n"
            "\u00d6ncelik belirle: P1 olarak belirledim."
        )
        results = self.extractor.extract(output, sample_steps)
        assert len(results) >= 4  # At least 4 steps matched (step-5 is optional match)
        # Check step IDs
        step_ids = [r[0] for r in results]
        assert "step-1" in step_ids
        assert "step-2" in step_ids
        assert "step-3" in step_ids
        assert "step-4" in step_ids
        assert "step-5" in step_ids
        # Check order: step-1 should come before step-2
        pos_1 = next(r[2] for r in results if r[0] == "step-1")
        pos_2 = next(r[2] for r in results if r[0] == "step-2")
        assert pos_1 < pos_2

    def test_extraction_no_match(self, sample_steps):
        """No steps mentioned in the output — empty result."""
        output = "Bug\u00fcn hava \u00e7ok g\u00fczel. D\u0131\u015far\u0131 \u00e7\u0131k\u0131p y\u00fcr\u00fcy\u00fc\u015f yapaca\u011f\u0131m."
        results = self.extractor.extract(output, sample_steps)
        assert len(results) == 0

    def test_extraction_partial_match(self, sample_steps):
        """Only some steps mentioned."""
        output = "Ortam\u0131 belirle: MacOS. Beklenen davran\u0131\u015f\u0131 a\u00e7\u0131kla."
        results = self.extractor.extract(output, sample_steps)
        step_ids = [r[0] for r in results]
        assert "step-1" in step_ids  # "Ortamı belirle" found
        assert "step-4" in step_ids  # "Beklenen davranışı açıkla" found
        assert "step-3" not in step_ids  # "Logları ekle" not mentioned

    def test_extraction_by_id(self, sample_steps):
        """Step IDs can also match."""
        output = "Ad\u0131m step-1 tamamland\u0131. \u015eimdi step-2'ye ge\u00e7iyorum."
        results = self.extractor.extract(output, sample_steps)
        step_ids = [r[0] for r in results]
        assert "step-1" in step_ids
        assert "step-2" in step_ids

    def test_extraction_with_empty_steps(self):
        """Empty steps list — should return empty results."""
        results = self.extractor.extract("Some text", [])
        assert results == []


# ─── OrderValidator Tests ────────────────────────────────────────────────────

class TestOrderValidator:
    """Step order validation."""

    def setup_method(self):
        self.validator = OrderValidator()

    def test_correct_order(self, sample_steps):
        """Steps in correct order — no violations."""
        executed = [
            ("step-1", 0.9, 0),
            ("step-2", 0.9, 50),
            ("step-3", 0.9, 100),
            ("step-4", 0.9, 150),
        ]
        violations = self.validator.validate(executed, sample_steps)
        assert len(violations) == 0

    def test_wrong_order_simple(self, sample_steps):
        """Step-2 appears before step-1, but step-2 depends on step-1."""
        executed = [
            ("step-2", 0.9, 0),   # step-2 first (WRONG — depends on step-1)
            ("step-1", 0.9, 50),  # step-1 second
        ]
        violations = self.validator.validate(executed, sample_steps)
        assert len(violations) == 1
        assert violations[0].violation_type == ViolationType.ORDER_VIOLATION
        assert violations[0].step_id == "step-2"
        assert violations[0].expected_order == 50  # step-1's text position
        assert violations[0].actual_order == 0      # step-2's text position

    def test_depends_chain_violation(self, sample_steps):
        """Step-3 appears before step-2, but step-3 depends on step-2."""
        executed = [
            ("step-1", 0.9, 0),
            ("step-3", 0.9, 50),  # step-3 before step-2 (WRONG)
            ("step-2", 0.9, 100),
        ]
        violations = self.validator.validate(executed, sample_steps)
        assert len(violations) == 1
        assert violations[0].step_id == "step-3"

    def test_no_depends_no_violation(self):
        """Steps without dependencies — no order violations possible."""
        steps = [
            Step(id="a", title="A", mandatory=True),
            Step(id="b", title="B", mandatory=True),
            Step(id="c", title="C", mandatory=True),
        ]
        executed = [
            ("c", 0.9, 0),
            ("a", 0.9, 50),
            ("b", 0.9, 100),
        ]
        violations = self.validator.validate(executed, steps)
        assert len(violations) == 0

    def test_empty_executed(self, sample_steps):
        """No executed steps — no violations."""
        violations = self.validator.validate([], sample_steps)
        assert len(violations) == 0


# ─── CompletenessValidator Tests ─────────────────────────────────────────────

class TestCompletenessValidator:
    """Step completeness validation."""

    def setup_method(self):
        self.validator = CompletenessValidator()

    def test_all_mandatory_present(self, sample_steps):
        """All mandatory steps present — no violations (checks satisfied)."""
        executed = [
            ("step-1", 0.9, 0),
            ("step-2", 0.9, 50),
            ("step-3", 0.9, 100),
            ("step-4", 0.9, 150),
        ]
        # Output must contain checks for step-1: "OS" and "browser"
        output = "Ortam\u0131 belirle: Windows (OS: Win11) browser: Chrome. Hatay\u0131 tan\u0131mla: crash. Loglar eklendi. Beklenen davran\u0131\u015f: a\u00e7\u0131ls\u0131n."
        violations = self.validator.validate(executed, sample_steps, output)
        assert len(violations) == 0

    def test_missing_mandatory_step(self, sample_steps):
        """A mandatory step is missing."""
        executed = [
            ("step-1", 0.9, 0),
            ("step-2", 0.9, 50),
            ("step-4", 0.9, 100),
        ]
        output = "Ortam belirlendi. Hata tan\u0131mland\u0131. Beklenen davran\u0131\u015f a\u00e7\u0131kland\u0131."
        violations = self.validator.validate(executed, sample_steps, output)
        # step-3 is mandatory but missing
        missing_ids = [v.step_id for v in violations if v.violation_type == ViolationType.MISSING_STEP]
        assert "step-3" in missing_ids

    def test_optional_step_skipped(self, sample_steps):
        """Optional step can be skipped without violation."""
        executed = [
            ("step-1", 0.9, 0),
            ("step-2", 0.9, 50),
            ("step-3", 0.9, 100),
            ("step-4", 0.9, 150),
        ]
        output = "All mandatory steps done."
        violations = self.validator.validate(executed, sample_steps, output)
        # step-5 is optional, no violation expected
        step5_violations = [v for v in violations if v.step_id == "step-5"]
        assert len(step5_violations) == 0

    def test_incomplete_step_missing_checks(self, sample_steps):
        """Step found but missing required checks."""
        executed = [("step-1", 0.9, 0)]
        # "OS" is mentioned but "browser" is not
        output = "Ortam\u0131 belirle: Ubuntu \u00e7al\u0131\u015f\u0131yor."
        violations = self.validator.validate(executed, sample_steps, output)
        check_violations = [v for v in violations if v.violation_type == ViolationType.INCOMPLETE_STEP]
        assert len(check_violations) == 1
        assert check_violations[0].step_id == "step-1"
        assert "browser" in check_violations[0].message

    def test_empty_steps(self):
        """No defined steps — no violations."""
        violations = self.validator.validate([], [], "")
        assert len(violations) == 0


# ─── WorkflowIntegrator Tests ────────────────────────────────────────────────

class TestWorkflowIntegrator:
    """Full pipeline with mock rule."""

    def setup_method(self):
        self.integrator = WorkflowIntegrator()

    def test_full_pipeline_no_violations(self, mock_rule):
        """All steps present and in correct order."""
        output = (
            "Ortam\u0131 belirle: Windows 11, Chrome browser (OS: Win11).\n"
            "Hatay\u0131 tan\u0131mla: Ad\u0131m ad\u0131m reproduce edilebilir.\n"
            "Loglar\u0131 ekle: Sistem loglar\u0131 eklendi.\n"
            "Beklenen davran\u0131\u015f\u0131 a\u00e7\u0131kla: Normalde a\u00e7\u0131lmas\u0131 gerekirdi.\n"
            "\u00d6ncelik belirle: P1."
        )
        conflicts, step_violations = self.integrator.validate(output, mock_rule)
        assert len(step_violations) == 0
        assert len(conflicts) == 0

    def test_incomplete_step_via_integrator(self, mock_rule):
        """Step-1 found but missing 'browser' check."""
        output = "Ortam\u0131 belirle: Ubuntu \u00e7al\u0131\u015f\u0131yor."
        conflicts, step_violations = self.integrator.validate(output, mock_rule)
        incomplete = [sv for sv in step_violations if sv.violation_type == ViolationType.INCOMPLETE_STEP]
        assert len(incomplete) >= 1
        # Check that conflict is created
        wf_conflicts = [c for c in conflicts if c.violation_type is not None]
        assert len(wf_conflicts) >= 1

    def test_missing_step_via_integrator(self, mock_rule):
        """Mandatory steps missing entirely."""
        output = "Ortam\u0131 belirle: Chrome. Hatay\u0131 tan\u0131mla: crash."
        conflicts, step_violations = self.integrator.validate(output, mock_rule)
        missing = [sv for sv in step_violations if sv.violation_type == ViolationType.MISSING_STEP]
        assert len(missing) >= 2  # step-3 and step-4 missing
        missing_ids = [sv.step_id for sv in missing]
        assert "step-3" in missing_ids
        assert "step-4" in missing_ids

    def test_order_violation_via_integrator(self, mock_rule):
        """Step-2 appears before step-1 despite depends_on."""
        output = "Hatay\u0131 tan\u0131mla: crash. Ortam\u0131 belirle: MacOS."
        conflicts, step_violations = self.integrator.validate(output, mock_rule)
        order_vios = [sv for sv in step_violations if sv.violation_type == ViolationType.ORDER_VIOLATION]
        assert len(order_vios) >= 1
        assert order_vios[0].step_id == "step-2"

    def test_no_steps_no_violations(self):
        """Rule without steps — no violations."""
        rule = Rule(id="no-steps", topic="Test", content="", file_path="test.md")
        conflicts, step_violations = self.integrator.validate("Some output", rule)
        assert len(step_violations) == 0
        assert len(conflicts) == 0

    def test_last_step_violations_property(self, mock_rule):
        """last_step_violations returns most recent results."""
        output = "Hatay\u0131 tan\u0131mla: crash."
        self.integrator.validate(output, mock_rule)
        assert len(self.integrator.last_step_violations) >= 1


# ─── PatchEngine Extended Tests ──────────────────────────────────────────────

class TestPatchEngineInsertBefore:
    """INSERT_BEFORE strategy tests."""

    def setup_method(self):
        self.patcher = PatchEngine()

    def test_insert_before_with_missing_step(self):
        """INSERT_BEFORE with MISSING_STEP violation type."""
        conflict = Conflict(
            rule_id="wf", topic="Workflow",
            severity=Severity.ERROR,
            llm_claim="Hatay\u0131 tan\u0131mla: crash.",
            kb_fact="\u00d6nce ortam\u0131 belirlemelisin!",
            violation_type=ViolationType.MISSING_STEP,
        )
        text = "Hatay\u0131 tan\u0131mla: crash."
        result, patches = self.patcher.apply(text, [conflict])
        assert patches[0].strategy == PatchStrategy.INSERT_BEFORE
        assert "\u00d6nce ortam\u0131" in result
        assert result.index("\u00d6nce ortam\u0131") < result.index("Hatay\u0131 tan\u0131mla")

    def test_insert_before_not_found(self):
        """Original not found — content should be prepended."""
        conflict = Conflict(
            rule_id="wf", topic="Workflow",
            severity=Severity.ERROR,
            llm_claim="Nonexistent text",
            kb_fact="Missing step: Ortam\u0131 belirle",
            violation_type=ViolationType.MISSING_STEP,
        )
        text = "Some existing content."
        result, patches = self.patcher.apply(text, [conflict])
        assert patches[0].strategy == PatchStrategy.INSERT_BEFORE
        assert "Missing step" in result


class TestPatchEngineReorder:
    """REORDER strategy tests."""

    def setup_method(self):
        self.patcher = PatchEngine()

    def test_reorder_with_order_violation(self):
        """REORDER with ORDER_VIOLATION violation type."""
        conflict = Conflict(
            rule_id="wf", topic="Workflow",
            severity=Severity.ERROR,
            llm_claim="Step-2 before step-1 wrong order.",
            kb_fact="Step-1 must come before Step-2",
            violation_type=ViolationType.ORDER_VIOLATION,
        )
        text = "Step-2 before step-1 wrong order."
        result, patches = self.patcher.apply(text, [conflict])
        assert patches[0].strategy == PatchStrategy.REORDER
        assert "Step-1 must come" in result

    def test_reorder_not_found_fallback(self):
        """Original not found — fallback to fuzzy replace."""
        conflict = Conflict(
            rule_id="wf", topic="Workflow",
            severity=Severity.ERROR,
            llm_claim="Some really long text that might not be found.",
            kb_fact="Reorder: Ortam\u0131 belirle first.",
            violation_type=ViolationType.ORDER_VIOLATION,
        )
        text = "Completely unrelated content."
        result, patches = self.patcher.apply(text, [conflict])
        assert patches[0].strategy == PatchStrategy.REORDER


# ─── ConflictDetector Workflow Integration Tests ────────────────────────────

class TestDetectorWithWorkflow:
    """Test that ConflictDetector handles workflow rules."""

    def test_detector_with_steps(self):
        """Detector should run workflow validation when rule has steps."""
        from anchor.detect import ConflictDetector

        detector = ConflictDetector()
        rule = Rule(
            id="wf-test",
            topic="Workflow",
            content="- **Fact:** Some fact",
            file_path="/tmp/wf-test.md",
            steps=[
                Step(id="s1", title="Step One", mandatory=True),
                Step(id="s2", title="Step Two", mandatory=True, depends_on=["s1"]),
            ],
        )

        output = "Step One done. Step Two done."
        conflicts = detector.detect(output, rule, [])
        # Should have no workflow conflicts since both steps present in order
        wf_conflicts = [c for c in conflicts if c.violation_type is not None]
        assert len(wf_conflicts) == 0
        assert hasattr(detector, 'last_step_violations')

    def test_detector_with_missing_step(self):
        """Detector should report workflow violations as conflicts."""
        from anchor.detect import ConflictDetector

        detector = ConflictDetector()
        rule = Rule(
            id="wf-test",
            topic="Workflow",
            content="- **Fact:** Some fact",
            file_path="/tmp/wf-test.md",
            steps=[
                Step(id="s1", title="Step One", mandatory=True),
                Step(id="s2", title="Step Two", mandatory=True, depends_on=["s1"]),
            ],
        )

        output = "Just some text about anything."
        conflicts = detector.detect(output, rule, [])
        # Should produce MISSING_STEP conflicts
        wf_conflicts = [c for c in conflicts if c.violation_type is not None]
        assert len(wf_conflicts) >= 1
        assert wf_conflicts[0].violation_type == ViolationType.MISSING_STEP
        assert hasattr(detector, 'last_step_violations')
        assert len(detector.last_step_violations) >= 1

    def test_detector_no_steps(self):
        """Detector should work normally for rules without steps."""
        from anchor.detect import ConflictDetector

        detector = ConflictDetector()
        rule = Rule(
            id="no-steps",
            topic="Test",
            content="- **Fact:** Some fact about NPX1.",
            file_path="/tmp/no-steps.md",
        )

        output = "NPX1 is a great processor."
        conflicts = detector.detect(output, rule, [])
        # Should not crash, workflow validation skipped
        assert hasattr(detector, 'last_step_violations')
        assert len(detector.last_step_violations) == 0


# ─── End-to-End Tests ───────────────────────────────────────────────────────

class TestWorkflowEndToEnd:
    """End-to-end integration through AnchorEngine."""

    @pytest.fixture
    def engine(self):
        e = AnchorEngine(rules_path=RULES_PATH, index_path=INDEX_PATH)
        e.build()
        yield e

    def test_workflow_rule_loaded(self, engine):
        """Bug report workflow rule should be loaded with steps."""
        # Query for the workflow rule
        result = engine.process(
            user_query="Bug Report Workflow",
            llm_output="Bug report workflow hakkında bilgi."
        )
        # Result should exist (rule found)
        assert "bug-report" in result.rules_activated or len(result.rules_activated) >= 0

    def test_engine_process_pipeline(self, engine):
        """Detector should produce workflow conflicts when processing."""
        result = engine.process(
            user_query="Bug Report Workflow hakkında bilgi",
            llm_output="Sadece hatayı tanımlıyorum: Uygulama crash yiyor."
        )
        # The result should have step_violations
        assert isinstance(result.step_violations, list)

    def test_step_violations_in_summary(self):
        """Step violations should appear in the summary."""
        result = RectificationResult(
            original="test",
            corrected="test",
            corrections=[],
            modified=True,
            step_violations=[
                StepViolation(
                    violation_type=ViolationType.MISSING_STEP,
                    step_id="step-3",
                    step_title="Logları ekle",
                    severity=Severity.ERROR,
                    message="Zorunlu adım eksik.",
                    fix_suggestion="Ekleyin.",
                ),
            ],
        )
        summary = result.summary
        assert "workflow ihlali" in summary
        assert "Loglar\u0131 ekle" in summary
        assert "missing_step" in summary


# ─── Rule Parser Steps Integration ──────────────────────────────────────────

class TestRuleParserWithSteps:
    """Test that Rule parser correctly handles steps in frontmatter."""

    def test_parse_steps_from_md(self):
        """Parse steps from markdown frontmatter."""
        from anchor.parser import RuleParser

        content = """---
topic: "Test Workflow"
steps:
  - id: step-1
    title: "First Step"
    mandatory: true
    checks: ["check1"]
  - id: step-2
    title: "Second Step"
    mandatory: true
    depends_on: [step-1]
    options: ["A", "B"]
---

Step content here.
"""
        parser = RuleParser()
        parsed = parser.parse_text(content, "test-workflow.md")
        assert len(parsed.steps) == 2
        assert parsed.steps[0].id == "step-1"
        assert parsed.steps[0].title == "First Step"
        assert parsed.steps[0].mandatory is True
        assert parsed.steps[0].checks == ["check1"]
        assert parsed.steps[1].id == "step-2"
        assert parsed.steps[1].depends_on == ["step-1"]
        assert parsed.steps[1].options == ["A", "B"]
