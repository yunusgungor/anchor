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


class TestDetectEdgeCases:
    """Edge case testleri."""

    def test_empty_llm_output(self):
        """Boş LLM çıktısı — hata vermemeli."""
        from anchor import Rule
        det = ConflictDetector()
        rule = Rule(id="test", topic="NPX1", content="- Edge AI", file_path="")
        rule.aliases = ["npx1"]
        conflicts = det.detect("", rule, [])
        assert len(conflicts) == 0

    def test_very_long_content(self):
        """Çok uzun rule içeriği."""
        from anchor import Rule
        det = ConflictDetector()
        long_content = "- " + "uzun bilgi " * 1000
        rule = Rule(id="test", topic="NPX1", content=long_content, file_path="")
        rule.aliases = ["npx1"]
        conflicts = det.detect("NPX1, uzun bilgi.", rule, [])
        assert isinstance(conflicts, list)

    def test_fact_extraction_from_pipe_table(self):
        """Pipe tablosundan fact çıkarma."""
        from anchor import Rule
        det = ConflictDetector()
        content = """| Konu | LLM'in Genelde Dediği | Doğrusu |
|------|----------------------|---------|
| Üretim | TSMC 7nm | SKY130 (130nm) |
| Amaç | Genel AI | Edge AI |"""
        rule = Rule(id="test", topic="NPX1", content=content, file_path="")
        rule.aliases = ["npx1"]
        conflicts = det.detect("NPX1, TSMC 7nm'de üretilir.", rule, [])
        assert len(conflicts) >= 1

    def test_fact_extraction_from_code_block(self):
        """Kod bloğundan fact çıkarma."""
        from anchor import Rule
        det = ConflictDetector()
        content = """```verilog
module npu_core (
    input clk,
    input rst_n
);
endmodule
```"""
        rule = Rule(id="test", topic="NPX1", content=content, file_path="")
        rule.aliases = ["npx1"]
        # Detector çalışmalı, hata vermemeli
        conflicts = det.detect("NPX1 hakkında bilgi.", rule, [])
        assert isinstance(conflicts, list)

    def test_no_topic_rules(self):
        """Topic eşleşmezse boş dönmeli."""
        from anchor import Rule
        det = ConflictDetector()
        rule = Rule(id="test", topic="NPX1", content="- Detail", file_path="")
        rule.aliases = ["npx1"]
        conflicts = det.detect("Hava nasıl?", rule, [])
        assert len(conflicts) == 0

    def test_claim_extractor_abbreviation(self):
        """Kısaltmalar claim extraction'ı bozmamalı."""
        ex = ClaimExtractor()
        ex.register_rule("NPX1", ["npx1"], ["hardware"], "")
        text = "Dr. Smith NPX1 hakkında konuştu. NPX1 TSMC'de üretilir."
        claims = ex.extract(text, "NPX1", ["npx1"])
        assert len(claims) >= 1

    def test_fact_matcher_identical(self):
        """Tamamen aynı metin — conflict olmamalı."""
        m = FactMatcher()
        result = m.match("SKY130 (130nm), OpenLane ile", "SKY130 (130nm), OpenLane ile")
        assert not result.is_conflict

    def test_fact_matcher_partial(self):
        """Kısmi eşleşme — düşük distance."""
        m = FactMatcher()
        result = m.match("SKY130 130nm düğüm", "SKY130 (130nm) düğüm")
        # Kısmi eşleşme, düşük distance
        assert result.edit_distance < 0.5

    def test_severity_edge_cases(self):
        """Severity sınır değerleri."""
        from anchor.detect import MatchResult
        sev = SeverityEngine()
        
        # INFO sınırı
        info_match = MatchResult("a", "a", 0.1, 0.1, 0.0, 0.1, False)
        assert sev.compute(info_match) == Severity.INFO
        
        # CRITICAL sınırı
        crit_match = MatchResult("a", "b", 0.85, 0.85, 0.0, 0.85, True)
        assert sev.compute(crit_match) == Severity.CRITICAL
        
        # WARNING eşik: >=0.2 ve <0.5
        warn_match = MatchResult("a", "b", 0.35, 0.35, 0.0, 0.35, True)
        assert sev.compute(warn_match) == Severity.WARNING
        
        # ERROR eşik: >=0.5 ve <0.8
        error_match = MatchResult("a", "b", 0.5, 0.5, 0.0, 0.5, True)
        assert sev.compute(error_match) == Severity.ERROR

    def test_extract_facts_multiple_formats(self):
        """Birden fazla formattan fact çıkarma."""
        from anchor.detect import ConflictDetector
        det = ConflictDetector()
        content = """# Başlık

- İlk fact: SKY130 PDK
- İkinci fact: OpenLane aracı

**Önemli:** Edge AI işlemcisi"""
        facts = det._extract_facts(content)
        assert any("SKY130" in f for f in facts)
        assert any("OpenLane" in f for f in facts)
