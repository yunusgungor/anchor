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
    Rule, Topic, Conflict, Severity, Correction,
    RectificationResult, StepViolation,
)
from anchor.config import (
    KEYWORD_MIN_LENGTH,
    TOPIC_MAX_OUTPUT_RULES,
    TOPIC_OUTPUT_KEYWORD_DENSITY_THRESHOLD,
    TOPIC_DOMAIN_MAX_RULES,
    RULE_DOMAIN_MAP,
    WF_QUERY_DIRECT_MAX_WORKFLOW_RULES,
)
from anchor.store.scale_store import ScalableRuleStore
from anchor.detect import (
    ClaimExtractor, ConflictDetector
)
from anchor.rectify import PatchEngine


class AnchorEngine:
    """
    Anchor — LLM çıktıları için deterministik rectification engine.
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
        self._total_processed = 0
        self._total_modified = 0
    
    def build(self):
        self.store.build()
        for rule_id, meta in self.store._rule_meta.items():
            self.extractor.register_rule(
                topic=meta["topic"],
                aliases=meta.get("aliases", []),
                tags=meta.get("tags", []),
                content="",
            )

    def hot_reload(self):
        self.store.build()

    def _apply_output_rule_limits(self, topics: list[Topic], keyword_matches: dict[str, list[str]]) -> list[Topic]:
        if not topics:
            return topics

        scored: list[tuple[float, str, Topic]] = []
        for t in topics:
            rule_id = None
            for rid, meta in self.store._rule_meta.items():
                if meta.get("topic") == t.name:
                    rule_id = rid
                    break
            if not rule_id:
                scored.append((t.confidence, 'unknown', t))
                continue
            total_keywords = max(1, len(self.store._rule_meta.get(rule_id, {}).get('keywords', [])))
            matched = len(keyword_matches.get(rule_id, []))
            density = matched / total_keywords if total_keywords else 0.0
            domain = RULE_DOMAIN_MAP.get(rule_id, self.store._rule_meta.get(rule_id, {}).get('domain', 'unknown'))
            score = max(t.confidence, density)
            if matched == 0:
                score = t.confidence
            scored.append((score, domain, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        kept: list[Topic] = []
        domain_counts: dict[str, int] = {}
        for score, domain, topic in scored:
            rule_id = None
            for rid, meta in self.store._rule_meta.items():
                if meta.get("topic") == topic.name:
                    rule_id = rid
                    break
            matched = len(keyword_matches.get(rule_id, [])) if rule_id else 0
            total_keywords = max(1, len(self.store._rule_meta.get(rule_id, {}).get('keywords', []))) if rule_id else 1
            density = matched / total_keywords if total_keywords else 0.0
            if matched > 0 and density < TOPIC_OUTPUT_KEYWORD_DENSITY_THRESHOLD:
                continue
            if domain_counts.get(domain, 0) >= TOPIC_DOMAIN_MAX_RULES:
                continue
            kept.append(topic)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            if len(kept) >= TOPIC_MAX_OUTPUT_RULES:
                break
        return kept or topics[:TOPIC_MAX_OUTPUT_RULES]
    
    def process(self, user_query: str, llm_output: str) -> RectificationResult:
        timings = {}
        
        t0 = time.perf_counter()
        raw_topics = self.extractor.extract(user_query, llm_output)
        t1 = time.perf_counter()
        timings['topic_extraction'] = (t1 - t0) * 1_000_000
        
        topics: list[Topic] = []
        topic_names: set[str] = set()
        for claim in raw_topics:
            for kw in claim.keywords_found:
                if kw not in topic_names:
                    topic_names.add(kw)
                    topics.append(Topic(name=kw, confidence=claim.confidence))
        
        query_lower = user_query.lower().strip()
        if len(query_lower) >= 3:
            for rid, meta in self.store._rule_meta.items():
                topic_lower = meta["topic"].lower()
                if len(topic_lower) >= 3 and topic_lower in query_lower:
                    tn = meta["topic"]
                    if tn not in topic_names:
                        topic_names.add(tn)
                        topics.append(Topic(name=tn, confidence=0.85))
                elif query_lower in topic_lower and len(query_lower) >= 3:
                    tn = meta["topic"]
                    if tn not in topic_names:
                        topic_names.add(tn)
                        topics.append(Topic(name=tn, confidence=0.80))
                for alias in meta.get("aliases", []):
                    alias_lower = alias.lower()
                    if not alias_lower or all(c in '-_=|*#/' for c in alias_lower.strip()):
                        continue
                    if (alias_lower in query_lower or (len(alias_lower) >= 4 and query_lower in alias_lower)):
                        tn = meta["topic"]
                        if tn not in topic_names:
                            topic_names.add(tn)
                            topics.append(Topic(name=tn, confidence=0.75 if alias_lower in query_lower else 0.65))
                            break
        
        topic_names = [t.name for t in topics]
        
        if not topics and llm_output and len(llm_output) >= 10:
            output_lower = llm_output.lower()
            for rid, meta in self.store._rule_meta.items():
                tn = meta["topic"]
                if tn in topic_names:
                    continue
                topic_lower = tn.lower()
                if len(topic_lower) >= 4 and topic_lower in output_lower:
                    topic_names.append(tn)
                    topics.append(Topic(name=tn, confidence=0.55))
                    continue
                for alias in meta.get("aliases", []):
                    alias_lower = alias.lower()
                    if not alias_lower or all(c in '-_=|*#/' for c in alias_lower.strip()):
                        continue
                    if len(alias_lower) >= 4 and alias_lower in output_lower:
                        if tn not in topic_names:
                            topic_names.append(tn)
                            topics.append(Topic(name=tn, confidence=0.60))
                            break
        
        kw_index = getattr(self.store, '_distinctive_keyword_index', {})
        keyword_matches: dict[str, list[str]] = {}
        if kw_index and llm_output and len(llm_output) >= 10:
            query_matched_ids = set()
            if topics:
                for rid, meta in self.store._rule_meta.items():
                    if meta["topic"] in topic_names:
                        query_matched_ids.add(rid)
            
            output_lower = llm_output.lower()
            for keyword, rule_ids in kw_index.items():
                if keyword in output_lower:
                    is_meaningful = (
                        len(keyword) >= KEYWORD_MIN_LENGTH or
                        '/' in keyword or '-' in keyword
                    )
                    if not is_meaningful:
                        continue
                    for rid in rule_ids:
                        meta = self.store._rule_meta.get(rid)
                        if not meta:
                            continue
                        if query_matched_ids and rid not in query_matched_ids:
                            if not ('/' in keyword or '-' in keyword):
                                continue
                        if meta["topic"] not in topic_names:
                            topic_names.append(meta["topic"])
                            topics.append(Topic(name=meta["topic"], confidence=0.65))
                        if rid not in keyword_matches:
                            keyword_matches[rid] = []
                        if keyword not in keyword_matches[rid]:
                            keyword_matches[rid].append(keyword)

        if not user_query.strip() and topics:
            topics = self._apply_output_rule_limits(topics, keyword_matches)
            topic_names = [t.name for t in topics]
        
        # Workflow rule filter: factual sorular workflow rule'larını tetiklememeli
        # Eğer query'de işlem/süreç kelimesi yoksa, workflow rule'larını filtrele
        query_lower_wf = user_query.lower().strip()
        workflow_keywords = ['nasıl', 'süreç', 'adım', 'workflow', 'yapılır', 'işlem',
                            'how to', 'process', 'step', 'procedure', 'yöntem',
                            'akış', 'pipeline', 'work', 'should i', 'best practice',
                            'review', 'incident', 'deploy', 'release', 'story',
                            'bug', 'fix', 'test', 'tdd', 'retro', 'refactor']
        is_workflow_query = any(kw in query_lower_wf for kw in workflow_keywords)
        # Eğer tespit edilen topic'ler workflow rule'larına aitse de workflow query say
        if not is_workflow_query and topics:
            for t in topics:
                tn = t.name.lower()
                if any(wk in tn for wk in ['process', 'workflow', 'cycle', 'pipeline']):
                    is_workflow_query = True
                    break
        
        rules = self.store.query(topic_names, llm_output)
        if user_query.strip() and rules:
            workflow_rules = [r for r in rules if getattr(r, 'steps', None)]
            non_workflow_rules = [r for r in rules if not getattr(r, 'steps', None)]
            # Workflow rule'ları sadece süreç sorusu sorulduğunda aktif olsun
            # "Clean Architecture Dependency Rule nedir?" → ADR workflow tetiklenmez
            if not is_workflow_query:
                workflow_rules = []
            if len(workflow_rules) > WF_QUERY_DIRECT_MAX_WORKFLOW_RULES:
                workflow_rules = workflow_rules[:WF_QUERY_DIRECT_MAX_WORKFLOW_RULES]
            rules = workflow_rules + non_workflow_rules
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
        
        all_conflicts: list[Conflict] = []
        all_step_violations: list = []
        for rule in rules:
            extra = keyword_matches.get(rule.id, None)
            conflicts = self.detector.detect(llm_output, rule, topics, additional_terms=extra)
            all_conflicts.extend(conflicts)
            if hasattr(self.detector, 'last_step_violations'):
                all_step_violations.extend(self.detector.last_step_violations)
        
        # Prioritize: Phase 0 known-wrong conflicts (confidence=0.5) önce gelsin
        # ki dedup'ta onlar kazansın. Diğer conflicts sıralamayı bozmaz.
        all_conflicts.sort(key=lambda c: (0 if c.confidence == 0.5 else 1, c.severity.value))
        
        # Cross-rule FP filter: herhangi bir rule'un confusion table'ında doğru
        # olarak geçen bir claim, başka bir rule tarafından general matching ile
        # FP olarak işaretlenmemeli.
        from anchor.parser.extractor import extract_known_wrong_claims
        all_correct_facts: list[str] = []
        for rule in rules:
            known_wrong = extract_known_wrong_claims(rule.content)
            for _, correct in known_wrong:
                if correct not in all_correct_facts:
                    all_correct_facts.append(correct)
        
        if all_correct_facts:
            from anchor.detect import FactMatcher
            fp_matcher = FactMatcher(use_embedding=False)
            filtered_conflicts = []
            for c in all_conflicts:
                # Phase 0 conflicts hep kalır
                if c.confidence == 0.5:
                    filtered_conflicts.append(c)
                    continue
                # General conflicts: claim doğru fact'lerden birine benziyorsa FP
                is_correct = False
                for cf in all_correct_facts:
                    fm = fp_matcher.match(c.llm_claim, cf)
                    if fm.combined_distance < 0.55:
                        is_correct = True
                        break
                if not is_correct:
                    filtered_conflicts.append(c)
                else:
                    pass  # FP — atla
            all_conflicts = filtered_conflicts
        t3 = time.perf_counter()
        timings['conflict_detection'] = (t3 - t2) * 1_000_000
        
        if all_conflicts:
            corrected_text, patches = self.patcher.apply(llm_output, all_conflicts)
            # Per-rule dedup: aynı claim farklı rule'lar tarafından farklı KB fact ile
            # düzeltilebilir (örn. known-wrong vs general fact matching).
            # Her rule'un kendi dedup set'i var.
            seen_claims_by_rule: dict[str, set[str]] = {}
            corrections = []
            for patch in patches:
                conflict = next((c for c in all_conflicts if c.llm_claim == patch.original), None)
                if conflict:
                    rule_id = conflict.rule_id
                    if rule_id not in seen_claims_by_rule:
                        seen_claims_by_rule[rule_id] = set()
                    if conflict.llm_claim in seen_claims_by_rule[rule_id]:
                        continue
                    seen_claims_by_rule[rule_id].add(conflict.llm_claim)
                    corrections.append(Correction(
                        conflict=conflict,
                        original_text=patch.original,
                        corrected_text=patch.replacement,
                        edit_distance=patch.edit_distance,
                    ))
            modified = len(corrections) > 0
        else:
            corrected_text = llm_output
            corrections = []
            modified = False
        t4 = time.perf_counter()
        timings['rectification'] = (t4 - t3) * 1_000_000
        timings['total'] = (t4 - t0) * 1_000_000
        
        result = RectificationResult(
            original=llm_output,
            corrected=corrected_text,
            corrections=corrections,
            topics_found=topics,
            rules_activated=[r.id for r in rules],
            latency_us=timings,
            modified=modified,
            step_violations=all_step_violations,
        )
        
        self._total_processed += 1
        if modified:
            self._total_modified += 1
        
        return result

    @property
    def stats(self) -> dict:
        """Runtime istatistikleri."""
        total = self._total_processed
        modified = self._total_modified
        store_stats = self.store.stats() if hasattr(self.store, 'stats') else {}
        return {
            'engine': {
                'total_processed': total,
                'total_modified': modified,
                'modification_rate': (modified / total) if total else 0.0,
            },
            'store': store_stats,
            'detector_avg_latency_us': getattr(self.detector, 'avg_latency_us', 0),
            'patcher_avg_latency_us': getattr(self.patcher, 'avg_latency_us', 0),
        }
