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
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from anchor.judge.llm_judge import JudgeConfig
    from anchor.judge.enricher import RuleEnricher

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
    
    def __init__(self, rules_path: str, index_path: Optional[str] = None,
                 use_embedding: bool = False,
                 judge_config: Optional["JudgeConfig"] = None,
                 enricher: Optional["RuleEnricher"] = None):
        self.store = ScalableRuleStore(rules_path, index_path, enricher=enricher,
                                        use_embedding=use_embedding)
        self.extractor = ClaimExtractor()
        self.detector = ConflictDetector(extractor=self.extractor,
                                          use_embedding=use_embedding,
                                          judge_config=judge_config)
        self.patcher = PatchEngine()
        self.use_embedding = use_embedding
        self._judge_config = judge_config
        
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
        topics: list[Topic] = []
        topic_names: set[str] = set()
        for claim in raw_topics:
            for kw in claim.keywords_found:
                if kw not in topic_names:
                    topic_names.add(kw)
                    topics.append(Topic(name=kw, confidence=claim.confidence))
        
        # v4.0: MULTI-TOPIC — ClaimExtractor'ın bulduğuna EK olarak
        # query'deki tüm eşleşen topic/alias'ları da ekle
        # (böylece "bug report: NPX1" → hem WF hem FACTUAL tetiklenir)
        query_lower = user_query.lower().strip()
        # Skip for empty or very short queries ("" in "any" is always True)
        if len(query_lower) >= 3:
            for rid, meta in self.store._rule_meta.items():
                matched = False
                # Topic kontrol: query topic içeriyor mu?
                if meta["topic"].lower() in query_lower:
                    tn = meta["topic"]
                    if tn not in topic_names:
                        topic_names.add(tn)
                        topics.append(Topic(name=tn, confidence=0.85))
                        matched = True
                # Alias kontrol: query alias içeriyor mu? veya alias query'i?
                for alias in meta.get("aliases", []):
                    alias_lower = alias.lower()
                    if (alias_lower in query_lower or 
                        (len(alias_lower) >= 4 and query_lower in alias_lower)):
                        tn = meta["topic"]
                        if tn not in topic_names:
                            topic_names.add(tn)
                            topics.append(Topic(name=tn, 
                                confidence=0.75 if alias_lower in query_lower else 0.65))
                            matched = True
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
        all_step_violations: list = []
        for rule in rules:
            conflicts = self.detector.detect(llm_output, rule, topics)
            all_conflicts.extend(conflicts)
            # v4.0: Collect step violations
            if hasattr(self.detector, 'last_step_violations'):
                all_step_violations.extend(self.detector.last_step_violations)
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
                modified=True,
                step_violations=all_step_violations,
            )
        else:
            result = RectificationResult(
                original=llm_output,
                corrected=llm_output,
                topics_found=topics,
                rules_activated=[r.id for r in rules],
                latency_us=timings,
                modified=False,
                step_violations=all_step_violations,
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
            "extractor": {
                "avg_latency_us": self.extractor.avg_latency_us,
            },
            "detector": {
                "avg_latency_us": self.detector.avg_latency_us,
            },
            "patcher": {
                "avg_latency_us": self.patcher.avg_latency_us,
            },
            "rectifier": {
                "avg_latency_us": self.patcher.avg_latency_us,
            },
        }
