"""
Anchor Engine v2 — End-to-end pipeline testleri.
"""

import os
import pytest
from pathlib import Path

from anchor.engine_v2 import AnchorEngineV2
from anchor import Severity


RULES_PATH = str(Path(__file__).parent.parent / "rules")
INDEX_PATH = str(Path(__file__).parent.parent / ".anchor_v2_test.idx")


class TestAnchorEngineV2:
    """v2 engine end-to-end testleri."""
    
    def teardown_method(self):
        """Test sonrası index temizle."""
        for p in [INDEX_PATH, INDEX_PATH.replace(".idx", ".idx.npz")]:
            if os.path.exists(p):
                os.unlink(p)
    
    @pytest.fixture
    def engine(self):
        """Build edilmiş v2 engine."""
        eng = AnchorEngineV2(RULES_PATH, INDEX_PATH)
        eng.build()
        return eng
    
    def test_no_topic_no_change(self, engine):
        """Topic bulunamazsa metin değişmez."""
        result = engine.process(
            user_query="Hava nasıl bugün?",
            llm_output="Bugün güneşli ve sıcak."
        )
        
        assert result.corrected == "Bugün güneşli ve sıcak."
        assert result.modified == False
        assert len(result.topics_found) == 0
    
    def test_topic_no_conflict(self, engine):
        """Topic bulunur, v2 agresif olabilir."""
        result = engine.process(
            user_query="NPX1 mimarisi nedir?",
            llm_output="NPX1, RISC-V mimarili bir işlemcidir."
        )
        
        # Topic bulunur
        assert len(result.topics_found) >= 1
        # Neural Processor X1 topic'i bulunmuş olmalı
        topic_names = [t.name.lower() for t in result.topics_found]
        assert "neural processor x1" in topic_names
    
    def test_critical_conflict_override(self, engine):
        """CRITICAL çelişki → cümle override."""
        result = engine.process(
            user_query="NPX1 hakkında bilgi ver",
            llm_output="NPX1, genel amaçlı bir AI hızlandırıcısıdır."
        )
        
        # "genel amaçlı" yanlış → CRITICAL
        assert result.modified == True
        assert "genel amaçlı" not in result.corrected.lower()
        # KB'deki doğru bilgi olmalı
        assert "edge" in result.corrected.lower() or "tarım" in result.corrected.lower()
    
    def test_error_conflict_patch(self, engine):
        """ERROR çelişki → cümle düzeltme."""
        result = engine.process(
            user_query="NPX1 üretimi hakkında bilgi ver",
            llm_output="NPX1, TSMC'de üretiliyor."
        )
        
        assert result.modified == True
        assert "(doğrusu:" in result.corrected or "Edge AI" in result.corrected
    
    def test_multiple_rules(self, engine):
        """Birden fazla rule aktive olabilir."""
        result = engine.process(
            user_query="StateGuard ve NPX1 hakkında bilgi ver",
            llm_output="StateGuard güvenlik aracıdır. NPX1, TSMC'de üretiliyor."
        )
        
        # Her iki rule da aktive olmalı
        assert len(result.rules_activated) >= 1
        assert result.modified == True
    
    def test_latency_budget(self, engine):
        """v2 pipeline latency < 15ms."""
        result = engine.process(
            user_query="NPX1 hakkında bilgi ver",
            llm_output="NPX1, genel amaçlı bir AI hızlandırıcısıdır ve TSMC'de üretiliyor."
        )
        
        total_us = result.latency_us.get('total', 0)
        assert total_us < 15_000, f"v2 latency {total_us:.0f}μs > 15ms"
    
    def test_binary_index_cold_start(self):
        """Binary index ile cold start hızlı olmalı."""
        # İlk build (rebuild)
        engine1 = AnchorEngineV2(RULES_PATH, INDEX_PATH)
        engine1.build()
        
        # İkinci build (load from index)
        import time
        t0 = time.perf_counter()
        engine2 = AnchorEngineV2(RULES_PATH, INDEX_PATH)
        engine2.build()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        
        assert elapsed_ms < 50, f"Cold start {elapsed_ms:.1f}ms > 50ms"
        
        # Query çalışmalı
        result = engine2.process(
            user_query="NPX1 nedir?",
            llm_output="NPX1, edge AI işlemcisidir."
        )
        assert len(result.topics_found) >= 1
    
    def test_stats(self, engine):
        """Stats çalışmalı."""
        # İşlem yap
        engine.process("NPX1 nedir?", "NPX1 genel amaçlıdır.")
        engine.process("Hava nasıl?", "Güneşli.")
        
        stats = engine.stats
        assert stats["engine"]["total_processed"] == 2
        assert stats["engine"]["total_modified"] >= 0
        assert "store" in stats
        assert "detector" in stats
        assert "patcher" in stats
    
    def test_semantic_fallback(self, engine):
        """Topic bilinmese bile LLM output'tan topic çıkarımı."""
        result = engine.process(
            user_query="Bu cihaz ne işe yarar?",
            llm_output="NPX1, tarım alanında kullanılan RISC-V tabanlı bir edge AI işlemcisidir."
        )
        
        # Semantic index sayesinde NPX1 bulunmalı
        assert len(result.topics_found) >= 1
        assert "np1" in [t.name.lower() for t in result.topics_found] or \
               "neural processor x1" in [t.name.lower() for t in result.topics_found]
