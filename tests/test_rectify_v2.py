"""
Rectification v2 Testleri — Sentence-level patch engine.
"""

import pytest

from anchor import Conflict, Severity
from anchor.rectify.v2.patch_engine import PatchEngine, PatchStrategy


class TestPatchEngine:
    """Patch engine stratejileri testleri."""
    
    def test_info_strategy(self):
        """INFO → dipnot ekleme."""
        engine = PatchEngine()
        llm = "NPX1, TSMC 7nm'de üretilen bir cihazdır."
        
        conflicts = [
            Conflict(
                rule_id="riscv-npu",
                topic="NPX1",
                severity=Severity.INFO,
                llm_claim="NPX1, TSMC 7nm'de üretilen bir cihazdır.",
                kb_fact="SKY130'da üretiliyor",
                patch_position=0,
                confidence=0.2,
            )
        ]
        
        result, patches = engine.apply(llm, conflicts)
        
        assert "📝 **Not:**" in result
        assert "SKY130'da üretiliyor" in result
        assert len(patches) == 1
        assert patches[0].strategy == PatchStrategy.APPEND_NOTE
    
    def test_warning_strategy(self):
        """WARNING → cümleden sonra ekleme."""
        engine = PatchEngine()
        llm = "NPX1, edge AI için tasarlanmıştır."
        
        conflicts = [
            Conflict(
                rule_id="riscv-npu",
                topic="NPX1",
                severity=Severity.WARNING,
                llm_claim="NPX1, edge AI için tasarlanmıştır.",
                kb_fact="Edge AI, tarım ve güvenlik için özel olarak optimize edilmiştir",
                patch_position=0,
                confidence=0.4,
            )
        ]
        
        result, patches = engine.apply(llm, conflicts)
        
        assert "Ancak kayıtlarıma göre:" in result
        assert patches[0].strategy == PatchStrategy.INSERT_AFTER
    
    def test_error_strategy(self):
        """ERROR → cümle düzeltme (orijinal + doğru)."""
        engine = PatchEngine()
        llm = "NPX1, TSMC'de üretiliyor."
        
        conflicts = [
            Conflict(
                rule_id="riscv-npu",
                topic="NPX1",
                severity=Severity.ERROR,
                llm_claim="NPX1, TSMC'de üretiliyor.",
                kb_fact="SKY130'da, OpenLane ile üretiliyor",
                patch_position=0,
                confidence=0.6,
            )
        ]
        
        result, patches = engine.apply(llm, conflicts)
        
        assert "(doğrusu:" in result
        assert "SKY130'da, OpenLane ile üretiliyor" in result
        assert patches[0].strategy == PatchStrategy.PATCH_SENTENCE
    
    def test_critical_strategy(self):
        """CRITICAL → cümle override (tamamen değiştir)."""
        engine = PatchEngine()
        llm = "NPX1, genel amaçlı bir AI hızlandırıcısıdır."
        
        conflicts = [
            Conflict(
                rule_id="riscv-npu",
                topic="NPX1",
                severity=Severity.CRITICAL,
                llm_claim="NPX1, genel amaçlı bir AI hızlandırıcısıdır.",
                kb_fact="Edge AI işlemcisi, tarım ve güvenlik uygulamaları için",
                patch_position=0,
                confidence=0.9,
            )
        ]
        
        result, patches = engine.apply(llm, conflicts)
        
        # Orijinal cümle yerine KB'deki doğru olmalı
        assert "genel amaçlı" not in result
        assert "Edge AI işlemcisi" in result
        assert patches[0].strategy == PatchStrategy.OVERRIDE_SENTENCE
    
    def test_multiple_conflicts(self):
        """Birden fazla çelişki → en yüksek severity önce uygulanır."""
        engine = PatchEngine()
        llm = "NPX1, TSMC 7nm'de üretilen genel amaçlı bir AI hızlandırıcısıdır."
        
        conflicts = [
            Conflict(
                rule_id="riscv-npu",
                topic="NPX1",
                severity=Severity.CRITICAL,
                llm_claim="NPX1, TSMC 7nm'de üretilen genel amaçlı bir AI hızlandırıcısıdır.",
                kb_fact="Edge AI işlemcisi, SKY130'da üretilen",
                patch_position=0,
                confidence=0.9,
            ),
            Conflict(
                rule_id="riscv-npu",
                topic="NPX1",
                severity=Severity.INFO,
                llm_claim="NPX1, TSMC 7nm'de üretilen genel amaçlı bir AI hızlandırıcısıdır.",
                kb_fact="Ayrıca RISC-V mimarili",
                patch_position=0,
                confidence=0.1,
            ),
        ]
        
        result, patches = engine.apply(llm, conflicts)
        
        # CRITICAL önce uygulanır → cümle override
        assert "Edge AI işlemcisi" in result
        # Sonra INFO → dipnot
        assert "📝 **Not:**" in result
    
    def test_no_conflict(self):
        """Çelişki yoksa metin değişmez."""
        engine = PatchEngine()
        llm = "NPX1, SKY130'da üretilen bir edge AI işlemcisidir."
        
        result, patches = engine.apply(llm, [])
        
        assert result == llm
        assert len(patches) == 0
    
    def test_latency_budget(self):
        """Patch latency < 1ms."""
        engine = PatchEngine()
        llm = "NPX1, TSMC'de üretiliyor."
        
        conflicts = [
            Conflict(
                rule_id="riscv-npu",
                topic="NPX1",
                severity=Severity.ERROR,
                llm_claim="NPX1, TSMC'de üretiliyor.",
                kb_fact="SKY130'da üretiliyor",
                patch_position=0,
                confidence=0.7,
            )
        ]
        
        import time
        t0 = time.perf_counter()
        result, _ = engine.apply(llm, conflicts)
        elapsed_us = (time.perf_counter() - t0) * 1_000_000
        
        assert elapsed_us < 1_000, f"Patch latency {elapsed_us:.0f}μs > 1ms"
