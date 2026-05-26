"""
Binary Index Serialization — Cold start optimizasyonu testleri.
"""

import os
import shutil
import time
from pathlib import Path

import pytest

from anchor.store.scale_store import ScalableRuleStore
from anchor.store.binary_index import BinaryIndexManager


RULES_PATH = str(Path(__file__).parent.parent / "rules")
INDEX_DIR = str(Path(__file__).parent.parent / ".anchor_test_index")


class TestBinaryIndex:
    """Binary index lifecycle testleri."""
    
    def teardown_method(self):
        """Her test sonrası index dosyalarını temizle."""
        if os.path.exists(INDEX_DIR):
            shutil.rmtree(INDEX_DIR)
    
    def test_first_build_creates_index(self):
        """İlk build → binary index oluşturulmalı."""
        store = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store.build()
        
        # Index dosyaları oluşmuş mu?
        idx_file = os.path.join(INDEX_DIR, "binary_index.json")
        npz_file = os.path.join(INDEX_DIR, "binary_index.npz")
        assert os.path.exists(idx_file), f"{idx_file} oluşmadı"
        assert os.path.exists(npz_file), f"{npz_file} oluşmadı"
    
    def test_second_load_from_index(self):
        """İkinci build → index'ten yükle (rebuild etme)."""
        # 1. İlk build (rebuild)
        store1 = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store1.build()
        
        # 2. İkinci build (load from index)
        store2 = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store2.build()
        
        # Aynı sonuçlar?
        results = store2.query(["clean-architecture"])
        assert len(results) >= 1
        assert results[0].id == "clean-architecture"
    
    def test_stale_detection(self):
        """Rules dizini değişince index stale olmalı."""
        store = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store.build()
        
        # Index fresh olmalı
        assert not store._binman.is_stale()
        
        # Bir rule dosyasını "değiştir" (touch)
        rule_file = Path(RULES_PATH) / "architecture" / "clean-architecture.md"
        if rule_file.exists():
            # mtime'ı değiştir
            os.utime(rule_file, None)
            # Stale olmalı
            assert store._binman.is_stale()
    
    def test_cold_start_benchmark(self):
        """Cold start latency benchmark."""
        # Index oluştur
        store1 = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store1.build()
        
        # Cold start (load)
        t0 = time.perf_counter()
        store2 = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store2.build()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        
        print(f"\n  Cold start: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 200  # Hedef: < 100ms (bloom+semantic rebuild dahil)
    
    def test_query_after_load(self):
        """Index'ten yüklendikten sonra query çalışmalı."""
        store1 = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store1.build()
        
        store2 = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store2.build()
        
        # Topic query
        results = store2.query(["clean-architecture"])
        assert len(results) >= 1
        
        # Semantic query (topic yok)
        results2 = store2.query(
            topics=[],
            llm_output="single responsibility principle open closed Liskov substitution"
        )
        assert len(results2) >= 1
    
    def test_invalidate_and_rebuild(self):
        """Index invalidate → sonraki build rebuild yapmalı."""
        store1 = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store1.build()
        
        # Invalidate
        store1._binman.invalidate()
        assert not os.path.exists(INDEX_DIR)
        
        # Rebuild
        store2 = ScalableRuleStore(RULES_PATH, INDEX_DIR)
        store2.build()
        
        idx_file = os.path.join(INDEX_DIR, "binary_index.json")
        assert os.path.exists(idx_file)
        results = store2.query(["clean-architecture"])
        assert len(results) >= 1
