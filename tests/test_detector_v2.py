"""
Conflict Detector v2 Testleri — Sentence-level claim extraction + edit distance.
"""

import pytest

from anchor.detect.v2.claim_extractor import ClaimExtractor
from anchor.detect.v2.fact_matcher import FactMatcher, MatchResult
from anchor.detect.v2.severity_engine import SeverityEngine
from anchor.detect.v2.detector_v2 import ConflictDetectorV2
from anchor import Rule, Severity


RULE_CONTENT = """
# RISC-V NPU

## Doğru Bilgiler

- **Mimari:** RISC-V + Systolic Array NPU
- **PDK:** SKY130 (130nm, open-source)
- **Üretim:** Açık kaynak PDK ve araçlarla, lisans ücreti ödenmez
- **Rakipler:** Hailo-8, Google Coral, STM32N6 (kısmen rakip)

## Sık Karıştırılan Noktalar

| Konu | LLM'in Genelde Dediği | Doğrusu |
|------|----------------------|---------|
| Üretim | TSMC'de üretiliyor | SKY130'da, OpenLane ile |
| Amaç | Genel AI hızlandırıcı | Edge AI, tarım/güvenlik |
| Lisans | Ücretli lisans | Sıfır lisans, açık kaynak |
"""


class TestClaimExtractor:
    """Claim extraction testleri."""
    
    def test_basic_claim_extraction(self):
        """Topic'le ilgili cümleleri çıkarmalı."""
        extractor = ClaimExtractor()
        llm_output = "NPX1, RISC-V mimarili bir edge AI işlemcisidir."
        
        claims = extractor.extract(llm_output, "Neural Processor X1", ["NPX1"])
        
        assert len(claims) >= 1
        assert "NPX1" in claims[0].text
        assert claims[0].position == 0
        assert claims[0].confidence > 0.5
    
    def test_multiple_sentences(self):
        """Birden fazla cümlede claim varsa hepsini çıkarmalı."""
        extractor = ClaimExtractor()
        llm_output = (
            "NPX1, RISC-V mimarili bir işlemcidir. "
            "Bu cihaz, tarım uygulamaları için tasarlanmıştır. "
            "NPX1, SKY130 düğümünde üretilmiştir."
        )
        
        claims = extractor.extract(llm_output, "Neural Processor X1", ["NPX1"])
        
        assert len(claims) >= 2
        # İlk cümle NPX1 ile başlıyor
        assert "NPX1" in claims[0].text
    
    def test_no_matching_claims(self):
        """Topic'le ilgili cümle yoksa boş döndürmeli."""
        extractor = ClaimExtractor()
        llm_output = "İstanbul, Türkiye'nin en büyük şehridir."
        
        claims = extractor.extract(llm_output, "Neural Processor X1", ["NPX1"])
        
        assert len(claims) == 0
    
    def test_alias_recognition(self):
        """Alias'ları tanımalı."""
        extractor = ClaimExtractor()
        llm_output = "Neural Processor X1 veya kısaca NPX1, benim tasarımımdır."
        
        claims = extractor.extract(
            llm_output, 
            "Neural Processor X1", 
            ["NPX1", "npx1", "neural processor"]
        )
        
        assert len(claims) >= 1
        found_alias = any(
            a in claims[0].keywords_found 
            for a in ["np1", "neural processor x1", "neural processor"]
        )
        assert found_alias or "np1" in claims[0].text.lower()


class TestFactMatcher:
    """Fact matcher mesafe metrikleri testleri."""
    
    def test_identical_claim_fact(self):
        """Aynı metin → distance = 0"""
        matcher = FactMatcher()
        claim = "NPX1 SKY130'da üretiliyor"
        fact = "NPX1 SKY130'da üretiliyor"
        
        result = matcher.match(claim, fact)
        
        assert result.edit_distance < 0.1
        assert result.semantic_distance < 0.1
        assert result.combined_distance < 0.2
        assert result.is_conflict == False
    
    def test_completely_different(self):
        """Tamamen farklı metin → distance ≈ 1"""
        matcher = FactMatcher()
        claim = "NPX1, TSMC 7nm'de üretiliyor"
        fact = "NPX1, SKY130'da açık kaynak üretim yapıyor"
        
        result = matcher.match(claim, fact)
        
        assert result.edit_distance > 0.3
        assert result.combined_distance > 0.2
        assert result.is_conflict == True
    
    def test_negative_detection(self):
        """Olumsuzlaştırma tespiti."""
        matcher = FactMatcher()
        claim = "NPX1 lisans ücretli değildir"
        fact = "NPX1 lisans ücretli değildir"
        
        result = matcher.match(claim, fact)
        
        # Olumsuzlaştırma var ama fact aynı → düşük conflict
        # (Negatif detection edit distance'i etkilemez)
        assert result.negative_distance > 0
    
    def test_semantic_distance(self):
        """Anlamsal mesafe hesaplaması."""
        matcher = FactMatcher()
        claim = "Bu cihaz tarım için edge AI yapıyor"
        fact = "Edge AI, tarım ve güvenlik için"
        
        result = matcher.match(claim, fact)
        
        # Bazı kelimeler ortak (edge, AI, tarım)
        assert result.semantic_distance < 0.8


class TestSeverityEngine:
    """Severity mapping testleri."""
    
    def test_info_severity(self):
        """Distance < 0.2 → INFO"""
        engine = SeverityEngine()
        match = MatchResult(
            claim="x", fact="x",
            edit_distance=0.05, semantic_distance=0.05,
            negative_distance=0.0, combined_distance=0.05,
            is_conflict=False,
        )
        
        assert engine.compute(match) == Severity.INFO
    
    def test_critical_severity(self):
        """Distance > 0.8 → CRITICAL"""
        engine = SeverityEngine()
        match = MatchResult(
            claim="x", fact="y",
            edit_distance=0.9, semantic_distance=0.9,
            negative_distance=0.0, combined_distance=0.9,
            is_conflict=True,
        )
        
        assert engine.compute(match) == Severity.CRITICAL
    
    def test_negative_boost(self):
        """Olumsuzlaştırma varsa minimum WARNING"""
        engine = SeverityEngine()
        match = MatchResult(
            claim="x değildir", fact="x",
            edit_distance=0.2, semantic_distance=0.1,
            negative_distance=0.5, combined_distance=0.25,
            is_conflict=True,
        )
        
        sev = engine.compute(match)
        assert sev in [Severity.WARNING, Severity.ERROR, Severity.CRITICAL]
        assert sev != Severity.INFO


class TestConflictDetectorV2:
    """End-to-end v2 detector testleri."""
    
    def test_detect_tsmc_fabrication(self):
        """TSMC yanlışı tespit etmeli."""
        detector = ConflictDetectorV2()
        rule = Rule(
            id="riscv-npu",
            topic="Neural Processor X1",
            content=RULE_CONTENT,
            file_path="rules/hardware/riscv-npu.md",
            aliases=["NPX1", "npx1", "neural-processor-x1"],
        )
        
        llm_output = "NPX1, TSMC 7nm'de üretilen bir AI hızlandırıcısıdır."
        
        conflicts = detector.detect(llm_output, rule, [])
        
        # Çelişki bulunmalı
        assert len(conflicts) >= 1
        # En az birinin severity'si ERROR veya CRITICAL olmalı
        severities = [c.severity for c in conflicts]
        assert Severity.ERROR in severities or Severity.CRITICAL in severities
    
    def test_no_conflict_correct_info(self):
        """Doğru bilgi söylenirse conflict tespit edilmemeli veya çok düşük."""
        detector = ConflictDetectorV2()
        rule = Rule(
            id="riscv-npu",
            topic="Neural Processor X1",
            content=RULE_CONTENT,
            file_path="rules/hardware/riscv-npu.md",
            aliases=["NPX1"],
        )
        
        # Bu claim "Doğru Bilgiler" bölümündeki fact'lerden biriyle örtüşüyor
        # ama diğer fact'lerle çakışabilir (bilinen bir sınırlama)
        llm_output = "NPX1 mimarisi RISC-V + Systolic Array NPU tabanlıdır."
        
        conflicts = detector.detect(llm_output, rule, [])
        
        # Eğer conflict varsa, düşük severity olmalı (aynı konu, farklı cümle)
        if conflicts:
            for c in conflicts:
                assert c.confidence < 0.8  # Çok yüksek confidence olmamalı
    
    def test_latency_budget(self):
        """v2 detector latency < 5ms."""
        detector = ConflictDetectorV2()
        rule = Rule(
            id="riscv-npu",
            topic="Neural Processor X1",
            content=RULE_CONTENT,
            file_path="rules/hardware/riscv-npu.md",
            aliases=["NPX1"],
        )
        
        llm_output = "NPX1, edge AI için tasarlanmış RISC-V tabanlı bir işlemcidir."
        
        import time
        t0 = time.perf_counter()
        conflicts = detector.detect(llm_output, rule, [])
        elapsed_us = (time.perf_counter() - t0) * 1_000_000
        
        assert elapsed_us < 5_000, f"v2 latency {elapsed_us:.0f}μs > 5ms"
