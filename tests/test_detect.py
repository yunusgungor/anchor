"""
Anchor Detection — ClaimExtractor, FactMatcher, SeverityEngine, ConflictDetector testleri.
"""

import pytest
from anchor.detect import ClaimExtractor, FactMatcher, SeverityEngine, ConflictDetector
from anchor import Severity


class TestClaimExtractor:
    def test_extract_basic(self):
        ex = ClaimExtractor()
        ex.register_rule("NPX1", ["npx1"], ["hardware"], "")
        claims = ex.extract("NPX1, Edge AI.", "NPX1", ["npx1"])
        assert len(claims) >= 1
        assert "NPX1" in claims[0].text

    def test_extract_legacy_api(self):
        ex = ClaimExtractor()
        ex.register_rule("NPX1", ["npx1"], ["hardware"], "")
        # Eski API: extract(query, content)
        claims = ex.extract("NPX1 nedir?", "NPX1, Edge AI.")
        assert len(claims) >= 1

    def test_no_match(self):
        ex = ClaimExtractor()
        ex.register_rule("NPX1", ["npx1"], ["hardware"], "")
        claims = ex.extract("Hava nasıl?", "Güneşli.")
        assert len(claims) == 0


class TestFactMatcher:
    def test_match_identical(self):
        m = FactMatcher()
        result = m.match("Edge AI", "Edge AI")
        assert result.edit_distance < 0.1
        assert not result.is_conflict

    def test_match_different(self):
        m = FactMatcher()
        result = m.match("TSMC 7nm", "SKY130 130nm")
        assert result.edit_distance > 0.5
        assert result.is_conflict


class TestSeverityEngine:
    def test_info(self):
        from anchor.detect import MatchResult
        sev = SeverityEngine()
        match = MatchResult("a", "a", 0.1, 0.1, 0.0, 0.1, False)
        assert sev.compute(match) == Severity.INFO

    def test_critical(self):
        from anchor.detect import MatchResult
        sev = SeverityEngine()
        match = MatchResult("a", "b", 0.9, 0.9, 0.0, 0.9, True)
        assert sev.compute(match) == Severity.CRITICAL


class TestConflictDetector:
    def test_detect_conflict(self):
        from anchor import Rule
        det = ConflictDetector()
        rule = Rule(id="test", topic="NPX1", content="- SKY130'da üretiliyor", file_path="")
        rule.aliases = ["npx1"]
        conflicts = det.detect("NPX1, TSMC'de.", rule, [])
        assert len(conflicts) >= 1
        assert conflicts[0].severity == Severity.CRITICAL

    def test_no_conflict(self):
        from anchor import Rule
        det = ConflictDetector()
        rule = Rule(id="test", topic="NPX1", content="- Edge AI", file_path="")
        rule.aliases = ["npx1"]
        conflicts = det.detect("NPX1, Edge AI.", rule, [])
        assert len(conflicts) == 0
