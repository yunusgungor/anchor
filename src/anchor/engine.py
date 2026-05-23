"""
Anchor Engine — Ana orkestrasyon katmanı.

Tüm pipeline'ı yönetir:
  Topic Extraction → Knowledge Retrieval → Conflict Detection → Rectification
"""

import time
from pathlib import Path
from typing import Optional

from anchor import (
    Conflict, Correction, RectificationResult, 
    Rule, Severity, Topic
)
from anchor.store.rule_store import RuleStore
from anchor.detect.topic_extractor import TopicExtractor
from anchor.detect.conflict_detector import ConflictDetector
from anchor.rectify.rectifier import Rectifier


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
    
    def __init__(self, rules_path: str):
        self.store = RuleStore(rules_path)
        self.extractor = TopicExtractor()
        self.detector = ConflictDetector()
        self.rectifier = Rectifier()
        
        # Store'a extractor referansını ver (callback'ler için)
        self.store.set_extractor(self.extractor)
        
        # İstatistik
        self._total_processed = 0
        self._total_modified = 0
    
    def build(self):
        """Index'leri inşa et."""
        self.store.build()
    
    def hot_reload(self, changed_path: Optional[str] = None):
        """Rules dosyası değişince index'i güncelle."""
        self.store.hot_reload(changed_path)
    
    def process(self, user_query: str, llm_output: str) -> RectificationResult:
        """
        Ana pipeline.
        
        Args:
            user_query: Kullanıcının orijinal sorusu
            llm_output: LLM'in ürettiği ham çıktı
            
        Returns:
            RectificationResult (düzeltilmiş çıktı + rapor)
        """
        timings = {}
        
        # === A1: Topic Extraction ===
        t0 = time.perf_counter()
        topics = self.extractor.extract(user_query, llm_output)
        t1 = time.perf_counter()
        timings['topic_extraction'] = (t1 - t0) * 1_000_000
        
        if not topics:
            result = RectificationResult(
                original=llm_output,
                corrected=llm_output,
                latency_us=timings,
                modified=False
            )
            self._total_processed += 1
            return result
        
        # === A2: Knowledge Retrieval ===
        topic_names = [t.name for t in topics]
        rules = self.store.query(topic_names)
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
        
        # === A3: Conflict Detection ===
        all_conflicts: list[Conflict] = []
        for rule in rules:
            conflicts = self.detector.detect(llm_output, rule, topics)
            all_conflicts.extend(conflicts)
        t3 = time.perf_counter()
        timings['conflict_detection'] = (t3 - t2) * 1_000_000
        
        # === A4: Rectification ===
        result = self.rectifier.rectify(llm_output, all_conflicts)
        result.topics_found = topics
        result.rules_activated = [r.id for r in rules]
        result.latency_us.update(timings)
        
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
            "store": self.store.stats,
            "extractor": {
                "avg_latency_us": self.extractor.avg_latency_us,
            },
            "detector": {
                "avg_latency_us": self.detector.avg_latency_us,
            },
            "rectifier": {
                "avg_latency_us": self.rectifier.avg_latency_us,
            },
        }
