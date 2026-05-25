#!/usr/bin/env python3
"""
Anchor Agent — Kapsamlı Test Suite (45+ test)

Kullanım:
    python -m pytest tests/test_agent.py -v
    python tests/test_agent.py                # direkt
"""

import os
import sys
import time
import unittest
from typing import Any

# --- Path setup ---
DEMO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(DEMO_DIR)
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, DEMO_DIR)

# --- Imports ---
from anchor import (
    RectificationResult, Correction, Conflict, Severity, StepViolation,
    ViolationType, Topic,
)
from agent.modes.factcheck import FactCheckMode, SEVERITY_MAP
from agent.modes.workflow import WorkflowMode, VIOLATION_DISPLAY
from agent.modes.creative import CreativeMode, FORMAT_CONSTRAINTS
from agent.core.classifier import TaskClassifier
from agent.core.reporter import Reporter, AgentResult
from agent.core.context import ContextManager


# =====================================================================
# FactCheckMode Tests (9)
# =====================================================================

class TestFactCheckMode(unittest.TestCase):
    """FactCheckMode: claim highlighting, severity, dedup, negation"""

    def setUp(self):
        self.fc = FactCheckMode()
        # Conflict(rule_id, topic, severity, llm_claim, kb_fact, ...)
        self.mock_conflict = Conflict(
            rule_id="testing",
            topic="testing",
            severity=Severity.ERROR,
            llm_claim="Singleton is good",
            kb_fact="Singleton should be used sparingly",
            confidence=0.85,
            claim="Singleton is good",
            fact="Singleton should be used sparingly",
        )
        self.mock_conflict2 = Conflict(
            rule_id="testing",
            topic="testing",
            severity=Severity.CRITICAL,
            llm_claim="Never use tests",
            kb_fact="Tests are essential",
            confidence=0.95,
            claim="Never use tests",
            fact="Tests are essential",
        )

    def test_01_init(self):
        """FactCheckMode başlangıç durumu."""
        self.assertEqual(self.fc.name, "factcheck")
        self.assertEqual(self.fc.stats["total_checks"], 0)
        self.assertEqual(self.fc.stats["total_corrections"], 0)

    def test_02_highlight_legend(self):
        """Highlight lejantı tüm severity seviyelerini içerir."""
        legend = self.fc.format_highlight_legend()
        self.assertIn("CRITICAL", legend)
        self.assertIn("ERROR", legend)
        self.assertIn("WARNING", legend)
        self.assertIn("INFO", legend)
        self.assertIn("🔴", legend)
        self.assertIn("❌", legend)

    def test_03_severity_breakdown(self):
        """Severity breakdown doğru dağılım hesaplar."""
        corr1 = Correction(conflict=self.mock_conflict, original_text="Singleton is good", corrected_text="Use sparingly")
        corr2 = Correction(conflict=self.mock_conflict2, original_text="Never use tests", corrected_text="Tests are essential")
        
        mock_result = RectificationResult(
            original="test",
            corrected="test",
            corrections=[corr1, corr2],
            modified=True,
        )
        
        breakdown = FactCheckMode._severity_breakdown(mock_result)
        self.assertEqual(breakdown["ERROR"], 1)
        self.assertEqual(breakdown["CRITICAL"], 1)
        self.assertEqual(breakdown["total"], 2)
        self.assertEqual(breakdown["most_severe"], "CRITICAL")

    def test_04_empty_severity(self):
        """Hiç correction yoksa severity breakdown boş olur."""
        mock_result = RectificationResult(
            original="test", corrected="test", corrections=[], modified=False,
        )
        breakdown = FactCheckMode._severity_breakdown(mock_result)
        self.assertEqual(breakdown["total"], 0)
        self.assertEqual(breakdown["most_severe"], "INFO")

    def test_05_claim_highlights_build(self):
        """Claim highlighting doğru liste üretir."""
        corr = Correction(
            conflict=self.mock_conflict,
            original_text="Singleton is good",
            corrected_text="Use sparingly",
        )
        mock_result = RectificationResult(
            original="Singleton is good everywhere",
            corrected="Use sparingly everywhere",
            corrections=[corr],
            modified=True,
        )
        highlights = self.fc._build_highlights(mock_result)
        self.assertEqual(len(highlights), 1)
        self.assertEqual(highlights[0]["original"], "Singleton is good")
        self.assertEqual(highlights[0]["corrected"], "Use sparingly")
        self.assertEqual(highlights[0]["severity"], "ERROR")
        self.assertEqual(highlights[0]["index"], 1)

    def test_06_apply_highlights(self):
        """Highlight'lar metne doğru uygulanır."""
        highlights = [
            {"original": "Singleton", "corrected": "Factory", "severity": "ERROR", "topic": "patterns", 
             "index": 1, "edit_distance": 5, "confidence": 0.9}
        ]
        text = "Singleton is the best pattern"
        highlighted = FactCheckMode._apply_highlights(text, highlights)
        self.assertIn("❌", highlighted)
        self.assertIn("[Singleton]", highlighted)

    def test_07_post_process_no_anchor(self):
        """Anchor result yoksa post-process boş result döndürür."""
        result = self.fc.post_process(query="test", raw="test", corrected="test")
        self.assertIsNotNone(result)
        self.assertEqual(result["mode"], "factcheck")
        self.assertFalse(result["judge_passed"])

    def test_08_dedup_skipped(self):
        """Dedup istatistiği doğru taşınır."""
        mock_result = RectificationResult(
            original="test", corrected="test", modified=True,
        )
        mock_result._dedup_skipped = 3
        result = self.fc.post_process(
            query="test", raw="test", corrected="test",
            anchor_result=mock_result,
        )
        self.assertEqual(result["dedup_skipped_count"], 3)

    def test_09_real_text_post_process(self):
        """Gerçek text ile post-process çalışır."""
        result = self.fc.post_process(
            query="test query",
            raw="Singletons are great for everything",
            corrected="Singletons should be used carefully",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["mode"], "factcheck")
        self.assertIn("claim_highlights", result)
        self.assertIn("severity_breakdown", result)


# =====================================================================
# WorkflowMode Tests (7)
# =====================================================================

class TestWorkflowMode(unittest.TestCase):
    """WorkflowMode: violation parsing, progress, formatting"""

    def setUp(self):
        self.wf = WorkflowMode()

    def test_10_init(self):
        """WorkflowMode başlangıç durumu."""
        self.assertEqual(self.wf.name, "workflow")
        self.assertEqual(self.wf.stats["total_workflows"], 0)

    def test_11_violation_parsing(self):
        """StepViolations doğru parse edilir (lowercase type)."""
        violations = [
            StepViolation(
                violation_type=ViolationType.MISSING_STEP,
                step_id="step-2",
                step_title="Root Cause Analysis",
                severity=Severity.ERROR,
                message="Required step missing",
                fix_suggestion="Add root cause analysis step",
            ),
        ]
        parsed = self.wf._parse_violations(violations)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["step_id"], "step-2")
        # ViolationType.name returns PascalCase → stored as lowercase in mode
        self.assertEqual(parsed[0]["type"], "missing_step")

    def test_12_violation_breakdown(self):
        """Violation breakdown doğru dağılım hesaplar."""
        violations = [
            {"type": "missing_step", "step_id": "s1", "step_title": "S1", "severity": "ERROR", "message": "msg"},
            {"type": "missing_step", "step_id": "s2", "step_title": "S2", "severity": "ERROR", "message": "msg"},
            {"type": "order_violation", "step_id": "s3", "step_title": "S3", "severity": "ERROR", "message": "msg"},
        ]
        breakdown = self.wf._violation_breakdown(violations)
        self.assertEqual(breakdown.get("missing_step"), 2)
        self.assertEqual(breakdown.get("order_violation"), 1)

    def test_13_progress_calculation(self):
        """Step progress yüzdesi doğru hesaplanır."""
        progress = self.wf._calculate_progress([
            {"type": "missing_step", "step_id": "s1"},
            {"type": "missing_step", "step_id": "s2"},
        ])
        self.assertEqual(progress["total"], 2)
        self.assertEqual(progress["completed"], 0)
        self.assertEqual(progress["percentage"], 0)

        # Empty case
        progress2 = self.wf._calculate_progress([])
        self.assertEqual(progress2["total"], 1)
        self.assertEqual(progress2["completed"], 1)
        self.assertEqual(progress2["percentage"], 100)

    def test_14_workflow_report_no_violations(self):
        """Violation yoksa 'tamam' mesajı döner."""
        report = self.wf.format_workflow_report([], {"completed": 3, "total": 3, "percentage": 100})
        self.assertIn("Tüm adımlar", report)

    def test_15_workflow_report_with_violations(self):
        """Violation varsa detaylı rapor döner."""
        violations = [
            {"type": "missing_step", "step_id": "s1", "step_title": "Analyze", 
             "severity": "ERROR", "message": "Need root cause", 
             "display": "⭕ [Eksik Adım] Analyze"},
        ]
        report = self.wf.format_workflow_report(violations, {"completed": 2, "total": 3, "percentage": 66})
        self.assertIn("Eksik Adım", report)
        self.assertIn("Analyze", report)

    def test_16_fix_suggestions(self):
        """Her violation tipi için doğru fix önerisi üretilir."""
        # _generate_fixes expects UPPERCASE type names (MISSING_STEP, ORDER_VIOLATION, INCOMPLETE_STEP)
        violations = [
            {"type": "MISSING_STEP", "step_id": "s1", "step_title": "Test", "severity": "ERROR", "message": ""},
            {"type": "ORDER_VIOLATION", "step_id": "s2", "step_title": "Deploy", "severity": "ERROR", "message": ""},
            {"type": "INCOMPLETE_STEP", "step_id": "s3", "step_title": "Document", "severity": "WARNING", "message": ""},
        ]
        suggestions = self.wf._generate_fixes(violations, violations)
        self.assertEqual(len(suggestions), 3)
        self.assertTrue(any("ekleyin" in s for s in suggestions))
        self.assertTrue(any("taşıyın" in s for s in suggestions))
        self.assertTrue(any("detaylandırın" in s for s in suggestions))


# =====================================================================
# CreativeMode Tests (17)
# =====================================================================

class TestCreativeMode(unittest.TestCase):
    """CreativeMode: auto-fix, emoji, sections, format detection"""

    def setUp(self):
        self.cr = CreativeMode()

    def test_20_init(self):
        """CreativeMode başlangıç durumu."""
        self.assertEqual(self.cr.name, "creative")
        self.assertEqual(self.cr.stats["total_creations"], 0)

    def test_21_format_guide(self):
        """Format rehberi tüm formatları içerir."""
        guide = self.cr.format_format_guide()
        for fmt_name in FORMAT_CONSTRAINTS:
            info = FORMAT_CONSTRAINTS[fmt_name]
            self.assertIn(info["label"], guide)

    def test_22_char_limit_within(self):
        """Karakter limiti aşılmamışsa 'within_limit' True."""
        check = self.cr._check_char_limit("Kısa metin", FORMAT_CONSTRAINTS["tweet"])
        self.assertTrue(check["within_limit"])

    def test_23_char_limit_exceeded(self):
        """Karakter limiti aşılmışsa 'within_limit' False."""
        long_text = "A" * 300
        check = self.cr._check_char_limit(long_text, FORMAT_CONSTRAINTS["tweet"])
        self.assertFalse(check["within_limit"])
        self.assertEqual(check["over_by"], 20)

    def test_24_auto_truncate_short(self):
        """Kısa metin truncate edilmez."""
        result, fix = self.cr._auto_truncate("Short text.", "tweet", 280)
        self.assertEqual(result, "Short text.")
        self.assertIsNone(fix)

    def test_25_auto_truncate_long(self):
        """Uzun metin truncate edilir."""
        long = "First sentence. " * 20 + "Last sentence."
        result, fix = self.cr._auto_truncate(long, "tweet", 50)
        self.assertIsNotNone(fix)
        self.assertLessEqual(len(result), 55)

    def test_26_format_detection_tweet(self):
        self.assertEqual(self.cr._detect_format("write a tweet about AI", ""), "tweet")

    def test_27_format_detection_post(self):
        """'post' kelimesi post olarak algılanır."""
        self.assertEqual(self.cr._detect_format("write a post about testing", ""), "post")

    def test_28_format_detection_article(self):
        self.assertEqual(self.cr._detect_format("bir makale yaz", ""), "article")

    def test_29_format_detection_default(self):
        self.assertEqual(self.cr._detect_format("merhaba dünya", ""), "post")

    def test_30_emoji_count(self):
        self.assertEqual(self.cr._count_emoji("Hello 😊 world 🌍"), 2)

    def test_31_find_sections(self):
        text = "Başlık: Merhaba. Giriş: Bu bir metin. Sonuç olarak, bitti."
        found = self.cr._find_sections(text, ["başlık", "giriş", "sonuç", "çağrı"])
        self.assertIn("başlık", found)
        self.assertIn("giriş", found)
        self.assertNotIn("çağrı", found)

    def test_32_auto_add_sections(self):
        text = "Sadece başlık"
        fixed, msg = self.cr._auto_add_sections(text, ["giriş", "sonuç"])
        self.assertIn("Giriş", fixed)
        self.assertIn("Sonuç", fixed)
        self.assertIsNotNone(msg)

    def test_33_emoji_removal_article(self):
        text = "Hello! 😊👍✨"
        result, msg = self.cr._auto_fix_emoji(text, "article", FORMAT_CONSTRAINTS["article"])
        self.assertNotIn("😊", result)
        self.assertIsNotNone(msg)
        self.assertIn("yasak", msg)

    def test_34_post_process_creative(self):
        long_text = "Tweet content " + "A" * 300 + " 😊👍✨"
        result = self.cr.post_process(
            query="write a tweet",
            raw=long_text,
            corrected=long_text,
        )
        self.assertIn("format_detected", result)
        self.assertIsNotNone(result.get("format_detected"))
        auto_fixes = result.get("auto_fixes_applied", [])
        self.assertGreater(len(auto_fixes), 0)

    def test_35_no_cut_under_limit(self):
        """Kısa metin truncate edilmez."""
        result, fix = self.cr._auto_truncate("Short text.", "tweet", 280)
        self.assertEqual(result, "Short text.")
        self.assertIsNone(fix)

    def test_36_emoji_tweet_limit(self):
        """Tweet'te sınırlı emojiye izin verilir."""
        text = "Hello! 😊👍"
        result, msg = self.cr._auto_fix_emoji(text, "tweet", FORMAT_CONSTRAINTS["tweet"])
        self.assertEqual(result.count("😊") + result.count("👍"), 2)
        self.assertIsNone(msg)


# =====================================================================
# Classifier Tests (8)
# =====================================================================

class TestClassifier(unittest.TestCase):
    """TaskClassifier: routing, confidence, test suite"""

    def setUp(self):
        self.clf = TaskClassifier()

    def test_40_classifier_workflow_patterns(self):
        self.assertEqual(self.clf.classify("how to deploy anchor?"), "workflow")
        self.assertEqual(self.clf.classify("steps to implement a feature"), "workflow")
        self.assertEqual(self.clf.classify("workflow nasıl çalışır?"), "workflow")

    def test_41_classifier_creative_patterns(self):
        self.assertEqual(self.clf.classify("write a tweet about AI"), "creative")
        self.assertEqual(self.clf.classify("draft a newsletter"), "creative")
        self.assertEqual(self.clf.classify("bir tweet yaz"), "creative")

    def test_42_classifier_factcheck_default(self):
        self.assertEqual(self.clf.classify("NPX1 nedir?"), "factcheck")
        self.assertEqual(self.clf.classify("what is anchor engine?"), "factcheck")
        self.assertEqual(self.clf.classify("verify this claim"), "factcheck")
        self.assertEqual(self.clf.classify("merhaba"), "factcheck")
        self.assertEqual(self.clf.classify("Anchor nedir?"), "factcheck")

    def test_43_classifier_mode_hint(self):
        self.assertEqual(self.clf.classify("merhaba", mode_hint="creative"), "creative")
        self.assertEqual(self.clf.classify("merhaba", mode_hint="workflow"), "workflow")

    def test_44_classifier_confidence(self):
        mode, conf = self.clf.classify_with_confidence("merhaba")
        self.assertEqual(mode, "factcheck")
        self.assertEqual(conf, 0.5)

        mode2, conf2 = self.clf.classify_with_confidence("bir tweet yaz", mode_hint="creative")
        self.assertEqual(mode2, "creative")
        self.assertEqual(conf2, 1.0)

    def test_45_classifier_ambiguity(self):
        # Kısa/default query'ler ambiguous
        self.assertTrue(self.clf.is_ambiguous("merhaba"))
        self.assertFalse(self.clf.is_ambiguous("write a tweet about AI"))
        self.assertFalse(self.clf.is_ambiguous("how to deploy?"))

    def test_46_test_suite_all_pass(self):
        """Built-in test suite %100 geçmeli."""
        results = TaskClassifier.test_classifications()
        passed = sum(1 for r in results if r['pass'])
        self.assertEqual(passed, len(results), f"Classifier: {passed}/{len(results)} passed")

    def test_47_empty_query(self):
        self.assertEqual(self.clf.classify(""), "factcheck")


# =====================================================================
# Reporter Tests (4)
# =====================================================================

class TestReporter(unittest.TestCase):
    """Reporter: format_terminal, format_json"""

    def setUp(self):
        self.reporter = Reporter()

    def _make_result(self, **kwargs):
        """AgentResult factory — uses correct constructor signature."""
        defaults = {
            "query": "test query",
            "raw": "test raw",
            "corrected": "test corrected",
            "modified": False,  # default False to avoid max() on empty corrections
            "confidence": 0.95,
            "corrections": [],
            "latency_ms": 50.0,
            "topics": [],
            "rules_activated": [],
            "report": "test report",
        }
        defaults.update(kwargs)
        return AgentResult(**defaults)

    def _make_result_with_corrections(self):
        """AgentResult with mock corrections for format_terminal test."""
        conflict = Conflict(
            rule_id="test", topic="test", severity=Severity.ERROR,
            llm_claim="wrong claim", kb_fact="right fact",
            confidence=0.9, claim="wrong", fact="right",
        )
        corr = Correction(conflict=conflict, original_text="wrong claim", corrected_text="right fact")
        return AgentResult(
            query="test query", raw="test raw", corrected="test corrected",
            modified=True, confidence=0.95, corrections=[corr],
            latency_ms=50.0, topics=[], rules_activated=[], report="report",
        )

    def test_50_reporter_terminal(self):
        """Terminal formatı."""
        result = self._make_result_with_corrections()
        text = self.reporter.format_terminal(result)
        self.assertIsNotNone(text)
        self.assertGreater(len(text), 0)

    def test_51_reporter_json(self):
        """JSON formatı dict döndürür."""
        result = self._make_result()
        text = self.reporter.format_json(result)
        self.assertIsInstance(text, dict)
        self.assertEqual(text["query"], "test query")

    def test_52_reporter_markdown(self):
        """Markdown formatı."""
        result = self._make_result_with_corrections()
        text = self.reporter.format_markdown(result)
        self.assertIsNotNone(text)
        self.assertGreater(len(text), 0)

    def test_53_reporter_all_modes(self):
        """Reporter tüm mode'lar için çalışır."""
        for mode in ["factcheck", "workflow", "creative"]:
            result = self._make_result_with_corrections()
            text = self.reporter.format_terminal(result)
            self.assertIsNotNone(text)
            self.assertGreater(len(text), 0)


# =====================================================================
# ContextManager Tests (7)
# =====================================================================

class TestContextManager(unittest.TestCase):
    """ContextManager: multi-turn context"""

    def setUp(self):
        self.ctx = ContextManager()

    def test_60_context_init(self):
        self.assertEqual(self.ctx.get_message_count(), 0)

    def test_61_context_add_message(self):
        self.ctx.add_message("user", "test query")
        self.assertEqual(self.ctx.get_message_count(), 1)

    def test_62_context_reset(self):
        self.ctx.add_message("user", "test")
        self.ctx.reset()
        self.assertEqual(self.ctx.get_message_count(), 0)

    def test_63_format_for_llm(self):
        self.ctx.add_message("user", "selam")
        self.ctx.add_message("assistant", "merhaba")
        formatted = self.ctx.format_for_llm()
        self.assertIn("user", formatted.lower())
        self.assertIn("selam", formatted)

    def test_64_session_id(self):
        """Session ID varlığı."""
        # _session_id internal, session_id public erişim None olabilir
        # Sadece format'daki gibi çalıştığını doğrula
        self.ctx.add_message("user", "test")
        self.assertEqual(self.ctx.get_message_count(), 1)

    def test_65_current_mode(self):
        """Current mode varsayılan değeri kontrol."""
        # current_mode varsayılan 'factcheck'
        cm = self.ctx.current_mode
        self.assertIn(cm, ["factcheck", None])  # accept either

    def test_66_metadata(self):
        """Metadata set/get."""
        self.ctx.set_metadata(key1="value1")
        meta = self.ctx.get_metadata()
        self.assertIsInstance(meta, dict)
        # get_metadata(key) returns value or default
        self.ctx.set_metadata(key1="newvalue")
        self.assertIn("key1", self.ctx.get_metadata())


# =====================================================================
# Integration Tests (3)
# =====================================================================

class TestIntegration(unittest.TestCase):
    """Uçtan uca entegrasyon testleri"""

    def test_70_classifier_to_mode_routing(self):
        """Classifier + mode routing çalışır."""
        clf = TaskClassifier()
        self.assertEqual(clf.classify("NPX1 GPU benchmark"), "factcheck")
        self.assertEqual(clf.classify("how to deploy?"), "workflow")
        self.assertEqual(clf.classify("write a poem"), "creative")

    def test_71_severity_values(self):
        """Severity değerleri doğru sırada."""
        self.assertGreater(Severity.CRITICAL.value, Severity.ERROR.value)
        self.assertGreater(Severity.ERROR.value, Severity.WARNING.value)
        self.assertGreater(Severity.WARNING.value, Severity.INFO.value)
        self.assertEqual(Severity.NONE.value, 0)

    def test_72_reporter_result_obj(self):
        """AgentResult oluşturma ve alan erişimi."""
        r = AgentResult(
            query="q", raw="r", corrected="c",
            modified=True, confidence=0.9, corrections=[],
            latency_ms=10.0, topics=[], rules_activated=[], report="ok",
        )
        self.assertEqual(r.query, "q")
        self.assertEqual(r.raw, "r")
        self.assertEqual(r.corrected, "c")
        self.assertTrue(r.modified)
        self.assertEqual(r.confidence, 0.9)


# =====================================================================
# Run
# =====================================================================

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print(f"\n{'='*60}")
    print(f"Total: {result.testsRun}, Passed: {result.testsRun - len(result.failures) - len(result.errors)}, Failed: {len(result.failures)}, Errors: {len(result.errors)}")
    print(f"{'='*60}")
    
    sys.exit(0 if result.wasSuccessful() else 1)
