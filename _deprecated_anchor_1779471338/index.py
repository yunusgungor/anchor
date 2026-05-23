"""
Anchor: Rule Index

Binlerce rules dosyası arasında O(1) veya O(log n) arama sağlar.
Hiç LLM çağırmaz — tamamen hash tabanlı indeksleme.
"""

from collections import defaultdict
from pathlib import Path
from typing import Optional
import glob
import re

from .models import Rule


class RuleIndex:
    """
    Rules dosyaları için çok katmanlı indeks.
    
    Index Katmanları:
    1. topic_index: topic → set[Rule]
    2. alias_index: alias → set[Rule]
    3. tag_index: tag → set[Rule]
    4. hot_cache: rule_id → Rule (LRU benzeri)
    5. trie: Prefix tree (hızlı topic eşleme)
    """
    
    def __init__(self, rules_path: str):
        self.path = Path(rules_path)
        self.rules: dict[str, Rule] = {}  # rule_id → Rule
        self.topic_index: dict[str, set[str]] = defaultdict(set)
        self.alias_index: dict[str, set[str]] = defaultdict(set)
        self.tag_index: dict[str, set[str]] = defaultdict(set)
        self.hot_cache: dict[str, Rule] = {}  # LRU benzeri
        self.cache_order: list[str] = []
        
        self._build_index()
    
    def _build_index(self):
        """Tüm rules dosyalarını tara ve indeksle."""
        md_files = list(self.path.rglob("*.md"))
        
        for fpath in md_files:
            rule = Rule.from_file(fpath)
            self._add_rule(rule)
    
    def _add_rule(self, rule: Rule):
        """Bir rule'u indekse ekle."""
        self.rules[rule.id] = rule
        
        # Topic index
        self.topic_index[rule.topic].add(rule.id)
        
        # Alias index
        for alias in rule.aliases:
            self.alias_index[alias.lower()].add(rule.id)
        
        # Tag index
        for tag in rule.tags:
            self.tag_index[tag.lower()].add(rule.id)
    
    def _remove_rule(self, rule_id: str):
        """Belirli bir rule'u indeksten çıkar."""
        rule = self.rules.get(rule_id)
        if not rule:
            return
        
        # Topic index'ten kaldır
        if rule.topic in self.topic_index:
            self.topic_index[rule.topic].discard(rule_id)
            if not self.topic_index[rule.topic]:
                del self.topic_index[rule.topic]
        
        # Alias index'ten kaldır
        for alias in rule.aliases:
            if alias.lower() in self.alias_index:
                self.alias_index[alias.lower()].discard(rule_id)
                if not self.alias_index[alias.lower()]:
                    del self.alias_index[alias.lower()]
        
        # Tag index'ten kaldır
        for tag in rule.tags:
            if tag.lower() in self.tag_index:
                self.tag_index[tag.lower()].discard(rule_id)
                if not self.tag_index[tag.lower()]:
                    del self.tag_index[tag.lower()]
        
        # Cache'ten kaldır
        self.hot_cache.pop(rule_id, None)
        
        # Rules dict'ten kaldır
        self.rules.pop(rule_id, None)
    
    def _touch_cache(self, rule_id: str):
        """Cache'te bir rule'a erişildi olarak işaretle."""
        # En basit LRU: en son erişilen arkada
        if rule_id in self.cache_order:
            self.cache_order.remove(rule_id)
        self.cache_order.append(rule_id)
        
        # Cache limit (200 rule)
        while len(self.cache_order) > 200:
            oldest = self.cache_order.pop(0)
            self.hot_cache.pop(oldest, None)
    
    def find_by_topic(self, topic: str) -> list[Rule]:
        """Topic'e göre rule ara. O(1) hash lookup."""
        topic_lower = topic.lower()
        rule_ids = set()
        
        # Topic index
        rule_ids |= self.topic_index.get(topic_lower, set())
        rule_ids |= self.topic_index.get(topic, set())
        
        # Alias fallback
        rule_ids |= self.alias_index.get(topic_lower, set())
        
        # Load rules
        results = []
        for rid in rule_ids:
            if rid in self.hot_cache:
                results.append(self.hot_cache[rid])
            elif rid in self.rules:
                rule = self.rules[rid]
                self.hot_cache[rid] = rule
                self._touch_cache(rid)
                results.append(rule)
        
        # Priority'ye göre sırala
        results.sort(key=lambda r: r.priority, reverse=True)
        return results
    
    def find_by_tags(self, tags: list[str]) -> list[Rule]:
        """Etiketlere göre rule ara. Kesişim işlemi."""
        if not tags:
            return []
        
        rule_ids = None
        for tag in tags:
            tag_lower = tag.lower()
            ids = self.tag_index.get(tag_lower, set())
            if rule_ids is None:
                rule_ids = ids
            else:
                rule_ids &= ids
        
        if not rule_ids:
            return []
        
        results = []
        for rid in rule_ids:
            if rid in self.hot_cache:
                results.append(self.hot_cache[rid])
            elif rid in self.rules:
                rule = self.rules[rid]
                self.hot_cache[rid] = rule
                results.append(rule)
        
        results.sort(key=lambda r: r.priority, reverse=True)
        return results
    
    def hot_reload(self, changed_file: str):
        """Tek bir dosya değişince indeksi güncelle."""
        fpath = Path(changed_file)
        if not fpath.exists():
            return
        
        # Eski rule'u bul ve kaldır (varsa)
        old_rule_id = fpath.stem
        if old_rule_id in self.rules:
            self._remove_rule(old_rule_id)
        
        # Yeni rule'u ekle
        rule = Rule.from_file(fpath)
        self._add_rule(rule)
    
    def full_rebuild(self):
        """Tüm indeksi sıfırdan inşa et."""
        self.rules.clear()
        self.topic_index.clear()
        self.alias_index.clear()
        self.tag_index.clear()
        self.hot_cache.clear()
        self.cache_order.clear()
        self._build_index()
    
    @property
    def rule_count(self) -> int:
        return len(self.rules)
    
    @property
    def cache_size(self) -> int:
        return len(self.hot_cache)
    
    def stats(self) -> dict:
        return {
            "total_rules": self.rule_count,
            "cache_size": self.cache_size,
            "topic_count": len(self.topic_index),
            "alias_count": len(self.alias_index),
            "tag_count": len(self.tag_index),
        }
