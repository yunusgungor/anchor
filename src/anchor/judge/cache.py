"""
Judge Cache — Deterministic caching for LLM-as-Judge decisions.

Aynı (claim, fact) çifti her zaman aynı sonucu döndürür.
Bu sayede LLM çağrıları azaltılır ve determinizm korunur.
"""

import hashlib
import json
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class JudgeVerdict:
    """LLM judge kararı."""
    is_conflict: bool
    reason: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "is_conflict": self.is_conflict,
            "reason": self.reason,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "JudgeVerdict":
        return cls(
            is_conflict=d.get("is_conflict", False),
            reason=d.get("reason", ""),
            confidence=d.get("confidence", 0.5),
        )


class JudgeCache:
    """
    Thread-safe LRU cache for judge verdicts.
    
    Varsayılan max 1000 entry → ~200KB bellek.
    Her entry: md5(claim + "|" + fact) → JudgeVerdict
    """

    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, JudgeVerdict] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, claim: str, fact: str) -> str:
        """Normalize edilmiş key — aynı içerik aynı key."""
        normalized = f"{claim.strip().lower()}|{fact.strip().lower()}"
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def get(self, claim: str, fact: str) -> Optional[JudgeVerdict]:
        """Cache'te varsa döndür, yoksa None."""
        key = self._make_key(claim, fact)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, claim: str, fact: str, verdict: JudgeVerdict):
        """Verdict'i cache'e ekle."""
        key = self._make_key(claim, fact)
        with self._lock:
            self._cache[key] = verdict
            self._cache.move_to_end(key)
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": self._hits / total if total > 0 else 0,
        }

    def save(self, path: str):
        """Cache'i diske kaydet (JSON)."""
        data = {
            k: v.to_dict()
            for k, v in self._cache.items()
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        logger.info("Judge cache saved: %d entries", len(data))

    def load(self, path: str):
        """Cache'i diskten yükle."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                for k, v in data.items():
                    self._cache[k] = JudgeVerdict.from_dict(v)
            logger.info("Judge cache loaded: %d entries", len(data))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug("No judge cache to load: %s", e)
