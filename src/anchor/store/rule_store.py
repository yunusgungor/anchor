"""
Rule Store — Rules dosyalarını depolama, indexleme ve gerçek zamanlı erişim.

Üç katmanlı mimari:
  Tier 1: Hot Cache (LRU, sık kullanılan rule'lar)
  Tier 2: Index (in-memory hash index'ler)
  Tier 3: File System (disk, git-versioned)
"""

import hashlib
import json
import re
from collections import defaultdict, OrderedDict
from pathlib import Path
from typing import Optional

from anchor import Rule
from anchor.parser.frontmatter import parse_frontmatter, extract_content, extract_metadata


class RuleStore:
    """
    Rules deposu. Tüm index'leri yönetir.
    
    Performans hedefleri:
      - 10K rule, < 0.5ms lookup
      - Hot reload < 1ms
      - Rebuild < 100ms
    """
    
    def __init__(self, rules_path: str):
        self.path = Path(rules_path)
        
        # Tier 1: Hot Cache (LRU)
        self._hot_cache: OrderedDict[str, Rule] = OrderedDict()
        self._hot_cache_max = 100
        
        # Tier 2: Index'ler
        self._rules: dict[str, Rule] = {}           # rule_id → Rule
        self._topic_index: dict[str, set[str]] = defaultdict(set)    # topic → {rule_id}
        self._alias_index: dict[str, set[str]] = defaultdict(set)    # alias → {rule_id}
        self._tag_index: dict[str, set[str]] = defaultdict(set)      # tag → {rule_id}
        self._keyword_index: dict[str, list[tuple[str, float]]] = defaultdict(list)
        
        # Extraction referansı (topic extractor'ın register_rule çağırması için)
        self._extractor = None
        
        # İstatistik
        self._hits = 0
        self._misses = 0
        self._total_lookups = 0
    
    def set_extractor(self, extractor):
        """Topic extractor referansını ata (callbacks için)."""
        self._extractor = extractor
    
    def build(self):
        """Tüm index'i yeniden inşa et."""
        self._rules.clear()
        self._topic_index.clear()
        self._alias_index.clear()
        self._tag_index.clear()
        self._keyword_index.clear()
        self._hot_cache.clear()
        
        for fpath in self.path.rglob("*.md"):
            try:
                rule = self._parse_file(fpath)
                self._add_rule(rule)
            except Exception as e:
                print(f"⚠️  Rule parse hatası: {fpath} — {e}")
        
        print(f"✅  Anchor KB: {len(self._rules)} rule yüklendi")
    
    def hot_reload(self, changed_path: Optional[str] = None):
        """Tek bir dosya değişince sadece onu güncelle."""
        if changed_path:
            fpath = Path(changed_path)
            if fpath.suffix != '.md':
                return
            
            # Eski rule'ı bul ve kaldır
            for rid, rule in list(self._rules.items()):
                if rule.file_path == str(fpath):
                    self._remove_rule(rid)
                    break
            
            # Yenisini ekle
            try:
                rule = self._parse_file(fpath)
                self._add_rule(rule)
            except Exception as e:
                print(f"⚠️  Hot reload hatası: {fpath} — {e}")
        else:
            self.build()
    
    def query(self, topics: list[str]) -> list[Rule]:
        """
        Topic listesine göre ilgili rule'ları bul.
        
        Strateji:
          1. topic_index'ten direkt eşleştir
          2. alias_index'ten fallback
          3. tag_index'ten genişlet
          4. Priority'ye göre sırala, top-K döndür
        """
        self._total_lookups += 1
        candidate_ids: set[str] = set()
        
        # 1. Topic index
        for topic in topics:
            topic_lower = topic.lower()
            candidate_ids |= self._topic_index.get(topic_lower, set())
        
        # 2. Alias index fallback
        if not candidate_ids:
            for topic in topics:
                topic_lower = topic.lower()
                candidate_ids |= self._alias_index.get(topic_lower, set())
        
        # 3. Tag index genişletme (sadece az sonuç varsa)
        if len(candidate_ids) < 3:
            for topic in topics:
                topic_lower = topic.lower()
                candidate_ids |= self._tag_index.get(topic_lower, set())
        
        # Sonuçları topla
        results = []
        for rid in candidate_ids:
            rule = self._get_cached(rid)
            if rule:
                results.append(rule)
        
        # Priority'ye göre sırala
        results.sort(key=lambda r: (-r.priority, r.id))
        
        return results[:10]  # En fazla 10 rule
    
    def _parse_file(self, fpath: Path) -> Rule:
        """Bir .md dosyasını parse edip Rule nesnesine çevir."""
        text = fpath.read_text(encoding='utf-8')
        rule_id = fpath.stem
        
        # Frontmatter utility kullan
        content = extract_content(text)
        meta = extract_metadata(text, rule_id)
        
        topic = meta["topic"]
        aliases = meta["aliases"]
        tags = meta["tags"]
        priority = meta["priority"]
        strictness = meta["strictness"]
        
        return Rule(
            id=rule_id,
            topic=topic,
            content=content,
            file_path=str(fpath),
            aliases=aliases if isinstance(aliases, list) else [aliases],
            tags=tags if isinstance(tags, list) else [tags],
            priority=priority,
            strictness=strictness
        )
    
    def _add_rule(self, rule: Rule):
        """Rule'u tüm index'lere ekle."""
        self._rules[rule.id] = rule
        
        # Topic index
        topic_lower = rule.topic.lower()
        self._topic_index[topic_lower].add(rule.id)
        
        # Alias index
        for alias in rule.aliases:
            self._alias_index[alias.lower()].add(rule.id)
        
        # Tag index
        for tag in rule.tags:
            self._tag_index[tag.lower()].add(rule.id)
        
        # Keyword index (önemli terimler)
        for term in self._extract_keywords(rule.content):
            self._keyword_index[term.lower()].append((rule.id, 1.0))
        
        # Extractor'a kaydet
        if self._extractor:
            self._extractor.register_rule(
                topic=rule.topic,
                aliases=rule.aliases,
                tags=rule.tags,
                content=rule.content
            )
    
    def _remove_rule(self, rule_id: str):
        """Rule'u tüm index'lerden kaldır."""
        if rule_id not in self._rules:
            return
        
        rule = self._rules[rule_id]
        
        # Topic index
        self._topic_index[rule.topic.lower()].discard(rule_id)
        
        # Alias index
        for alias in rule.aliases:
            self._alias_index[alias.lower()].discard(rule_id)
        
        # Tag index
        for tag in rule.tags:
            self._tag_index[tag.lower()].discard(rule_id)
        
        # Cache
        self._hot_cache.pop(rule_id, None)
        
        # Rules dict
        del self._rules[rule_id]
    
    def _get_cached(self, rule_id: str) -> Optional[Rule]:
        """LRU cache üzerinden rule getir."""
        if rule_id in self._hot_cache:
            # LRU: kullanıldı → sona taşı
            rule = self._hot_cache.pop(rule_id)
            self._hot_cache[rule_id] = rule
            self._hits += 1
            return rule
        
        rule = self._rules.get(rule_id)
        if rule:
            # Hot cache'e ekle
            self._hot_cache[rule_id] = rule
            if len(self._hot_cache) > self._hot_cache_max:
                self._hot_cache.popitem(last=False)
            self._misses += 1
        
        return rule
    
    def _extract_keywords(self, content: str) -> list[str]:
        """Content'ten keyword'leri çıkar."""
        keywords = set()
        
        # Bold terimler
        for m in re.finditer(r'\*\*(.+?)\*\*', content):
            keywords.add(m.group(1))
        
        # Kod bloklarındaki terimler (ilk satır)
        for m in re.finditer(r'```\w*\n(.+?)\n', content):
            first_line = m.group(1).strip()
            if len(first_line) < 50:
                keywords.add(first_line)
        
        # Pipe tablosundaki ilk kolon
        for m in re.finditer(r'^\|\s*([^|]+?)\s*\|', content, re.MULTILINE):
            kw = m.group(1).strip()
            if kw and kw != '---' and len(kw) < 30:
                keywords.add(kw)
        
        return list(keywords)
    
    @property
    def stats(self) -> dict:
        return {
            "total_rules": len(self._rules),
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "total_lookups": self._total_lookups,
            "hit_ratio": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0
        }
