"""
Scalable Rule Store — 10.000+ rule için optimize edilmiş depolama.

Özellikler:
  - Domain Sharding: Sadece ilgili shard'ları yükle
  - Bloom Filter: Hızlı negatif lookup
  - Semantic Index: TF-IDF ile anlamsal eşleştirme
  - Lazy Loading: Rule içeriği sadece ihtiyaç anında parse edilir
  - Binary Cache: Serialize edilmiş index (cold start < 50ms)
"""

import logging
import pickle
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from anchor import Rule, Topic
from anchor.organize.domain_shard import ShardRouter
from anchor.organize.bloom_index import BloomIndex
from anchor.organize.semantic_index import SemanticIndex
from anchor.store.rule_store import RuleStore
from anchor.store.binary_index import BinaryIndexManager
from anchor.parser.frontmatter import extract_topic, extract_metadata

if TYPE_CHECKING:
    from anchor.judge.enricher import RuleEnricher

logger = logging.getLogger(__name__)


class ScalableRuleStore:
    """
    Büyük ölçekli rule deposu.
    
    Mevcut RuleStore'un aksine, tüm rule'ları başlangıçta yüklemez.
    Bunun yerine:
      1. Binary Index (cold start < 50ms)
      2. Domain Sharding → hangi shard'lar gerekli?
      3. Bloom Filter → bu shard'ta ilgili rule var mı?
      4. Semantic Index → en yakın rule'lar hangileri?
      5. Lazy Load → sadece gerekli rule'ların içeriğini parse et
    """
    
    def __init__(self, rules_path: str, index_path: Optional[str] = None,
                 enricher: Optional["RuleEnricher"] = None):
        self.path = Path(rules_path)
        self._router = ShardRouter(rules_path)
        self._bloom = BloomIndex(expected_items=10_000, false_positive_rate=0.01)
        self._semantic = SemanticIndex(max_features=2000)
        self._binman = BinaryIndexManager(rules_path, index_path)
        self._enricher = enricher
        
        # Hot cache (LRU)
        self._hot_cache: OrderedDict[str, Rule] = OrderedDict()
        self._hot_cache_max = 200
        
        # Shard içindeki rule ID'ler (topic → list[rule_id])
        self._shard_topic_map: dict[str, list[str]] = {}
        
        # Rule metadata for lazy load (id → {topic, priority, strictness, path})
        self._rule_meta: dict[str, dict] = {}
        
        # İstatistik
        self._hits = 0
        self._misses = 0
        self._lazy_loads = 0
        self._bloom_skips = 0
        
        self._built = False
    
    def build(self):
        """
        Index'leri inşa et. Önce binary index dene, yoksa rebuild et.
        """
        # 1. Binary index var ve fresh mi?
        if not self._binman.is_stale():
            loaded = self._binman.load()
            if loaded:
                self._shard_topic_map = loaded["shard_map"]
                self._bloom = loaded["bloom"]
                self._semantic = loaded["semantic"]
                self._rule_meta = {r["id"]: r for r in loaded.get("rule_metadata", [])}
                self._built = True
                return
        
        # 2. Yoksa rebuild et
        self._rebuild()
    
    def _rebuild(self):
        """Tüm index'leri sıfırdan inşa et ve diske kaydet."""
        t0 = time.perf_counter()
        
        # Shard'ları keşfet
        
        # Bloom Filter
        self._bloom.build_from_rules(str(self.path))
        
        # Semantic Index
        self._semantic.fit(str(self.path))
        
        # Shard-topic mapping + metadata
        rule_metadata = []
        for shard_name in self._router.list_shards():
            shard_path = self._router.get_shard_path(shard_name)
            if not shard_path:
                continue
            for fpath in shard_path.rglob("*.md"):
                rule_id = fpath.stem
                topic = self._extract_topic_from_file(fpath) or rule_id
                
                self._shard_topic_map.setdefault(topic.lower(), []).append(rule_id)
                self._shard_topic_map.setdefault(rule_id.lower(), []).append(rule_id)
                
                # Metadata
                aliases, tags, priority, strictness = self._extract_meta_from_file(fpath)
                meta = {
                    "id": rule_id,
                    "topic": topic,
                    "path": str(fpath),
                    "aliases": aliases,
                    "tags": tags,
                    "priority": priority,
                    "strictness": strictness,
                }
                
                # Build-time enrichment: facts'in paraphrase'larını üret
                if self._enricher is not None:
                    try:
                        text = fpath.read_text(encoding="utf-8")
                        enriched = self._enricher.enrich_rule(text)
                        if enriched:
                            meta["enriched_facts"] = enriched
                            logger.debug("Enriched %s: %d facts → %d",
                                         rule_id, len(enriched) // 3, len(enriched))
                    except Exception as e:
                        logger.warning("Enrichment failed for %s: %s", rule_id, e)
                
                self._rule_meta[rule_id] = meta
                rule_metadata.append(meta)
        
        self._built = True
        
        # Binary index'e kaydet
        self._binman.save(
            shard_map=self._shard_topic_map,
            bloom=self._bloom,
            semantic=self._semantic,
            rule_metadata=rule_metadata,
        )
        
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("ScalableStore rebuild: %.1fms | shards=%d | bloom=%d | vectors=%d",
                     elapsed, len(self._router.list_shards()), self._bloom.size,
                     self._semantic.stats()['indexed_vectors'])
    
    def _extract_topic_from_file(self, fpath: Path) -> Optional[str]:
        """Sadece topic çıkar — tam parse değil (utility kullanır)."""
        try:
            text = fpath.read_text(encoding="utf-8")
            return extract_topic(text)
        except Exception:
            pass
        return None
    
    def _extract_meta_from_file(self, fpath: Path) -> tuple:
        """Frontmatter'dan metadata çıkar (utility kullanır)."""
        try:
            text = fpath.read_text(encoding="utf-8")
            meta = extract_metadata(text, fpath.stem)
            return (
                meta["aliases"],
                meta["tags"],
                meta["priority"],
                meta["strictness"],
            )
        except Exception:
            pass
        return [], [], 5, 0.8
    
    def query(self, topics: list[str], llm_output: str = "") -> list[Rule]:
        """
        Topic'lere göre rule ara — büyük ölçekli versiyon.
        
        Algoritma:
          1. Bloom Filter: Hiçbir topic eşleşmiyorsa → boş döndür (~1μs)
          2. Router: Hangi shard'lar gerekli? (~1μs)
          3. Semantic: LLM output'undan ek rule önerileri (~100μs)
          4. Lazy Load: Sadece gerekli rule'ları parse et ve cache'le
        """
        if not self._built:
            self.build()
        
        # 0. Eğer topics boş ama llm_output varsa → direkt semantic
        if not topics and llm_output:
            semantic_hits = self._semantic.query(llm_output, top_k=5)
            candidate_ids: set[str] = set()
            for rule_id, sim in semantic_hits:
                if sim > 0.15:
                    candidate_ids.add(rule_id)
            results = []
            for rid in candidate_ids:
                rule = self._get_cached_or_load(rid)
                if rule:
                    results.append(rule)
            results.sort(key=lambda r: (-r.priority, r.id))
            return results[:10]
        
        # 1. Bloom Filter — negatif lookup
        has_any, bloom_matches = self._bloom.check_topics(topics)
        if not has_any:
            self._bloom_skips += 1
            return []
        
        # 2. Router — shard'ları belirle
        shards = self._router.route(topics)
        candidate_ids: set[str] = set()
        
        # Topic + alias exact match (shard içinde)
        for topic in topics:
            topic_lower = topic.lower()
            candidate_ids.update(self._shard_topic_map.get(topic_lower, []))
            # Ayrıca stem'leri dene
            parts = topic_lower.split()
            for i in range(len(parts)):
                partial = " ".join(parts[i:])
                candidate_ids.update(self._shard_topic_map.get(partial, []))
        
        # 3. Semantic fallback (eğer az sonuç varsa)
        if len(candidate_ids) < 3 and llm_output:
            semantic_hits = self._semantic.query(llm_output, top_k=5)
            for rule_id, sim in semantic_hits:
                if sim > 0.15:  # Threshold
                    candidate_ids.add(rule_id)
        
        if not candidate_ids:
            return []
        
        # 4. Lazy Load + Cache
        results = []
        for rid in candidate_ids:
            rule = self._get_cached_or_load(rid)
            if rule:
                results.append(rule)
        
        # Priority'ye göre sırala (yüksek öncelikli önce)
        results.sort(key=lambda r: (-r.priority, r.id))
        return results[:10]
    
    def _get_cached_or_load(self, rule_id: str) -> Optional[Rule]:
        """Cache'ten al, yoksa diskten lazy load et."""
        # Cache hit?
        if rule_id in self._hot_cache:
            rule = self._hot_cache.pop(rule_id)
            self._hot_cache[rule_id] = rule  # LRU: sona taşı
            self._hits += 1
            return rule
        
        # Diskten bul
        rule = self._lazy_load(rule_id)
        if rule:
            # Hot cache'e ekle
            self._hot_cache[rule_id] = rule
            if len(self._hot_cache) > self._hot_cache_max:
                self._hot_cache.popitem(last=False)
            self._misses += 1
        
        return rule
    
    def _lazy_load(self, rule_id: str) -> Optional[Rule]:
        """Diskten bir rule'u parse et, enriched facts varsa ekle."""
        # rule_id → dosya yolunu bul
        for fpath in self.path.rglob(f"{rule_id}.md"):
            if fpath.is_file():
                try:
                    from anchor import Rule
                    rule = Rule.from_file(fpath)
                    # Enriched facts varsa rule objesine ekle
                    meta = self._rule_meta.get(rule_id, {})
                    enriched = meta.get("enriched_facts", [])
                    if enriched:
                        rule.enriched_facts = enriched
                    return rule
                except Exception:
                    pass
        return None
    
    def stats(self) -> dict:
        total_lookups = self._hits + self._misses
        return {
            "total_rules": len(self._shard_topic_map) // 2,  # topic + rule_id duplicates
            "shards": len(self._router.list_shards()),
            "bloom_items": self._bloom.size,
            "semantic_vocab": self._semantic.stats()["vocab_size"],
            "cache_size": len(self._hot_cache),
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "hit_ratio": self._hits / total_lookups if total_lookups > 0 else 0,
            "bloom_skips": self._bloom_skips,
            "lazy_loads": self._lazy_loads,
        }
