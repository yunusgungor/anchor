"""
Anchor Engine — End-to-end rectification pipeline.

Pipeline:
  A1: Topic Extraction    → < 1ms
  A2: Knowledge Retrieval → < 2ms (binary index + lazy load)
  A3: Conflict Detection  → < 5ms (claim extraction + fact matching)
  A4: Rectification       → < 1ms (sentence-level patch)
  ─────────────────────────────────────
  TOTAL: < 10ms
"""

import time
from pathlib import Path
from typing import Optional

from anchor import (
    Conflict, Correction, RectificationResult,
    Rule, Severity, Topic
)
from anchor.store.scale_store import ScalableRuleStore
from anchor.detect import (
    ClaimExtractor, ConflictDetector
)
from anchor.rectify import PatchEngine


class AnchorEngine:
    """
    Anchor — LLM çıktıları için deterministik rectification engine.
    
    Kullanım:
        engine = AnchorEngine(rules_path="rules/")
        engine.build()
        
        result = engine.process(
            user_query="RISC-V NPU hakkında bilgi ver",
            llm_output="RISC-V NPU, genel amaçlı bir AI hızlandırıcıdır..."
        )
        
        if result.modified:
            print(result.corrected)
            print(result.summary)
    """
    
    def __init__(self, rules_path: str, index_path: Optional[str] = None):
        self.store = ScalableRuleStore(rules_path, index_path)
        self.extractor = ClaimExtractor()
        self.detector = ConflictDetector()
        self.patcher = PatchEngine()
        
        # İstatistik
        self._total_processed = 0
        self._total_modified = 0
    
    def build(self):
        """Index'leri inşa et (binary index varsa yükle, yoksa rebuild)."""
        self.store.build()
        
        # Topic extractor'ı rule'larla populate et
        for rule_id, meta in self.store._rule_meta.items():
            self.extractor.register_rule(
                topic=meta["topic"],
                aliases=meta.get("aliases", []),
                tags=meta.get("tags", []),
                content="",
            )
    
    def hot_reload(self):
        """Index'i yeniden build et (rules değişince)."""
        self.store.build()
    
    def process(self, user_query: str, llm_output: str) -> RectificationResult:
        """
        Ana v2 pipeline.
        
        Args:
            user_query: Kullanıcının orijinal sorusu
            llm_output: LLM'in ürettiği ham çıktı
            
        Returns:
            RectificationResult (düzeltilmiş çıktı + rapor)
        """
        timings = {}
        
        # === A1: Topic Extraction ===
        t0 = time.perf_counter()
        raw_topics = self.extractor.extract(user_query, llm_output)
        t1 = time.perf_counter()
        timings['topic_extraction'] = (t1 - t0) * 1_000_000
        
        # Claim listesini Topic listesine dönüştür (backward compat)
        from anchor import Topic
        topics = []
        topic_names = set()
        for claim in raw_topics:
            for kw in claim.keywords_found:
                if kw not in topic_names:
                    topic_names.add(kw)
                    topics.append(Topic(name=kw, confidence=claim.confidence))
        
        # Eğer hiç topic bulunamazsa, query'den topic dene
        if not topics:
            for rule_id, meta in self.store._rule_meta.items():
                if meta["topic"].lower() in user_query.lower():
                    topics.append(Topic(name=meta["topic"], confidence=0.8))
                    break
                for alias in meta.get("aliases", []):
                    if alias.lower() in user_query.lower():
                        topics.append(Topic(name=meta["topic"], confidence=0.7))
                        break
        
        topic_names = [t.name for t in topics]
        
        # === A2: Knowledge Retrieval ===
        # Scalable store: bloom → semantic → lazy load
        rules = self.store.query(topic_names, llm_output)
        t2 = time.perf_counter()
        timings['knowledge_retrieval'] = (t2 - t1) * 1_000_000
        
        if not rules:
            result = RectificationResult(
                original=llm_output,
                corrected=llm_output,
                topics_found=topics,
                latency_us=timings,
                modified=False
            )
            self._total_processed += 1
            return result
        
        # === A3: Conflict Detection (v2) ===
        all_conflicts: list[Conflict] = []
        for rule in rules:
            conflicts = self.detector.detect(llm_output, rule, topics)
            all_conflicts.extend(conflicts)
        t3 = time.perf_counter()
        timings['conflict_detection'] = (t3 - t2) * 1_000_000
        
        # === A4: Rectification (v2 patch engine) ===
        if all_conflicts:
            corrected_text, patches = self.patcher.apply(llm_output, all_conflicts)
            
            # Corrections listesi oluştur
            corrections = []
            for patch in patches:
                # Patch'ten corresponding conflict'i bul
                conflict = next(
                    (c for c in all_conflicts if c.llm_claim == patch.original),
                    None
                )
                if conflict:
                    corrections.append(Correction(
                        conflict=conflict,
                        original_text=patch.original,
                        corrected_text=patch.replacement,
                    ))
            
            result = RectificationResult(
                original=llm_output,
                corrected=corrected_text,
                corrections=corrections,
                topics_found=topics,
                rules_activated=[r.id for r in rules],
                latency_us=timings,
                modified=True
            )
        else:
            result = RectificationResult(
                original=llm_output,
                corrected=llm_output,
                topics_found=topics,
                rules_activated=[r.id for r in rules],
                latency_us=timings,
                modified=False
            )
        
        t4 = time.perf_counter()
        result.latency_us['total'] = (t4 - t0) * 1_000_000
        
        self._total_processed += 1
        if result.modified:
            self._total_modified += 1
        
        return result
    
    @property
    def stats(self) -> dict:
        return {
            "engine": {
                "total_processed": self._total_processed,
                "total_modified": self._total_modified,
                "modification_rate": self._total_modified / max(self._total_processed, 1),
            },
            "store": self.store.stats(),
            "detector": {
                "avg_latency_us": self.detector.avg_latency_us,
            },
            "patcher": {
                "avg_latency_us": self.patcher.avg_latency_us,
            },
        }
