"""
Anchor Organize — Büyük ölçekli index ve erişim testleri.
"""

import pytest
from pathlib import Path

from anchor.organize.domain_shard import ShardRouter
from anchor.organize.bloom_index import BloomIndex
from anchor.organize.semantic_index import SemanticIndex
from anchor.store.scale_store import ScalableRuleStore


RULES_PATH = str(Path(__file__).parent.parent / "rules")


class TestDomainSharding:
    """Domain-based shard routing testleri."""
    
    def test_shard_discovery(self):
        """Shard'lar otomatik keşfedilmeli."""
        router = ShardRouter(RULES_PATH)
        shards = router.list_shards()
        assert len(shards) >= 3  # hardware, projects, concepts
        assert "hardware" in shards
        assert "projects" in shards
        assert "concepts" in shards
    
    def test_topic_to_shard_routing(self):
        """Topic → shard eşlemesi çalışmalı."""
        router = ShardRouter(RULES_PATH)
        shards = router.route(["Neural Processor X1"])
        assert "hardware" in shards
    
    def test_alias_routing(self):
        """Alias ile shard routing çalışmalı."""
        router = ShardRouter(RULES_PATH)
        shards = router.route(["NPX1"])
        # NPX1 alias'ı riscv-npu.md'de, bu hardware shard'ında
        assert "hardware" in shards
    
    def test_no_match_routing(self):
        """Eşleşmeyen topic → boş shard set."""
        router = ShardRouter(RULES_PATH)
        shards = router.route(["kripto para", "hava durumu"])
        assert len(shards) == 0


class TestBloomIndex:
    """Probabilistic membership testleri."""
    
    def test_build_from_rules(self):
        """Bloom filter rules'dan build edilmeli."""
        bloom = BloomIndex(expected_items=1000)
        bloom.build_from_rules(RULES_PATH)
        assert bloom.size > 0
        # En az topic, alias, tag, başlık kadar item olmalı
        assert bloom.size >= 10
    
    def test_positive_membership(self):
        """Var olan topic → True."""
        bloom = BloomIndex()
        bloom.build_from_rules(RULES_PATH)
        assert bloom.contains("Neural Processor X1") is True
        assert bloom.contains("riscv-npu") is True
        assert bloom.contains("SKY130") is True
    
    def test_negative_membership(self):
        """Olmayan topic → False (kesin dışarıda)."""
        bloom = BloomIndex()
        bloom.build_from_rules(RULES_PATH)
        assert bloom.contains("Bitcoin fiyatı") is False
        assert bloom.contains("ABD başkanı") is False
    
    def test_check_topics_batch(self):
        """Birden fazla topic kontrolü."""
        bloom = BloomIndex()
        bloom.build_from_rules(RULES_PATH)
        has_any, matches = bloom.check_topics(["Neural Processor X1", "Bitcoin"])
        assert has_any is True
        assert "Neural Processor X1" in matches
        assert "Bitcoin" not in matches


class TestSemanticIndex:
    """TF-IDF semantic similarity testleri."""
    
    def test_fit(self):
        """Semantic index fit edilmeli."""
        idx = SemanticIndex(max_features=500)
        idx.fit(RULES_PATH)
        stats = idx.stats()
        assert stats["indexed_vectors"] > 0
        assert stats["vocab_size"] > 0
    
    def test_query_similarity(self):
        """Query ile en yakın rule'ları bul."""
        idx = SemanticIndex(max_features=500)
        idx.fit(RULES_PATH)
        
        # NPX1 hakkında bir metin
        results = idx.query("RISC-V tabanlı edge AI işlemcisi", top_k=3)
        assert len(results) > 0
        # En yüksek skorlu rule riscv-npu olmalı
        top_id = results[0][0]
        assert "riscv" in top_id or "npu" in top_id
    
    def test_query_no_match(self):
        """Alakasız metin → düşük skor veya boş."""
        idx = SemanticIndex(max_features=500)
        idx.fit(RULES_PATH)
        
        results = idx.query("Bugün hava çok güzel", top_k=3)
        # Çok düşük skorlu veya boş olmalı
        if results:
            assert all(sim < 0.5 for _, sim in results)


class TestScalableStore:
    """Büyük ölçekli store entegrasyon testleri."""
    
    def test_lazy_loading(self):
        """Rule'lar lazy load edilmeli."""
        store = ScalableRuleStore(RULES_PATH)
        store.build()
        
        # Başlangıçta cache boş
        assert len(store._hot_cache) == 0
        
        # Sorgu yap → lazy load
        results = store.query(["Neural Processor X1"])
        assert len(results) >= 1
        assert results[0].id == "riscv-npu"
        
        # Şimdi cache'te olmalı
        assert len(store._hot_cache) >= 1
    
    def test_bloom_skip(self):
        """Olmayan konu → bloom filter hemen reddetmeli."""
        store = ScalableRuleStore(RULES_PATH)
        store.build()
        
        before = store.stats()["bloom_skips"]
        results = store.query(["Bitcoin fiyatı"])
        after = store.stats()["bloom_skips"]
        
        assert len(results) == 0
        assert after > before
    
    def test_semantic_fallback(self):
        """LLM output'u varsa semantic index devreye girmeli (topic çıkarımı yoksa bile)."""
        store = ScalableRuleStore(RULES_PATH)
        store.build()
        
        # Topic boş, sadece LLM output'u var
        results = store.query(
            topics=[],
            llm_output="NPX1 is an edge AI processor using RISC-V architecture for agricultural applications"
        )
        # Semantic index sayesinde riscv-npu bulunmalı
        assert len(results) >= 1
