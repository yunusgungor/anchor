"""
Topic Extraction — LLM çıktısından konu çıkarma.

Tamamen deterministik. Hiçbir LLM çağrısı yok.
Üç kaynak kullanır:
  1. Kullanıcının sorusu (en güvenilir sinyal)
  2. Regex pattern eşleştirme (teknik terimler)
  3. Prefix tree (trie) üzerinde akış arama
"""

import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

from anchor import Topic


class TrieNode:
    """Prefix tree düğümü."""
    __slots__ = ('children', 'topics')
    
    def __init__(self):
        self.children: dict[str, 'TrieNode'] = {}
        self.topics: list[str] = []


class TopicTrie:
    """Konu eşleştirme için prefix tree."""
    
    def __init__(self):
        self.root = TrieNode()
    
    def insert(self, phrase: str, topic: str):
        """Bir phrase ve onun hangi topic'e ait olduğunu ekle."""
        node = self.root
        words = phrase.lower().split()
        for word in words:
            if word not in node.children:
                node.children[word] = TrieNode()
            node = node.children[word]
        node.topics.append(topic)
    
    def search(self, words: list[str], start: int, max_depth: int = 5) -> list[str]:
        """start pozisyonundan itibaren max_depth kelime tara, eşleşen topic'leri döndür."""
        node = self.root
        found = []
        end = min(start + max_depth, len(words))
        
        for i in range(start, end):
            word = words[i].lower().strip('.,;:!?()[]{}""\'')
            if not word:
                break
            if word in node.children:
                node = node.children[word]
                if node.topics:
                    found.extend(node.topics)
            else:
                break
        
        return found


class PatternMatcher:
    """Regex pattern'leri ile teknik terim eşleştirme."""
    
    def __init__(self):
        self.patterns: list[tuple[re.Pattern, str]] = []
    
    def add_pattern(self, regex: str, topic: str):
        """Bir regex pattern'i ve eşleştiği topic'i ekle."""
        self.patterns.append((re.compile(regex, re.IGNORECASE), topic))
    
    def match(self, text: str) -> list[str]:
        """Metindeki tüm eşleşmeleri döndür."""
        found = []
        for pattern, topic in self.patterns:
            if pattern.search(text):
                found.append(topic)
        return found


class TopicExtractor:
    """
    Deterministic topic extraction.
    
    Strateji:
      1. Kullanıcı sorusundan direkt topic eşleştirme
      2. LLM çıktısında regex pattern arama
      3. Trie üzerinde n-gram akış arama
    
    Hiçbir adımda LLM çağrılmaz.
    """
    
    def __init__(self):
        # Topic → alias listesi
        self.topic_aliases: dict[str, list[str]] = {}
        # Regex pattern matcher
        self.patterns = PatternMatcher()
        # Prefix tree
        self.trie = TopicTrie()
        
        # İstatistik
        self._total_calls = 0
        self._total_latency_us = 0
    
    def register_rule(self, topic: str, aliases: list[str], tags: list[str], content: str):
        """Bir rule'u topic extractor'a kaydet."""
        # Alias index
        self.topic_aliases[topic] = aliases
        
        # Trie: topic başlığını ekle
        self.trie.insert(topic, topic)
        for alias in aliases:
            self.trie.insert(alias, topic)
        
        # Regex: content'ten teknik terim pattern'leri çıkar
        # (Her rule'un içindeki önemli terimler)
        important_terms = self._extract_important_terms(content)
        for term in important_terms:
            if len(term.split()) <= 3:  # Kısa terimler
                self.patterns.add_pattern(r'\b' + re.escape(term) + r'\b', topic)
    
    def _extract_important_terms(self, content: str) -> set[str]:
        """Content'ten önemli terimleri çıkar (code block ve yorumlardan arındırılmış)."""
        terms = set()
        
        # Markdown başlıkları
        for match in re.finditer(r'^#{1,3}\s+(.+)$', content, re.MULTILINE):
            terms.add(match.group(1).strip())
        
        # Bold text
        for match in re.finditer(r'\*\*(.+?)\*\*', content):
            terms.add(match.group(1))
        
        # Korkuluk tablosundaki terimler
        for match in re.finditer(r'\|\s*([^|]+?)\s*\|', content):
            term = match.group(1).strip()
            if term and term not in ('Konu', '---', ''):
                terms.add(term)
        
        return terms
    
    def extract(self, user_query: str, llm_output: str) -> list[Topic]:
        """
        Ana extraction metodu.
        
        Args:
            user_query: Kullanıcının sorusu
            llm_output: LLM'in ürettiği ham çıktı
            
        Returns:
            Çıkarılan topic'ler (confidence'a göre sıralı)
        """
        import time
        t0 = time.perf_counter()
        self._total_calls += 1
        
        found: dict[str, float] = {}
        
        # === Kaynak 1: Kullanıcı sorusu (en güvenilir) ===
        query_lower = user_query.lower()
        for topic, aliases in self.topic_aliases.items():
            if topic.lower() in query_lower:
                found[topic] = max(found.get(topic, 0), 1.0)
            for alias in aliases:
                if alias.lower() in query_lower:
                    found[topic] = max(found.get(topic, 0), 0.95)
        
        # === Kaynak 2: Regex pattern'leri ===
        for topic in self.patterns.match(llm_output):
            found[topic] = max(found.get(topic, 0), 0.8)
        
        # === Kaynak 3: Trie akış arama ===
        words = self._tokenize(llm_output)
        for i in range(len(words)):
            matches = self.trie.search(words, i, max_depth=3)
            for topic in matches:
                found[topic] = max(found.get(topic, 0), 0.7)
        
        # Ayrıca kullanıcı sorusunda da trie ara
        query_words = self._tokenize(user_query)
        for i in range(len(query_words)):
            matches = self.trie.search(query_words, i, max_depth=3)
            for topic in matches:
                found[topic] = max(found.get(topic, 0), 0.9)
        
        # Sonuçları confidence'a göre sırala
        result = [
            Topic(name=topic, confidence=score,
                  source="query" if score >= 1.0 else 
                         "alias" if score >= 0.95 else
                         "pattern" if score >= 0.8 else "content")
            for topic, score in sorted(found.items(), key=lambda x: -x[1])
        ]
        
        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000
        
        return result
    
    def _tokenize(self, text: str) -> list[str]:
        """Basit tokenization."""
        return re.findall(r'\b[a-zA-Z0-9_-]+\b', text)
    
    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
