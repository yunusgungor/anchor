"""
Conflict Detection v2 — Sentence-level claim extraction + edit distance.

ClaimExtractor: LLM output'undan konuyla ilgili cümleleri çıkar
FactMatcher: KB fact'leriyle claim'leri karşılaştır
SeverityEngine: Distance → severity mapping
"""

from .claim_extractor import ClaimExtractor
from .fact_matcher import FactMatcher
from .severity_engine import SeverityEngine

__all__ = ["ClaimExtractor", "FactMatcher", "SeverityEngine"]
