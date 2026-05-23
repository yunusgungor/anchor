"""
Anchor — Ana test suite'i.
"""

import pytest
from pathlib import Path
from anchor import Rule, Conflict, Severity, Topic
from anchor.engine import AnchorEngine


# === Test Env ===

RULES_PATH = str(Path(__file__).parent.parent / "rules")


@pytest.fixture(scope="session")
def engine():
    eng = AnchorEngine(RULES_PATH)
    eng.build()
    return eng


# === Topic Extraction Tests ===

class TestTopicExtraction:
    
    def test_extract_direct_query(self, engine):
        """Kullanıcı sorusundan direkt topic eşleştirme."""
        topics = engine.extractor.extract(
            "Neural Processor X1 hakkında bilgi ver",
            "Bu bir işlemci tasarımıdır..."
        )
        assert len(topics) > 0
        assert any("Neural Processor X1" in t.name or "neural-processor-x1" in t.name for t in topics)
    
    def test_extract_alias(self, engine):
        """Alias ile topic eşleştirme."""
        topics = engine.extractor.extract(
            "NPX1 nedir?",
            "NPX1 bir işlemcidir..."
        )
        assert len(topics) > 0
        names = [t.name for t in topics]
        assert any("NPX1" not in n for n in names)  # NPX1 → Neural Processor X1'e map olmalı
    
    def test_extract_no_match(self, engine):
        """Eşleşmeyen sorgu → boş sonuç."""
        topics = engine.extractor.extract(
            "Bugün hava nasıl?",
            "Hava güneşli ve 25 derece."
        )
        assert len(topics) == 0


# === Rule Store Tests ===

class TestRuleStore:
    
    def test_rules_loaded(self, engine):
        """Tüm rule'lar yüklendi mi?"""
        assert len(engine.store._rules) >= 4  # En az 4 rule olmalı
    
    def test_topic_index(self, engine):
        """Topic index çalışıyor mu?"""
        result = engine.store.query(["Neural Processor X1"])
        assert len(result) >= 1
    
    def test_alias_lookup(self, engine):
        """Alias ile lookup çalışıyor mu?"""
        # NPX1 alias ile ara
        result = engine.store.query(["NPX1"])
        assert len(result) >= 1  # Alias index'ten topic'e map olup rule döndürmeli
    
    def test_hot_cache(self, engine):
        """Hot cache çalışıyor mu?"""
        # İlk çağrı
        r1 = engine.store.query(["StateGuard Agent"])
        # İkinci çağrı (cache'ten)
        r2 = engine.store.query(["StateGuard Agent"])
        assert len(r1) == len(r2)
        assert r1[0].id == r2[0].id if r1 and r2 else True


# === Conflict Detection Tests ===

class TestConflictDetection:
    
    def test_detect_wrong_fabrication(self, engine):
        """LLM 'TSMC 7nm' derse → çelişki tespit etmeli."""
        rule = engine.store._rules.get("riscv-npu")
        assert rule is not None, "riscv-npu rule yüklenmeli"
        
        conflicts = engine.detector.detect(
            "NPX1, TSMC'nin 7nm düğümünde üretilen bir AI hızlandırıcısıdır.",
            rule, []
        )
        critical_conflicts = [c for c in conflicts if c.severity in (Severity.ERROR, Severity.CRITICAL)]
        assert len(critical_conflicts) >= 1
    
    def test_detect_correct_info(self, engine):
        """LLM doğru bilgi verirse → çelişki yok."""
        rule = engine.store._rules.get("riscv-npu")
        assert rule is not None
        
        conflicts = engine.detector.detect(
            "NPX1, SKY130 PDK ile üretilen edge AI için bir işlemcidir.",
            rule, []
        )
        critical_conflicts = [c for c in conflicts if c.severity in (Severity.ERROR, Severity.CRITICAL)]
        assert len(critical_conflicts) == 0
    
    def test_detect_stateguard_misconcept(self, engine):
        """LLM 'StateGuard bir güvenlik duvarıdır' derse → çelişki."""
        rule = engine.store._rules.get("state-guard")
        assert rule is not None
        
        conflicts = engine.detector.detect(
            "StateGuard bir güvenlik duvarı aracıdır.",
            rule, []
        )
        assert len(conflicts) >= 1


# === Full Pipeline Tests ===

class TestPipeline:
    
    def test_full_pipeline_modification(self, engine):
        """LLM yanlış bilgi verirse → pipeline düzeltmeli."""
        result = engine.process(
            "NPX1 hakkında bilgi ver",
            "NPX1, TSMC 7nm'de üretilen genel amaçlı bir AI hızlandırıcısıdır."
        )
        assert result.modified, "Pipeline yanlış bilgiyi düzeltmeli"
        
        # Düzeltilmiş metinde SKY130 geçmeli
        assert "SKY130" in result.corrected or "130nm" in result.corrected
    
    def test_full_pipeline_no_modification(self, engine):
        """LLM doğru bilgi verirse → değişiklik yok."""
        result = engine.process(
            "Hava durumu",
            "Bugün hava güneşli, 25 derece."
        )
        assert not result.modified, "İlgisiz konuda düzeltme olmamalı"
    
    def test_full_pipeline_stateguard(self, engine):
        """StateGuard için pipeline testi."""
        result = engine.process(
            "StateGuard nedir?",
            "StateGuard bir güvenlik duvarı aracıdır."
        )
        assert result.modified
        assert "validasyon" in result.corrected.lower() or "doğrulama" in result.corrected.lower()
    
    def test_latency_budget(self, engine):
        """Latency budget kontrolü (< 20ms)."""
        result = engine.process(
            "SKY130 hakkında bilgi",
            "SKY130, Global Foundries'in 28nm düğümüdür."  # İki hata
        )
        total_us = result.latency_us.get('total', 0)
        assert total_us < 20_000, f"Latency budget aşıldı: {total_us}μs > 20ms"
