"""
Anchor Conflict Detection — Sentence-level claim extraction + edit distance.

Bileşenler:
  ClaimExtractor: LLM output'undan konuyla ilgili cümleleri çıkar
  FactMatcher: KB fact'leriyle claim'leri karşılaştır
  SeverityEngine: Distance → severity mapping
  ConflictDetector: Üst seviye detector (tüm bileşenleri koordine eder)
"""

import logging
import re
import time
from difflib import SequenceMatcher
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, TYPE_CHECKING

from anchor import Conflict, Severity

import numpy as np

if TYPE_CHECKING:
    from anchor.judge.llm_judge import JudgeConfig

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    claim: str
    fact: str
    edit_distance: float      # 0-1 normalize edilmiş
    semantic_distance: float  # 0-1 (Jaccard veya embedding)
    negative_distance: float  # 0-1
    combined_distance: float  # Ağırlıklı toplam
    is_conflict: bool         # Çelişki var mı?
    embedding_distance: float = -1.0  # -1 if not computed


@dataclass
class Claim:
    """LLM'in bir konu hakkında söylediği bir cümle."""
    text: str
    position: int
    keywords_found: list[str]
    confidence: float = 1.0


class ClaimExtractor:
    """
    LLM çıktısındaki iddiaları (claims) konu bazında çıkarır.
    
    v4.2: Synonym-aware matching eklenmiştir:
      - Domain synonym map: alias → yaygın varyasyonlar
      - Prefix-stem matching: "retros" → "retrospectives"
      - Word overlap: multi-word alias'ların tekil kelimeleri
    """
    
    # Domain-specific synonym map (alias → common variations)
    DOMAIN_SYNONYMS: list[tuple[str, list[str]]] = [
        ("pipeline", ["ci/cd", "ci", "cd", "build pipeline"]),
        ("retrospective", ["retro", "retros", "retrospective"]),
        ("retrospectives", ["retro", "retros", "postmortem", "post-mortem"]),
        ("architecture", ["arch", "design", "system design", "architectural"]),
        ("release", ["deploy", "go-live", "ship", "release process"]),
        ("refinement", ["grooming", "backlog grooming", "backlog refinement"]),
        ("backend", ["server", "service layer", "business logic"]),
        ("frontend", ["ui", "client", "presentation"]),
        ("singleton", ["singleton pattern"]),
        ("tdd", ["test-driven", "test driven", "tdd cycle"]),
        ("code review", ["pr review", "peer review", "code review process"]),
        ("branching", ["git branch", "branch strategy", "branching model"]),
    ]
    
    def __init__(self):
        self._total_calls = 0
        self._total_latency_us = 0
        self._rules = []

    def register_rule(self, topic: str, aliases: list[str], tags: list[str], content: str):
        self._rules.append({
            "topic": topic,
            "aliases": aliases,
            "tags": tags,
            "content": content,
        })

    def extract(self, *args, **kwargs) -> list[Claim]:
        """
        LLM output'undan topic'le ilgili cümleleri çıkar.
        
        Eski API: extract(query, content)
        Yeni API: extract(llm_output, topic, aliases)
        """
        # Eski signature detection: extract(query, content)
        if len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], str):
            # Eski API: extract(query, content)
            query, content = args
            # Query'den topic ve alias bul
            return self._extract_legacy(content, query)
        
        # Yeni signature: extract(llm_output, topic, aliases)
        llm_output = args[0] if len(args) > 0 else kwargs.get('llm_output')
        topic = args[1] if len(args) > 1 else kwargs.get('topic')
        aliases = args[2] if len(args) > 2 else kwargs.get('aliases', [])
        
        if llm_output is None or topic is None:
            raise TypeError("extract() requires (llm_output, topic, aliases) or (query, content)")
        
        return self._extract_new(llm_output, topic, aliases)
    
    def _extract_legacy(self, content: str, query: str) -> list[Claim]:
        """Eski API desteği — query'den topic bul, content'ten claim çıkar."""
        # Query'den en uygun topic'i bul
        best_topic = None
        best_aliases = []
        
        for rule in self._rules:
            topic_lower = rule["topic"].lower()
            aliases_lower = [a.lower() for a in rule["aliases"]]
            
            if topic_lower in query.lower():
                best_topic = rule["topic"]
                best_aliases = rule["aliases"]
                break
            for alias in aliases_lower:
                if alias in query.lower():
                    best_topic = rule["topic"]
                    best_aliases = rule["aliases"]
                    break
        
        if not best_topic:
            return []
        
        return self._extract_new(content, best_topic, best_aliases)
    
    def _extract_new(self, llm_output: str, topic: str, aliases: list[str]) -> list[Claim]:
        """Yeni API — doğrudan topic ve alias ile claim çıkar.
        
        v4.2: Synonym-aware matching:
          - Domain synonym map: alias → yaygın varyasyonlar
          - Prefix-stem matching: "retros" ≈ "retrospectives"
          - Word overlap: multi-word alias'ların tekil kelimeleri
        """
        t0 = time.perf_counter()
        self._total_calls += 1

        # 1. Base terms: topic + aliases
        all_terms = [topic.lower()] + [a.lower() for a in aliases]
        all_terms.sort(key=len, reverse=True)

        # 2. Auto-generate word-based terms from topic
        topic_words = [w for w in topic.lower().split() if len(w) >= 4]
        for w in topic_words:
            if w not in all_terms:
                all_terms.append(w)

        # 3. Synonym expansion from domain map
        for alias, synonyms in self.DOMAIN_SYNONYMS:
            if any(alias in t for t in all_terms):
                for syn in synonyms:
                    if syn not in all_terms:
                        all_terms.append(syn)

        # 4. Build prefix-stem index for fuzzy matching
        #    e.g. "retrospectives" → stem "retro" matches "retros"
        prefix_map: dict[str, list[str]] = {}
        for term in all_terms:
            if len(term) >= 5:
                for stem_len in (4, 5, 6):
                    if len(term) >= stem_len:
                        stem = term[:stem_len]
                        prefix_map.setdefault(stem, []).append(term)

        sentences = self._segment_sentences(llm_output)
        claims = []

        for sent, pos in sentences:
            sent_lower = sent.lower()
            found_terms = []
            
            # 4a. Exact substring matching
            for term in all_terms:
                if term in sent_lower:
                    found_terms.append(term)
            
            # 4b. Prefix-stem fuzzy matching (if exact didn't find enough)
            if not found_terms:
                sent_words = set(sent_lower.split())
                for word in sent_words:
                    if len(word) >= 4:
                        for stem_len in (4, 5):
                            stem = word[:stem_len]
                            if stem in prefix_map:
                                for matched_term in prefix_map[stem]:
                                    if matched_term not in found_terms:
                                        found_terms.append(matched_term)

            if found_terms:
                avg_term_len = sum(len(t.split()) for t in found_terms) / len(found_terms)
                confidence = min(1.0, 0.5 + avg_term_len * 0.15)
                claims.append(Claim(
                    text=sent, position=pos,
                    keywords_found=found_terms, confidence=confidence,
                ))

        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000
        return claims

    def _segment_sentences(self, text: str) -> list[tuple[str, int]]:
        """
        Metni cümlelere ayır — abbreviation-aware.
        
        Kısaltmaları (Dr., Mr., vs., vb., Yrd., Prof., No., St., vb.) 
        cümle sonu sanmaz.
        """
        # Kısaltma listesi (cümle sonu sanılmaması gereken)
        abbr_pattern = re.compile(
            r'\b(?:'
            r'Dr|Mr|Mrs|Ms|Prof|St|Ave|Blvd|Rd|Sq|No|vs|vb|vd|yn'
            r'|Yrd|Doç|Arş|Gör|Cad|Sok|Mah|Apt|Tel|Fax'
            r'|AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA'
            r'|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK'
            r'|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY'
            r')\.'
        )
        
        # Kısaltmaları placeholder ile değiştir
        placeholders = {}
        def _replace(match):
            ph = f"\x00ABBR{len(placeholders)}\x00"
            placeholders[ph] = match.group(0)
            return ph
        
        text_clean = abbr_pattern.sub(_replace, text)
        
        # Şimdi güvenli cümle bölme
        sent_pattern = re.compile(r'[^.!?\n]+[.!?\n]+')
        sentences = []
        for m in sent_pattern.finditer(text_clean):
            sent = m.group().strip()
            # Placeholder'ları geri çevir
            for ph, original in placeholders.items():
                sent = sent.replace(ph, original)
            if len(sent) > 10:
                sentences.append((sent, m.start()))
        
        # Regex hiç eşleşmediyse tüm metni tek cümle olarak al
        if not sentences and text.strip():
            sentences.append((text.strip(), 0))
        
        return sentences

    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls


class FactMatcher:
    """KB'deki bir fact ile LLM'in claim'i arasındaki mesafeyi ölçer.

    α·d_edit + β·d_sem + γ·d_neg
      d_edit: SequenceMatcher (Levenshtein)
      d_sem : Jaccard (fallback) veya embedding cosine similarity
      d_neg : Olumsuzluk ifadesi tespiti

    Embedding modu:
        matcher = FactMatcher(use_embedding=True)
        load_model()  # bir kere
    """

    def __init__(self, alpha: float = 0.4, beta: float = 0.4, gamma: float = 0.2,
                 use_embedding: bool = False):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.use_embedding = use_embedding
        self._total_calls = 0
        self._total_latency_us = 0
        
        # Embedding cache (build-time pre-computed + runtime claim cache)
        self._fact_texts: list[str] = []
        self._fact_embeddings: Optional[np.ndarray] = None
        self._claim_cache: dict[str, np.ndarray] = {}
        self._claim_cache_max = 10

    def cache_facts(self, facts: Optional[list[str]] = None,
                    precomputed: Optional[np.ndarray] = None,
                    fact_texts: Optional[list[str]] = None):
        """Cache fact embeddings (build-time pre-computed or runtime batch).
        
        Two modes:
          1. Build-time (fast): pass precomputed (float16) + fact_texts
          2. Runtime (fallback): pass facts list to batch-encode
        
        Args:
            facts: Runtime mode — fact strings to batch-encode.
            precomputed: Build-time mode — pre-computed numpy array (float16 OK).
            fact_texts: Build-time mode — corresponding fact texts.
        """
        if not self.use_embedding:
            return
        
        if precomputed is not None and fact_texts is not None:
            self._fact_texts = list(fact_texts)
            if precomputed.dtype == np.float16:
                precomputed = precomputed.astype(np.float32)
            self._fact_embeddings = precomputed
            logger.log(5, "Loaded %d pre-computed fact embeddings", len(fact_texts))
            return
        
        if facts:
            from anchor.judge.embedding import encode_batch
            vecs = encode_batch(facts)
            if vecs is not None:
                self._fact_texts = list(facts)
                self._fact_embeddings = vecs
                logger.log(5, "Cached %d fact embeddings (%s)", len(facts), vecs.shape)

    def _get_claim_embedding(self, claim: str) -> Optional[np.ndarray]:
        """Get (possibly cached) claim embedding."""
        if claim in self._claim_cache:
            return self._claim_cache[claim]
        from anchor.judge.embedding import encode
        vec = encode(claim)
        if vec is not None:
            if len(self._claim_cache) >= self._claim_cache_max:
                self._claim_cache.pop(next(iter(self._claim_cache)))
            self._claim_cache[claim] = vec
        return vec

    def _batch_embedding_distance(self, claim: str, fact: str) -> Optional[float]:
        """Compute embedding distance using cached fact embeddings (~1µs)."""
        if self._fact_embeddings is None or not self._fact_texts:
            return None
        try:
            idx = self._fact_texts.index(fact)
        except ValueError:
            return None
        claim_vec = self._get_claim_embedding(claim)
        if claim_vec is None:
            return None
        sim = float(np.dot(self._fact_embeddings[idx], claim_vec))
        return 1.0 - max(-1.0, min(1.0, sim))

    def clear_cache(self):
        self._fact_texts = []
        self._fact_embeddings = None
        self._claim_cache.clear()

    def match(self, claim: str, fact: str) -> MatchResult:
        t0 = time.perf_counter()
        self._total_calls += 1

        d_edit = self._compute_edit_distance(claim, fact)
        d_sem = self._compute_semantic_distance(claim, fact)
        d_neg = self._compute_negative_distance(claim)
        
        # Embedding distance (if available)
        d_emb = -1.0
        if self.use_embedding:
            # Prefer batch cache (~1µs) over individual encoding (>100ms)
            d = self._batch_embedding_distance(claim, fact)
            if d is None:
                # Fallback: cache claim encoding for subsequent calls
                _claim_vec = self._get_claim_embedding(claim)
                try:
                    from anchor.judge.embedding import semantic_distance
                    d = semantic_distance(claim, fact)
                except Exception:
                    d = None
            elif d == 2.0:
                # 2.0 means orthogonal/opposite vectors (max distance)
                # Still valid, just not similar
                pass
            
            if d is not None:
                d_emb = d
        
        # Combined distance: embedding-aware if available
        if d_emb >= 0:
            if d_emb < 0.5:
                # Embedding says semantically related → paraphrase olabilir
                d_combined = self.alpha * d_edit + self.beta * d_emb + self.gamma * d_neg
                is_conflict = d_combined > 0.5
                d_sem_effective = d_emb
            elif d_emb > 0.7:
                # Embedding says VERY different → farklı alt-konular
                # Sadece güçlü çelişkiler geçmeli
                d_combined = self.alpha * d_edit + self.beta * d_sem + self.gamma * d_neg
                is_conflict = d_combined > 0.7
                d_sem_effective = d_sem
            else:
                # Embedding neutral → standart formül
                d_combined = self.alpha * d_edit + self.beta * d_sem + self.gamma * d_neg
                is_conflict = d_combined > 0.4
                d_sem_effective = d_sem
        else:
            # No embedding: standard formula
            d_combined = self.alpha * d_edit + self.beta * d_sem + self.gamma * d_neg
            is_conflict = d_combined > 0.4
            d_sem_effective = d_sem

        result = MatchResult(
            claim=claim, fact=fact,
            edit_distance=d_edit, semantic_distance=d_sem_effective,
            negative_distance=d_neg, combined_distance=d_combined,
            is_conflict=is_conflict,
            embedding_distance=d_emb,
        )

        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000
        return result

    def _compute_edit_distance(self, claim: str, fact: str) -> float:
        sm = SequenceMatcher(None, claim.lower(), fact.lower())
        return 1.0 - sm.ratio()

    def _compute_semantic_distance(self, claim: str, fact: str) -> float:
        """Semantic distance: Jaccard (or embedding when use_embedding=False).
        
        When use_embedding=True, embedding is computed separately in 
        the 'Embedding distance' block of match() — avoid double compute.
        """
        if self.use_embedding:
            # Embedding computed in match() embedding block — use Jaccard here
            return self._compute_jaccard_distance(claim, fact)
        # Without embedding: try semantic_distance, fallback to Jaccard
        try:
            from anchor.judge.embedding import semantic_distance
            d = semantic_distance(claim, fact)
            if d is not None:
                return d
        except Exception:
            pass
        return self._compute_jaccard_distance(claim, fact)

    def _compute_jaccard_distance(self, claim: str, fact: str) -> float:
        """Jaccard distance (1 - intersection/union)."""
        claim_words = set(self._tokenize(claim))
        fact_words = set(self._tokenize(fact))
        if not claim_words or not fact_words:
            return 1.0
        intersection = len(claim_words & fact_words)
        union = len(claim_words | fact_words)
        if union == 0:
            return 1.0
        return 1.0 - (intersection / union)

    def _compute_negative_distance(self, claim: str) -> float:
        negative_markers = [
            r'\bdeğil\w*\b', r'\bnot\b', r'\bno\b',
            r'\byanlış\b', r'\bwrong\b', r'\bfalse\b',
            r'\bhatalı\b', r'\binvalid\b', r'\bincorrect\b',
            r'\bnever\b', r'\bnone\b',
        ]
        claim_lower = claim.lower()
        hit_count = sum(1 for p in negative_markers if re.search(p, claim_lower))
        return min(1.0, hit_count / 3.0)

    def _tokenize(self, text: str) -> list[str]:
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


class SeverityEngine:
    """Bir MatchResult'ın distance değerlerini Severity'ye dönüştürür."""

    INFO_THRESHOLD = 0.2
    WARNING_THRESHOLD = 0.5
    ERROR_THRESHOLD = 0.8

    def compute(self, match: MatchResult) -> Severity:
        d = match.combined_distance

        if match.negative_distance > 0.3:
            if d >= self.ERROR_THRESHOLD:
                return Severity.CRITICAL
            base_sev = self._from_distance(d)
            if base_sev.value < Severity.WARNING.value:
                return Severity.WARNING
            return base_sev

        if match.edit_distance > 0.7 and match.semantic_distance > 0.7:
            return Severity.CRITICAL

        return self._from_distance(d)

    def _from_distance(self, d: float) -> Severity:
        if d < self.INFO_THRESHOLD:
            return Severity.INFO
        elif d < self.WARNING_THRESHOLD:
            return Severity.WARNING
        elif d < self.ERROR_THRESHOLD:
            return Severity.ERROR
        else:
            return Severity.CRITICAL

    def confidence(self, match: MatchResult) -> float:
        return match.combined_distance


class ConflictDetector:
    """
    Üst seviye detector — tüm bileşenleri koordine eder.
    ClaimExtractor → FactMatcher → SeverityEngine
    
    Extractor dışarıdan enjekte edilebilir (AnchorEngine ile paylaşmak için).
    """

    def __init__(self, extractor: Optional["ClaimExtractor"] = None,
                 use_embedding: bool = False,
                 judge_config: Optional["JudgeConfig"] = None):
        self.extractor = extractor or ClaimExtractor()
        self.matcher = FactMatcher(use_embedding=use_embedding)
        self._jaccard_matcher = FactMatcher(use_embedding=False)
        self.severity = SeverityEngine()
        self.use_embedding = use_embedding
        self._total_calls = 0
        self._total_latency_us = 0
        
        # LLM-as-Judge
        self._judge = None
        if judge_config and judge_config.use_llm:
            from anchor.judge.llm_judge import LLMJudge
            self._judge = LLMJudge(judge_config)
            logger.info("LLM-as-Judge enabled: %s/%s",
                        judge_config.llm_provider, judge_config.llm_model)
        
        # v4.0: Workflow Governor
        self.workflow_validator = None  # lazy import WorkflowIntegrator
        self.last_step_violations: list = []  # v4.0: last detection's step violations

    def detect(self, llm_output: str, rule, topics: list,
               additional_terms: list[str] | None = None) -> list[Conflict]:
        """
        LLM output'unda rule'la ilgili çelişkileri tespit et.
        
        İki aşamalı strateji:
          1. Confusion table'daki bilinen yanlış claim'lerle karşılaştır
             (doğrudan eşleşme → conflict)
          2. Diğer fact'lerle karşılaştır:
             a. Relevance filter: farklı konu → false positive önleme
             b. Dynamic threshold: ortak keyword varsa (paraphrase olabilir)
                conflict eşiği yükseltilir
             c. LLM-as-Judge: borderline case'lerde (opsiyonel)
        
        NOT: enriched_facts (build-time paraphrase'lar) otomatik kullanılır.
        rule objesi anchor.parser'dan gelen standart Rule ise,
        ScaleStore'daki enriched_facts'ler ConflictDetector'a enjekte edilmelidir.

        Args:
            llm_output: LLM'in ürettiği ham metin
            rule: KB'deki Rule objesi
            topics: Bulunan topic'ler
            additional_terms: v4.3 — distinctive keyword matching'den
                             gelen ek terimler (örn. ["singleton"])

        Returns:
            Çelişki listesi
        """
        t0 = time.perf_counter()
        self._total_calls += 1

        conflicts = []

        # 1. Claim extraction (additional_terms ile genişlet)
        combined_aliases = list(rule.aliases)
        if additional_terms:
            for term in additional_terms:
                if term not in combined_aliases:
                    combined_aliases.append(term)
        claims = self.extractor.extract(llm_output, rule.topic, combined_aliases)

        if not claims:
            # v4.0: Still run workflow validation even without claims
            wf_conflicts, step_violations = self._run_workflow_validation(llm_output, rule)
            self.last_step_violations = step_violations
            conflicts.extend(wf_conflicts)
            t1 = time.perf_counter()
            self._total_latency_us += (t1 - t0) * 1_000_000
            return conflicts

        # 2. Rule'dan fact'leri ve bilinen yanlış claim'leri parse et
        facts = self._extract_facts(rule.content)
        known_wrong = self._extract_known_wrong_claims(rule.content)
        
        # 2b. Enriched facts varsa ekle (build-time paraphrase'lar)
        enriched = getattr(rule, "enriched_facts", None) or []
        if enriched:
            # enriched_facts orijinalleri de içerir, duplicate'leri önle
            original_set = set(f.lower() for f in facts)
            for ef in enriched:
                if ef.lower() not in original_set:
                    facts.append(ef)
                    original_set.add(ef.lower())
        
        # 2c. Pre-computed fact embeddings (build-time, ~1µs)
        #     NOT: Pre-computed fact_texts kullanılıyorsa, onların
        #     embedding'leri de NPZ'de mevcut → batch cache her zaman HIT.
        if self.use_embedding:
            precomputed = getattr(rule, "fact_embeddings", None)
            fact_texts = getattr(rule, "fact_texts", None)
            if precomputed is not None and fact_texts is not None:
                self.matcher.cache_facts(precomputed=precomputed, fact_texts=fact_texts)
                # Pre-computed fact'ler variablesa, runtime fact list'ini de
                # pre-computed list'le değiştir ki cache her zaman HIT olsun.
                # Sadece enriched facts eklenir (duplicate önlenir).
                facts = list(fact_texts)
                original_set = set(f.lower() for f in facts)
                for ef in enriched:
                    if ef.lower() not in original_set:
                        facts.append(ef)
                        original_set.add(ef.lower())
                known_wrong = self._extract_known_wrong_claims(rule.content)

        # 3. Her claim'i kontrol et
        for claim in claims:
            # Entity name set'ini hazırla (entity-aware threshold için)
            entity_names: set[str] = set()
            entity_names.update(self._get_significant_tokens(rule.topic))
            for alias in rule.aliases:
                entity_names.update(self._get_significant_tokens(alias))
            
            # 3a. ÖNCE: Bilinen yanlış claim'lerle karşılaştır
            #     (confusion table: "LLM'in Genelde Dediği" kolonu)
            for wrong, correct in known_wrong:
                # ÖNCE: Claim, bilinen yanlış ifadeyi içeriyor mu?
                # (substring kontrolü — distance eşiği geçmese bile)
                claim_lower = claim.text.lower()
                
                is_wrong_pattern = False
                wrong_distance = 1.0
                
                # Tüm alternatifleri kontrol et (" / " ile ayrılmış olabilir)
                wrong_alternatives = [w.strip() for w in wrong.split("/") if w.strip()]
                for alt in wrong_alternatives:
                    alt_lower = alt.lower().strip()
                    # Exact match
                    if alt_lower in claim_lower and len(alt_lower) >= 3:
                        is_wrong_pattern = True
                        wrong_distance = 0.5
                        break
                    # Turkish suffix-tolerant match: "network katmanı" ≈ "network katmanında"
                    if len(alt_lower) >= 5 and alt_lower.rstrip("ıiueöoa") in claim_lower:
                        is_wrong_pattern = True
                        wrong_distance = 0.55
                        break
                
                # 2. Distance-based benzerlik (substring eşleşmezse)
                if not is_wrong_pattern:
                    match_w = self.matcher.match(claim.text, wrong)
                    wrong_distance = match_w.combined_distance
                    if wrong_distance < 0.6:
                        is_wrong_pattern = True
                
                if is_wrong_pattern:
                    # EK KONTROL: Claim aynı zamanda doğru fact'lerden birine
                    # de benziyorsa, LLM aslında doğruyu söylüyordur
                    # (örn: "SkyWater ve Google" → Google yanlış ama SkyWater doğru)
                    also_correct = False
                    if known_wrong and facts:
                        for fact in facts:
                            fm = self._jaccard_matcher.match(claim.text, fact)
                            if fm.combined_distance < 0.5:
                                also_correct = True
                                break
                    
                    if not also_correct:
                        conflicts.append(Conflict(
                            rule_id=rule.id,
                            topic=rule.topic,
                            llm_claim=claim.text,
                            kb_fact=correct,  # DOĞRU bilgiyi kullan
                            severity=Severity.CRITICAL,
                            confidence=wrong_distance,
                        ))
            
            # 3b. SONRA: Diğer fact'lerle karşılaştır 
            #     (relevance filter + dynamic threshold ile)
            for fact in facts:
                # Relevance filter: farklı konu → false positive
                if not self._are_relevant(claim.text, fact, rule.topic, rule.aliases):
                    continue
                
                match = self.matcher.match(claim.text, fact)
                if match.is_conflict:
                    # Dynamic threshold: ortak keyword varsa, paraphrase
                    # olabilir → daha yüksek eşik gerekli
                    claim_tokens = self._get_significant_tokens(claim.text)
                    fact_tokens = self._get_significant_tokens(fact)
                    shared_count = len(claim_tokens & fact_tokens)
                    
                    # Paylaşılan keyword sayısı arttıkça eşik yükselir
                    # Bu, aynı konuda paraphrase olan (farklı ifade, aynı anlam)
                    # claim-fact çiftlerinin false positive üretmesini engeller
                    #
                    # 0 shared → 0.40 (varsayılan)
                    # 1 shared → 0.65 (paraphrase ihtimali)
                    # 2 shared → 0.80 (güçlü bağlantı)
                    # 3 shared → 0.85 (çok güçlü)
                    # 4+ shared→ 0.90 (neredeyse aynı konu)
                    if shared_count == 1:
                        # Entity-aware: sadece entity adı paylaşılıyorsa
                        # (örn: "NPX1, TSMC'de" vs "NPX1, SKY130'da")
                        # daha düşük eşik kullan — farklı iddiaları yakala
                        shared = claim_tokens & fact_tokens
                        only_entity = bool(shared) and shared.issubset(entity_names) if entity_names else False
                        if only_entity:
                            effective_threshold = 0.48  # entity-only → çelişki olabilir
                        else:
                            effective_threshold = 0.65  # content overlap → paraphrase
                    elif shared_count == 2:
                        effective_threshold = 0.80
                    elif shared_count >= 3:
                        effective_threshold = 0.85
                    else:
                        effective_threshold = 0.40
                    
                    # Check if combined_distance exceeds the effective threshold
                    # bu bir paraphrase (farklı ifade, aynı anlam)
                    if match.combined_distance < effective_threshold:
                        continue
                    
                    # LLM-as-Judge: borderline case'lerde son karar
                    if self._judge is not None and match.embedding_distance >= 0:
                        d_emb = match.embedding_distance
                        if d_emb < 0.5:
                            # Embedding benzer dedi → paraphrase
                            continue
                        elif d_emb > 0.7:
                            # Embedding çok farklı dedi → conflict zaten
                            pass
                        else:
                            # Borderline (0.5 <= d_emb <= 0.7): LLM'e danış
                            verdict = self._judge.judge(claim.text, fact,
                                                         embedding_distance=d_emb)
                            if not verdict.is_conflict:
                                # LLM çelişki yok dedi → atla
                                continue
                    
                    sev = self.severity.compute(match)
                    conflicts.append(Conflict(
                        rule_id=rule.id,
                        topic=rule.topic,
                        llm_claim=claim.text,
                        kb_fact=fact,
                        severity=sev,
                        confidence=match.combined_distance,
                    ))

        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000

        # v4.0: Workflow validation (runs even without claims for workflow rules)
        wf_conflicts, step_violations = self._run_workflow_validation(llm_output, rule)
        conflicts.extend(wf_conflicts)
        self.last_step_violations = step_violations

        return conflicts

    def _run_workflow_validation(self, llm_output: str, rule) -> tuple[list, list]:
        """Run workflow validation if rule has steps.
        
        Returns (conflicts, step_violations) tuple.
        Used both in early-return (no claims) and normal flow.
        """
        if not hasattr(rule, 'steps') or not rule.steps:
            return [], []
        try:
            if self.workflow_validator is None:
                from anchor.compliance.workflow_validator import WorkflowIntegrator
                self.workflow_validator = WorkflowIntegrator()
            return self.workflow_validator.validate(llm_output, rule)
        except Exception as e:
            logger.warning("Workflow validation failed: %s", e)
            return [], []

    def _extract_facts(self, content: str) -> list[str]:
        """Rule içeriğinden fact'leri çıkar — format-agnostik.
        
        Desteklenen pattern'ler (Anchor native):
          1. Liste öğeleri: ``- fact``, ``* fact``
          2. Checklist öğeleri: ``- [ ] fact``, ``- [x] fact``
          3. Pipe table satırları: ``| Type | Description |``
          4. Blockquote: ``> fact``
          5. Kalın metin: ``**label:** value`` (inline veya ayrı satır)
          6. Alt başlıklar: ``### N. Title`` → label + takip eden içerik
          7. Kalın blok: ``**Bold Block**`` başlık + takip eden içerik
          8. Section bazlı: ``## Bölüm`` altındaki liste öğeleri
          9. Confusion table doğru bilgileri: son sütun değerleri
        """
        facts = []
        lines = content.split('\n')
        in_code_block = False
        in_frontmatter = False
        in_pipe_table = False  # Track table context
        
        # Section tracker for H2 grouping
        current_section = ""
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            raw = lines[i]
            
            # === CODE BLOCK TOGGLE ===
            if line.startswith('```'):
                in_code_block = not in_code_block
                i += 1
                continue
            if in_code_block:
                i += 1
                continue
            
            # === YAML FRONTMATTER SKIP ===
            if line == '---' and i == 0:
                in_frontmatter = True
                i += 1
                continue
            if in_frontmatter:
                if line == '---':
                    in_frontmatter = False
                i += 1
                continue
            
            # === TRACK H2 SECTION (for context/grouping) ===
            if line.startswith('## ') and not line.startswith('### '):
                current_section = line[3:].strip()
                i += 1
                continue
            
            # === H3 HEADING: "### N. Title"  → extract label + content ===
            if line.startswith('### '):
                heading_text = line[4:].strip()
                # Remove leading number: "1. Dependency Rule" → "Dependency Rule"
                heading_label = re.sub(r'^\d+[\.\)]\s*', '', heading_text)
                heading_label = heading_label.strip('*').strip()
                
                # Collect following content until next heading or empty line gap
                content_lines = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line.startswith('###') or next_line.startswith('## '):
                        break
                    if next_line.startswith('---'):
                        j += 1
                        break
                    if next_line.startswith('```'):
                        j += 1
                        break
                    if next_line:
                        content_lines.append(next_line)
                    else:
                        if j + 1 < len(lines) and not lines[j+1].strip():
                            break
                    j += 1
                
                if heading_label and content_lines:
                    combined = f"{heading_label}: {' '.join(content_lines)}"
                    if len(combined) > 10:
                        facts.append(combined)
                        i = j
                        continue
            
            # === BOLD BLOCK: "**Bold Title**" at line start ===
            if line.startswith('**') and '**' in line[2:] and not line.startswith('***'):
                bold_match = re.match(r'\*\*(.+?)\*\*', line)
                if bold_match:
                    bold_text = bold_match.group(1).strip()
                    if bold_text.endswith(':'):
                        i += 1
                        continue
                    
                    content_lines = []
                    after_bold = line[bold_match.end():].strip()
                    if after_bold:
                        content_lines.append(after_bold)
                    j = i + 1
                    while j < len(lines):
                        nl = lines[j].strip()
                        if nl.startswith('###') or nl.startswith('## '):
                            break
                        if nl.startswith('---') or nl.startswith('```'):
                            break
                        if nl:
                            content_lines.append(nl)
                        else:
                            break
                        j += 1
                    
                    if bold_text and content_lines:
                        combined = f"{bold_text}: {' '.join(content_lines)}"
                        if len(combined) > 10:
                            facts.append(combined)
                            i = j if j > i + 1 else i + 1
                            continue
            
            # === PIPE TABLE ROW: "| Type | Description |" ===
            if line.startswith('|') and line.count('|') >= 2:
                cols = [c.strip().strip('*') for c in line.split('|') if c.strip()]
                if len(cols) >= 2 and any(c.isalpha() for c in line):
                    # Skip table separators (|---|---|---|)
                    if not any(c.isalpha() for c in cols[0]) and not any(c.isalpha() for c in cols[-1]):
                        i += 1
                        in_pipe_table = False
                        continue
                    
                    in_pipe_table = True
                    
                    # Check if this is a 3+ column table (could be confusion or info)
                    if len(cols) >= 3:
                        # Extract all column pairs, prioritize last 2 (confusion pattern)
                        correct = cols[-1]  # Last column = "Doğrusu" / correct info
                        prev = cols[-2]     # Second-to-last = "LLM'in Genelde Dediği"
                        
                        # Skip header rows
                        header_keywords = {'konu', 'topic', 'type', 'description', 'when to use',
                                          "llm'in genelde dediği", "doğrusu", 'common misconception',
                                          'what llms usually say', 'correct'}
                        is_header = any(k in cols[0].lower() for k in header_keywords)
                        
                        if not is_header and correct and len(correct) > 3:
                            # Add the correct value as a fact
                            if correct not in facts and len(correct) > 5:
                                facts.append(correct)
                            # Also add "label: correct" format
                            if cols[0] and len(cols[0]) > 2 and len(cols[0] + ': ' + correct) > 10:
                                labeled = f"{cols[0]}: {correct}"
                                if labeled not in facts:
                                    facts.append(labeled)
                    
                    # 2-column tables: "| Type | Description |"
                    elif len(cols) == 2 and any(c.isalpha() for c in cols[1]) and len(cols[1]) > 5:
                        if cols[1] not in facts:
                            facts.append(cols[1])
                
                i += 1
                continue
            
            # === BLOCKQUOTE: "> text" ===
            if line.startswith('> '):
                fact = line.lstrip('> ').strip('* \t')
                if fact and len(fact) > 10:
                    facts.append(fact)
                # Multi-line blockquote: collect subsequent > lines as one fact
                combined_blockquote = fact
                j = i + 1
                while j < len(lines):
                    nl = lines[j].strip()
                    if nl.startswith('> '):
                        combined_blockquote += ' ' + nl.lstrip('> ').strip('* \t')
                        j += 1
                    elif nl == '>':
                        j += 1
                    else:
                        break
                if combined_blockquote != fact and len(combined_blockquote) > 15:
                    facts.append(combined_blockquote)
                i += 1
                continue
            
            # === CHECKLIST ITEM: "- [ ] fact" or "- [x] fact" ===
            if line.startswith('- [') and '] ' in line[:6]:
                fact = line.split('] ', 1)[-1].strip()
                # Inline bold in fact: "Write **exactly one** test" → use full text
                if fact and len(fact) > 5:
                    facts.append(fact)
            
            # === LIST ITEM: "- " veya "* " ===
            elif line.startswith('- ') or line.startswith('* '):
                fact = line[2:].strip()
                if fact and len(fact) > 5:
                    # Section context prefix (avoid duplication of long sections)
                    if current_section and current_section not in fact[:50]:
                        facts.append(fact)
                    else:
                        facts.append(fact)
            
            # === BOLD LABEL: "**Label:** value" (standalone line) ===
            elif ':**' in line[:40] and line.count('**') >= 2:
                # **Label:** Value → keep both
                fact = line.strip()
                if len(fact) > 5:
                    facts.append(fact)
            
            i += 1
        
        # Remove duplicates (preserve order)
        seen = set()
        unique_facts = []
        for f in facts:
            fl = f.lower().strip()
            if fl not in seen and len(f) > 10:
                # Check 85% similarity threshold for near-duplicates
                is_dup = False
                for existing in seen:
                    sm = SequenceMatcher(None, fl, existing)
                    if sm.ratio() > 0.85:
                        is_dup = True
                        break
                if not is_dup:
                    seen.add(fl)
                    unique_facts.append(f)
        
        return unique_facts if unique_facts else [content.strip()]
    
    def _extract_known_wrong_claims(self, content: str) -> list[tuple[str, str]]:
        """
        Confusion table'dan (yanlış, doğru) çiftlerini çıkar.
        
        Pipe tablosu formatı:
        | Konu | LLM'in Genelde Dediği | Doğrusu |
        | Üretim düğümü | TSMC 7nm | SKY130 (130nm) |
        
        Returns:
            [("TSMC 7nm", "SKY130 (130nm), OpenLane ile"),
             ("Genel AI hızlandırıcı", "Edge AI, tarım/güvenlik"), ...]
        """
        confusions = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('|') and line.count('|') >= 3:
                cols = [c.strip() for c in line.split('|') if c.strip()]
                if len(cols) >= 3:
                    wrong = cols[-2]  # sondan bir önceki: LLM'in Genelde Dediği
                    correct = cols[-1]  # son sütun: Doğrusu
                    # Skip: table separators (only ---, ===, etc.), headers, empty
                    is_separator = not any(c.isalpha() for c in wrong) and not any(c.isalpha() for c in correct)
                    if (wrong and wrong not in ('LLM\'in Genelde Dediği', '---', '')
                        and correct and correct not in ('Doğrusu', '---', '')
                        and not is_separator):
                        confusions.append((wrong, correct))
        
        return confusions
    
    def _get_significant_tokens(self, text: str) -> set[str]:
        """Metinden önemli token'ları çıkar (stopwords + çok kısa kelimeler hariç)."""
        # Temizle: markdown, noktalama
        clean = re.sub(r'[#*_`\[\]()|\\]', ' ', text.lower())
        words = re.findall(r'\b[a-zçğıöşü0-9]{2,}\b', clean)  # 2+ chars
        
        stopwords = {
            'bir', 've', 'bu', 'için', 'ile', 'olan', 'gibi', 'kadar', 'ama',
            'the', 'and', 'for', 'with', 'this', 'that', 'from', 'are', 'was',
            'nedir', 'hakkında', 'nasıl', 'olarak', 'tarafından', 'ancak',
            'is', 'not', 'but', 'or', 'as', 'to', 'of', 'in', 'on', 'at', 'by',
            'değil', 'daha', 'çok', 'sonra', 'önce', 'son', 'kadar', 'yeni',
            'başka', 'kendi', 'aynı', 'her', 'tüm', 'hem', 'ya', 'da', 'şey',
            'bir', 'iki', 'üç', 'vb', 'vs', 'dr', 'mr', 'no',  # kısaltmalar
        }
        
        return {w for w in words if w not in stopwords}
    
    def _are_relevant(self, claim_text: str, fact_text: str, *args, **kwargs) -> bool:
        """
        İki metnin aynı konuda olup olmadığını kontrol eder.
        
        Farklı konulardaki claim-fact çiftleri conflict olarak 
        işaretlenmemelidir (false positive önleme).
        """
        claim_tokens = self._get_significant_tokens(claim_text)
        fact_tokens = self._get_significant_tokens(fact_text)
        
        # İkisinden birinde anlamlı token yoksa → varsayılan olarak relevant
        if not claim_tokens or not fact_tokens:
            return True
        
        # Ortak anlamlı token var mı?
        if claim_tokens & fact_tokens:
            return True
        
        # Hiçbir bağlantı yok → farklı konu
        return False

    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
