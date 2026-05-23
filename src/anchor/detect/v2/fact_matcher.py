r"""
Fact Matcher v2 — KB fact'leri ile LLM claim'leri arasındaki mesafeyi hesapla.

Metrikler:
  1. Edit Distance (Levenshtein) — kelime-level fark
  2. Cosine Distance (TF-IDF) — anlamsal fark
  3. Negative Detection — olumsuzlaştırma ("değil", "not", "yanlış")

$$D(c, f) = \alpha \cdot D_{edit}(c, f) + \beta \cdot D_{sem}(c, f) + \gamma \cdot D_{neg}(c)$$
"""

import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

import numpy as np


@dataclass
class MatchResult:
    """Bir claim-fact eşleştirme sonucu."""
    claim: str
    fact: str
    edit_distance: float      # 0-1 normalize edilmiş
    semantic_distance: float  # 0-1
    negative_distance: float  # 0-1
    combined_distance: float  # Ağırlıklı toplam
    is_conflict: bool         # Çelişki var mı?


class FactMatcher:
    """
    KB'deki bir fact ile LLM'in claim'i arasındaki mesafeyi ölçer.
    """
    
    def __init__(self, alpha: float = 0.4, beta: float = 0.4, gamma: float = 0.2):
        self.alpha = alpha      # Edit distance ağırlığı
        self.beta = beta        # Semantic distance ağırlığı
        self.gamma = gamma      # Negative detection ağırlığı
        
        self._total_calls = 0
        self._total_latency_us = 0
    
    def match(self, claim: str, fact: str) -> MatchResult:
        """
        Bir claim ile bir fact arasındaki mesafeyi hesapla.
        
        Args:
            claim: LLM'in söylediği cümle
            fact: KB'deki doğru bilgi
            
        Returns:
            MatchResult (tüm mesafe metrikleri)
        """
        import time
        t0 = time.perf_counter()
        self._total_calls += 1
        
        # 1. Edit Distance
        d_edit = self._compute_edit_distance(claim, fact)
        
        # 2. Semantic Distance (TF-IDF cosine)
        d_sem = self._compute_semantic_distance(claim, fact)
        
        # 3. Negative Detection
        d_neg = self._compute_negative_distance(claim)
        
        # Combined
        d_combined = self.alpha * d_edit + self.beta * d_sem + self.gamma * d_neg
        
        # Çelişki: hem edit distance hem semantic distance yüksekse
        is_conflict = d_combined > 0.4
        
        result = MatchResult(
            claim=claim,
            fact=fact,
            edit_distance=d_edit,
            semantic_distance=d_sem,
            negative_distance=d_neg,
            combined_distance=d_combined,
            is_conflict=is_conflict,
        )
        
        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000
        
        return result
    
    def _compute_edit_distance(self, claim: str, fact: str) -> float:
        """
        Levenshtein edit distance — normalize edilmiş (0-1).
        
        0 = tamamen aynı
        1 = tamamen farklı
        """
        # SequenceMatcher (Python stdlib)
        sm = SequenceMatcher(None, claim.lower(), fact.lower())
        similarity = sm.ratio()  # 0-1, 1 = aynı
        return 1.0 - similarity  # distance'e çevir
    
    def _compute_semantic_distance(self, claim: str, fact: str) -> float:
        """
        Basit kelime ağırlıklı cosine distance.
        
        Kelime listeleri oluştur, TF-IDF'siz basit word overlap.
        Gelişmiş versiyon: ScalableStore'daki TF-IDF vektörlerini kullan.
        """
        # Tokenize
        claim_words = set(self._tokenize(claim))
        fact_words = set(self._tokenize(fact))
        
        if not claim_words or not fact_words:
            return 1.0
        
        # Jaccard distance (basit versiyon)
        intersection = len(claim_words & fact_words)
        union = len(claim_words | fact_words)
        
        if union == 0:
            return 1.0
        
        jaccard_sim = intersection / union
        return 1.0 - jaccard_sim
    
    def _compute_negative_distance(self, claim: str) -> float:
        """
        Claim'de olumsuzlaştırma var mı?
        
        "değil", "not", "yanlış", "wrong" gibi kelimeler →
        claim'in fact'in zıttını söylediğini gösterir.
        """
        negative_markers = [
            r'\bdeğil\w*\b', r'\bnot\b', r'\bno\b',
            r'\byanlış\b', r'\bwrong\b', r'\bfalse\b',
            r'\bhatalı\b', r'\binvalid\b', r'\bincorrect\b',
            r'\bünlem\b', r'\bnever\b', r'\bnone\b',
        ]
        
        claim_lower = claim.lower()
        hit_count = 0
        
        for pattern in negative_markers:
            if re.search(pattern, claim_lower):
                hit_count += 1
        
        # Normalize: 0-3 arası hit → 0-1 arası distance
        return min(1.0, hit_count / 3.0)
    
    def _tokenize(self, text: str) -> list[str]:
        """Basit tokenization."""
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        stopwords = {
            'bir', 've', 'bu', 'için', 'ile', 'olan', 'gibi', 'kadar',
            'the', 'and', 'for', 'with', 'this', 'that', 'from', 'is', 'are',
        }
        return [w for w in words if w not in stopwords and len(w) > 2]
    
    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
