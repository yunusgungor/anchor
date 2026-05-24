"""
Bloom Index — Negatif lookup için O(1) probabilistik filtre.

Mantık:
  - "Bu konuyla ilgili hiç rule yok mu?" sorusuna HAYIR/MAYBE cevabı verir.
  - HAYIR → %100 doğru (hiç rule yok, arama yapmaya gerek yok)
  - MAYBE → Rule olabilir, detaylı aramaya devam et
  
Bu, 10.000 rule arasında gereksiz hash lookup'ları önler.

Implementasyon:
  - Python set ile lightweight versiyon (gerçek bit-array yerine hash set)
  - m = 100.000 bucket, k = 3 hash fonksiyonu
  - Faux Bloom: basitçe tüm topic/alias/tag'leri bir set'te tut
    (küçük ölçekte gerçek Bloom Filter'a gerek yok, set yeterli)
"""

import hashlib
from pathlib import Path


class BloomIndex:
    """
    Lightweight topic membership index.
    
    Gerçek bir Bloom Filter yerine (bitarray bağımlılığı),
    hash tabanlı bir "muhtemelen içerir" index.
    """
    
    def __init__(self, expected_items: int = 10_000, false_positive_rate: float = 0.01):
        self._set: set[str] = set()
        self._expected = expected_items
        self._fp_rate = false_positive_rate
        self._hash_count = self._optimal_k(expected_items, self._optimal_m(expected_items, false_positive_rate))
    
    def _optimal_m(self, n: int, p: float) -> int:
        """Optimal bit array boyutu: m = -(n * ln(p)) / (ln(2)^2)"""
        import math
        return int(-(n * math.log(p)) / (math.log(2) ** 2))
    
    def _optimal_k(self, n: int, m: int) -> int:
        """Optimal hash fonksiyonu sayısı: k = (m/n) * ln(2)"""
        import math
        return max(1, int((m / n) * math.log(2)))
    
    def add(self, item: str):
        """Bir topic/alias/tag ekle."""
        self._set.add(item.lower())
    
    def add_many(self, items: list[str]):
        """Birden fazla item ekle."""
        for item in items:
            self.add(item)
    
    def contains(self, item: str) -> bool:
        """
        Item muhtemelen içeride mi?
        
        Returns:
            False → %100 dışarıda (hiç rule yok)
            True  → Olabilir (detaylı aramaya devam et)
        """
        return item.lower() in self._set
    
    def check_topics(self, topics: list[str]) -> tuple[bool, list[str]]:
        """
        Topic listesini kontrol et.
        
        Returns:
            (any_match, matching_topics)
            any_match: En az bir topic index'te var mı?
            matching_topics: Hangi topic'ler bulundu?
        """
        matches = []
        for topic in topics:
            if self.contains(topic):
                matches.append(topic)
        return len(matches) > 0, matches
    
    def build_from_rules(self, rules_path: str):
        """Bir rules klasöründen tüm topic/alias/tag'leri index'e ekle."""
        from anchor.parser.frontmatter import extract_all_topics_and_aliases_from_dir
        items = extract_all_topics_and_aliases_from_dir(rules_path)
        for item in items:
            self._set.add(item)
    
    @property
    def size(self) -> int:
        return len(self._set)
    
    def stats(self) -> dict:
        return {
            "indexed_items": self.size,
            "expected_capacity": self._expected,
            "hash_functions": self._hash_count,
            "false_positive_rate_target": self._fp_rate,
        }
