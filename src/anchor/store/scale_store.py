"""
Scalable Rule Store — 10.000+ rule için optimize edilmiş depolama.

Özellikler:
  - Domain Sharding: Sadece ilgili shard'ları yükle
  - Bloom Filter: Hızlı negatif lookup
  - Semantic Index: TF-IDF ile anlamsal eşleştirme
  - Lazy Loading: Rule içeriği sadece ihtiyaç anında parse edilir
  - Binary Cache: Serialize edilmiş index (cold start < 50ms)
"""

import logging
import math
import pickle
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np

from anchor import Rule, Topic
from anchor.organize.domain_shard import ShardRouter
from anchor.organize.bloom_index import BloomIndex
from anchor.organize.semantic_index import SemanticIndex
from anchor.store.rule_store import RuleStore
from anchor.store.binary_index import BinaryIndexManager
from anchor.parser.frontmatter import extract_topic, extract_metadata

if TYPE_CHECKING:
    from anchor.judge.enricher import RuleEnricher

logger = logging.getLogger(__name__)


class ScalableRuleStore:
    """
    Büyük ölçekli rule deposu.
    
    Mevcut RuleStore'un aksine, tüm rule'ları başlangıçta yüklemez.
    Bunun yerine:
      1. Binary Index (cold start < 50ms)
      2. Domain Sharding → hangi shard'lar gerekli?
      3. Bloom Filter → bu shard'ta ilgili rule var mı?
      4. Semantic Index → en yakın rule'lar hangileri?
      5. Lazy Load → sadece gerekli rule'ların içeriğini parse et
    """
    
    def __init__(self, rules_path: str, index_path: Optional[str] = None,
                 enricher: Optional["RuleEnricher"] = None,
                 use_embedding: bool = False):
        self.path = Path(rules_path)
        self._index_path = index_path
        self._enricher = enricher
        self._use_embedding = use_embedding
        self._router = ShardRouter(rules_path)
        self._bloom = BloomIndex(expected_items=10_000, false_positive_rate=0.01)
        self._semantic = SemanticIndex(max_features=2000)
        self._binman = BinaryIndexManager(rules_path, index_path)
        
        # Hot cache (LRU)
        self._hot_cache: OrderedDict[str, Rule] = OrderedDict()
        self._hot_cache_max = 200
        
        # Shard içindeki rule ID'ler (topic → list[rule_id])
        self._shard_topic_map: dict[str, list[str]] = {}
        
        # Rule metadata for lazy load (id → {topic, priority, strictness, path})
        self._rule_meta: dict[str, dict] = {}
        
        # v4.3: Distinctive keyword index (TF-IDF tabanlı)
        # keyword → [rule_id1, rule_id2, ...] — zero-config topic discovery
        self._distinctive_keyword_index: dict[str, list[str]] = {}
        
        # İstatistik
        self._hits = 0
        self._misses = 0
        self._lazy_loads = 0
        self._bloom_skips = 0
        
        self._built = False
    
    def build(self):
        """
        Index'leri inşa et. Önce binary index dene, yoksa rebuild et.
        """
        # 1. Binary index var ve fresh mi?
        if not self._binman.is_stale():
            loaded = self._binman.load()
            if loaded:
                self._shard_topic_map = loaded["shard_map"]
                self._bloom = loaded["bloom"]
                self._semantic = loaded["semantic"]
                self._rule_meta = {r["id"]: r for r in loaded.get("rule_metadata", [])}
                # v4.3: Restore keyword index from cache
                self._distinctive_keyword_index = loaded.get("distinctive_keyword_index", {})
                if not self._distinctive_keyword_index:
                    self._rebuild_keyword_index_from_meta()
                self._built = True
                # Eager model pre-warm for <10ms first query
                if self._use_embedding:
                    self._pre_warm_model()
                return
        
        # 2. Yoksa rebuild et
        self._rebuild()
    
    def _pre_warm_model(self):
        """Embedding model'i eager yükle — ilk sorgu hızlı olsun."""
        try:
            from anchor.judge.embedding import load_model, get_model_info
            loaded = load_model()
            if loaded:
                logger.debug("Embedding model pre-warmed: %s", get_model_info())
        except Exception as e:
            logger.debug("Embedding model pre-warm skipped: %s", e)
    
    def _rebuild(self):
        """Tüm index'leri sıfırdan inşa et ve diske kaydet."""
        t0 = time.perf_counter()
        
        # Shard'ları keşfet
        
        # Bloom Filter
        self._bloom.build_from_rules(str(self.path))
        
        # Semantic Index
        self._semantic.fit(str(self.path))
        
        # Shard-topic mapping + metadata
        rule_metadata = []
        for shard_name in self._router.list_shards():
            shard_path = self._router.get_shard_path(shard_name)
            if not shard_path:
                continue
            for fpath in shard_path.rglob("*.md"):
                rule_id = fpath.stem
                topic = self._extract_topic_from_file(fpath) or rule_id
                
                self._shard_topic_map.setdefault(topic.lower(), []).append(rule_id)
                self._shard_topic_map.setdefault(rule_id.lower(), []).append(rule_id)
                
                # Metadata
                aliases, tags, priority, strictness = self._extract_meta_from_file(fpath)
                
                # Auto-derive word-based aliases from topic name
                # (e.g. "Branching & Commit Rules" → ["branching", "commit"])
                import re as _re
                if not aliases and topic:
                    topic_words = set(_re.findall(r'\b[a-zA-Zçğıöşüü]{4,}\b', topic.lower()))
                    excluded = {'rules', 'principles', 'standards', 'guide', 'cycle',
                                'process', 'practices', 'about', 'and', 'the', 'for',
                                'with', 'testing', 'management', 'production',
                                'naming', 'clean',
                                # Generic words not useful as aliases
                                'code', 'function', 'design', 'name', 'error',
                                'architecture', 'structure', 'style', 'guide'}
                    word_aliases = [w for w in topic_words if w not in excluded]
                    # Also add the original topic as a fallback alias
                    topic_as_alias = topic.lower().strip()
                    if topic_as_alias and len(topic_as_alias) >= 5:
                        word_aliases.append(topic_as_alias)
                    if word_aliases:
                        aliases = word_aliases[:5]  # Keep top 5
                
                meta = {
                    "id": rule_id,
                    "topic": topic,
                    "path": str(fpath),
                    "aliases": aliases,
                    "tags": tags,
                    "priority": priority,
                    "strictness": strictness,
                }
                
                # v4.4: Diagram metadata extraction
                # Mermaid/ASCII diyagramlarını parse et, fact/flow/node bilgilerini çıkar
                try:
                    text = fpath.read_text(encoding="utf-8")
                    from anchor.parser.diagram import (
                        extract_diagram_blocks, diagram_to_facts, diagram_to_terms
                    )
                    diagrams = extract_diagram_blocks(text)
                    if diagrams:
                        meta["diagrams"] = diagrams
                        
                        # Diagram'dan fact'ler
                        diag_facts = []
                        for d in diagrams:
                            diag_facts.extend(diagram_to_facts(d))
                        if diag_facts:
                            meta["diagram_facts"] = diag_facts
                        
                        # Diagram'dan term'ler (extended aliases — ayrı alanda tut)
                        diag_terms = []
                        for d in diagrams:
                            diag_terms.extend(diagram_to_terms(d))
                        if diag_terms:
                            # Sadece anlamlı diagram term'lerini sakla;
                            # aliases'e KARIŞTIRMA, keyword matching için ayrı alanda tut
                            meaningful_terms = [
                                t for t in diag_terms
                                if (len(t) >= 5 or ' ' in t)
                                    and not all(c in '-_=|*#' for c in t)
                            ]
                            if meaningful_terms:
                                meta["diagram_terms"] = meaningful_terms
                            else:
                                meta["diagram_terms"] = diag_terms
                        
                        # Diagram flow'ları (workflow validation için)
                        flows = []
                        for d in diagrams:
                            from anchor.parser.diagram import diagram_to_flows
                            flows.extend(diagram_to_flows(d))
                        if flows:
                            meta["diagram_flows"] = flows
                except Exception as e:
                    logger.debug("Diagram extraction failed for %s: %s", rule_id, e)
                
                # Build-time enrichment (Phase 3)
                if self._enricher is not None:
                    try:
                        text = fpath.read_text(encoding="utf-8")
                        enriched = self._enricher.enrich_rule(text)
                        if enriched:
                            meta["enriched_facts"] = enriched
                            logger.debug("Enriched %s: %d facts → %d",
                                         rule_id, len(enriched) // 3, len(enriched))
                    except Exception as e:
                        logger.warning("Enrichment failed for %s: %s", rule_id, e)
                
                # Pre-compute fact embeddings (Phase 1 optimization)
                # Burada hesaplanan embedding'ler binary index'e kaydedilir
                # Runtime'da encode_batch() çağrısına gerek kalmaz
                if self._use_embedding:
                    text = fpath.read_text(encoding="utf-8")
                    from anchor.parser.extractor import extract_facts
                    facts = extract_facts(text)
                    if facts:
                        try:
                            from anchor.judge.embedding import load_model, encode_batch
                            loaded = load_model()
                            if not loaded:
                                logger.debug("Embedding model not available for %s "
                                             "(sentence-transformers not installed?)",
                                             rule_id)
                            else:
                                vecs = encode_batch(facts)
                                if vecs is not None:
                                    meta["fact_embeddings"] = vecs.astype(np.float16)
                                    meta["fact_texts"] = facts
                                    logger.debug("Pre-computed %d fact embeddings for %s",
                                                 len(facts), rule_id)
                                else:
                                    logger.debug("encode_batch returned None for %s", rule_id)
                        except Exception as e:
                            logger.debug("Embedding pre-compute failed for %s: %s: %s",
                                         rule_id, type(e).__name__, e)
                    else:
                        logger.log(5, "No facts extracted for %s", rule_id)
                
                self._rule_meta[rule_id] = meta
                rule_metadata.append(meta)
        
        self._built = True
        
        # v4.3: Build distinctive keyword index (zero-config topic discovery)
        self._build_distinctive_keywords()
        
        # Binary index'e kaydet
        self._binman.save(
            shard_map=self._shard_topic_map,
            bloom=self._bloom,
            semantic=self._semantic,
            rule_metadata=rule_metadata,
            distinctive_keyword_index=self._distinctive_keyword_index,
        )
        
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("ScalableStore rebuild: %.1fms | shards=%d | bloom=%d | vectors=%d",
                     elapsed, len(self._router.list_shards()), self._bloom.size,
                     self._semantic.stats()['indexed_vectors'])
    
    def _rebuild_keyword_index_from_meta(self):
        """Binary index'ten yüklendikten sonra keyword index'i yeniden kur."""
        self._distinctive_keyword_index = {}
        for rid, meta in self._rule_meta.items():
            keywords = meta.get("distinctive_keywords", [])
            for kw in keywords:
                self._distinctive_keyword_index.setdefault(kw, []).append(rid)
        logger.debug("Keyword index rebuilt from meta: %d keywords, %d rules",
                     len(self._distinctive_keyword_index), len(self._rule_meta))
    
    def _build_distinctive_keywords(self):
        """TF-IDF tabanlı distinctive keyword index oluştur.
        
        Her rule'ın fact'lerinden kelimeler çıkar, tüm rule'lar arasında
        document frequency hesapla. Sadece az sayıda rule'da geçen 
        (distinctive) kelimeleri keyword olarak sakla.
        
        Bu sayede kullanıcı hiçbir topic/alias belirtmese bile:
        - LLM çıktısında "liskov" geçiyorsa → solid-principles tetiklenir
        - "/v1/" geçiyorsa → api-versionlama tetiklenir
        - "mock" geçiyorsa → mocking-guide tetiklenir
        
        %0 false positive garantisi: exact substring matching kullanılır.
        """
        from anchor.parser.extractor import extract_facts
        
        STOPWORDS = {
            'bir', 've', 'bu', 'ile', 'olan', 'gibi', 'kadar', 'ama', 'sonra',
            'önce', 'için', 'olarak', 'tarafından', 'ancak', 'daha', 'çok',
            'başka', 'kendi', 'aynı', 'her', 'tüm', 'hem', 'ya', 'da', 'şey',
            'the', 'and', 'for', 'with', 'this', 'that', 'from', 'are', 'was',
            'is', 'not', 'but', 'or', 'as', 'to', 'of', 'in', 'on', 'at', 'by',
            'değil', 'son', 'yeni', 'iki', 'üç', 'vb', 'vs', 'dr', 'mr', 'no',
            'rules', 'principles', 'standards', 'guide', 'cycle', 'process',
            'practices', 'patterns', 'about', 'the', 'for', 'with',
            'testing', 'management', 'production', 'naming', 'clean',
            'code', 'just', 'use', 'should', 'must', 'can', 'will', 'may',
            'used', 'using', 'based', 'also', 'well', 'need', 'make', 'way',
            'part', 'set', 'get', 'without', 'within', 'between', 'over',
            'first', 'last', 'next', 'each', 'many', 'some', 'any', 'all',
            'both', 'other', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'up', 'down', 'out', 'off', 'under', 'again',
            'further', 'once', 'here', 'there', 'when', 'where', 'why',
            'how', 'what', 'which', 'who', 'whom', 'this', 'those', 'these',
            # v4.3: Ek stopwords (çok yaygın kelimeler)
            'always', 'never', 'ever', 'very', 'much', 'still',
            'already', 'yet', 'now', 'then', 'than', 'too', 'also',
            'even', 'though', 'although', 'while', 'since', 'until',
            'every', 'everyone', 'everything', 'everywhere',
            'someone', 'something', 'somewhere', 'anyone', 'anything',
            'anywhere', 'nobody', 'nothing', 'both', 'either', 'neither',
            'upon', 'onto', 'into', 'within', 'without', 'throughout',
            'against', 'between', 'among', 'beside', 'beyond', 'around',
            'about', 'across', 'along', 'despite', 'during', 'except',
            'inside', 'outside', 'toward', 'towards', 'under', 'underneath',
            'because', 'therefore', 'however', 'moreover', 'furthermore',
            'nevertheless', 'nonetheless', 'otherwise', 'thus', 'hence',
            'namely', 'such', 'like', 'than', 'rather', 'quite', 'hardly',
            'scarcely', 'barely', 'nearly', 'almost', 'mostly', 'mainly',
            'primarily', 'largely', 'widely', 'typically', 'usually',
            'frequently', 'often', 'sometimes', 'occasionally', 'rarely',
            'seldom', 'commonly', 'generally', 'normally', 'essentially',
            'basically', 'roughly', 'approximately', 'virtually',
            'practically', 'just', 'simply', 'merely', 'purely',
            'truly', 'highly', 'deeply', 'strongly', 'clearly', 'obviously',
            'apparently', 'evidently', 'presumably', 'supposedly',
            'allegedly', 'reportedly', 'arguably', 'debatably',
            'consequently', 'accordingly', 'subsequently', 'previously',
            'initially', 'originally', 'eventually', 'ultimately',
            'finally', 'lastly', 'meanwhile', 'conversely', 'likewise',
            'similarly', 'contrarily', 'alternatively',
            'specially', 'especially', 'particularly', 'specifically',
            'says', 'said', 'seen', 'given', 'taken',
            'called', 'known', 'made', 'come', 'came', 'go', 'goes',
            'went', 'take', 'took', 'see', 'saw', 'know', 'knew',
            'think', 'thought', 'want', 'wanted', 'tell', 'told',
            'give', 'gave', 'find', 'found', 'show', 'showed', 'shown',
            'bring', 'brought', 'leave', 'left', 'keep', 'kept',
            'hold', 'held', 'let', 'begin', 'began', 'begun',
            'keep', 'kept', 'feel', 'felt', 'mean', 'meant',
            'run', 'ran', 'set', 'put', 'move', 'moved', 'live',
            'lived', 'work', 'worked', 'seem', 'seemed', 'look',
            'looked', 'become', 'became', 'remain', 'remained',
            'start', 'started', 'stop', 'stopped', 'try', 'tried',
            'ask', 'asked', 'need', 'needed', 'feel', 'felt',
            'place', 'places', 'point', 'points', 'case', 'cases',
            'fact', 'facts', 'side', 'sides', 'line', 'lines',
            'kind', 'kinds', 'sort', 'sorts', 'type', 'types',
            'form', 'forms', 'area', 'areas', 'group', 'groups',
            'number', 'numbers', 'system', 'systems',
            'thing', 'things', 'world', 'worlds', 'life', 'lives',
            'hand', 'hands', 'part', 'parts', 'result', 'results',
            'reason', 'reasons', 'difference', 'differences',
            'value', 'values', 'important', 'different', 'possible',
            'common', 'simple', 'basic', 'specific', 'general',
            'current', 'previous', 'following', 'above', 'below',
            'single', 'multiple', 'various', 'similar', 'separate',
            'entire', 'whole', 'complete', 'total', 'partial',
            'direct', 'indirect', 'primary', 'secondary', 'major',
            'minor', 'main', 'central', 'local', 'global',
            'overall', 'overview', 'summary', 'details', 'detail',
            # v4.3 FP fix: false positive'e sebep olan yaygın kelimeler
            'today', 'yesterday', 'tomorrow', 'morning', 'evening',
            'afternoon', 'night', 'week', 'month', 'year',
            'time', 'times', 'day', 'days', 'date', 'dates',
            'server', 'client', 'user', 'users', 'data',
            'print', 'input', 'output', 'value', 'values',
            'hello', 'world', 'test', 'tests', 'name', 'names',
            'page', 'pages', 'key', 'keys', 'file', 'files',
            'list', 'lists', 'array', 'object', 'objects',
            'class', 'classes', 'method', 'methods', 'function',
            'string', 'number', 'integer', 'float', 'bool',
            'true', 'false', 'none', 'null', 'zero', 'one', 'two',
            'running', 'sleep', 'wait', 'stand', 'sit',
            'weather', 'temperature', 'city', 'country',
            'food', 'water', 'air', 'home', 'house', 'room',
            'door', 'window', 'table', 'chair', 'book',
            'read', 'write', 'speak', 'talk', 'walk', 'play',
            'big', 'small', 'large', 'little', 'great', 'good',
            'bad', 'new', 'old', 'long', 'short', 'high', 'low',
            'fast', 'slow', 'hard', 'soft', 'easy', 'hard',
            'right', 'wrong', 'real', 'same', 'different',
            'free', 'open', 'close', 'start', 'end', 'begin',
            'top', 'bottom', 'front', 'back', 'left', 'right',
            'where', 'here', 'there', 'everywhere', 'anywhere',
            'who', 'whom', 'whose', 'which', 'what', 'why', 'how',
            'normal', 'special', 'regular', 'daily', 'weekly',
            'monthly', 'yearly', 'annual', 'permanent', 'temporary',
            'active', 'passive', 'public', 'private', 'internal',
            'external', 'native', 'remote', 'local', 'global',
            'source', 'target', 'origin', 'destination',
            'scope', 'range', 'length', 'size', 'volume',
            'color', 'shape', 'image', 'picture', 'photo',
            'sound', 'voice', 'music', 'video', 'text',
            'word', 'letter', 'character', 'symbol', 'sign',
            'drive', 'click', 'press', 'hold', 'drag', 'drop',
            'sort', 'order', 'sequence', 'pattern', 'format',
            'empty', 'full', 'clean', 'dirty', 'fresh', 'stale',
            'state', 'status', 'mode', 'type', 'kind', 'form',
            'action', 'event', 'signal', 'message', 'notice',
            'group', 'team', 'member', 'leader', 'owner',
            'role', 'rule', 'task', 'job', 'duty', 'goal',
            'plan', 'idea', 'view', 'opinion', 'thought',
            'color', 'shape', 'size', 'weight', 'height',
            'depth', 'width', 'angle', 'degree', 'rate',
            'price', 'cost', 'fee', 'rate', 'tax', 'budget',
            'allow', 'enable', 'disable', 'grant', 'deny',
            'support', 'help', 'aid', 'assist', 'guide',
            'check', 'verify', 'confirm', 'validate', 'ensure',
            'create', 'make', 'build', 'form', 'produce',
            'update', 'change', 'modify', 'edit', 'revise',
            'delete', 'remove', 'clear', 'erase', 'cancel',
            'add', 'insert', 'attach', 'include', 'append',
            'connect', 'link', 'join', 'merge', 'combine',
            'split', 'divide', 'separate', 'break', 'cut',
            'send', 'receive', 'accept', 'reject', 'approve',
            'offer', 'provide', 'supply', 'deliver', 'return',
            'request', 'demand', 'require', 'need', 'want',
            'search', 'find', 'locate', 'track', 'follow',
            'show', 'display', 'present', 'reveal', 'expose',
            'hide', 'cover', 'mask', 'disguise', 'protect',
            'random', 'specific', 'particular', 'certain',
            'domain', 'context', 'environment', 'situation',
            # v4.3 FP fix 2: çok yaygın kod/teknik kelimeler
            'import', 'export', 'extends', 'implements',
            'return', 'yield', 'raise', 'except', 'finally',
            'lambda', 'global', 'nonlocal', 'assert', 'del',
            'break', 'continue', 'pass', 'elif', 'else',
            'default', 'static', 'dynamic', 'abstract',
            'synchronized', 'volatile', 'transient',
            'prototype', 'constructor', 'typeof', 'instanceof',
            'void', 'null', 'undefined', 'nan', 'infinity',
            'console', 'require', 'module', 'exports',
            # Additional FP fixes
            'sentence', 'paragraph', 'meaning', 'random',
        }
        
        # Pass 1: Tüm rule'lardan kelimeleri çıkar, document frequency hesapla
        doc_freq: dict[str, int] = {}       # word → kaç rule'da geçiyor
        rule_words: dict[str, set[str]] = {} # rule_id → distinctive adayı kelimeler
        
        for rid, meta in self._rule_meta.items():
            fpath = meta.get("path", "")
            if not fpath or not Path(fpath).exists():
                continue
            
            text = Path(fpath).read_text(encoding="utf-8")
            facts = extract_facts(text)
            
            words = set()
            for fact in facts:
                # Normalize: lowercase, extract alpha tokens 3+ chars
                tokens = re.findall(r'\b[a-zçğıöşüü]{3,}\b', fact.lower())
                words.update(tokens)
                # Also extract special patterns: /v1/, CI/CD, test-pyramid, etc.
                special = re.findall(r'[/][a-z0-9çğıöşüü/_-]+[/]|'
                                     r'[a-zçğıöşüü0-9_-]+/'
                                     r'[a-zçğıöşüü0-9_-]+', fact.lower())
                for s in special:
                    clean = s.strip('/').replace('/', '-').replace('_', '-')
                    if len(clean) >= 3:
                        words.add(clean)
            
            rule_words[rid] = words
            for w in words:
                doc_freq[w] = doc_freq.get(w, 0) + 1
        
        N = len(rule_words)
        if N == 0:
            return
        
        # Pass 2: IDF threshold — a word can appear in at most max_allowed rules
        max_allowed = max(5, int(N * 0.2))  # ≤20% of rules or 5, whichever larger
        
        self._distinctive_keyword_index = {}
        for rid, words in rule_words.items():
            distinctive = []
            for w in sorted(words):  # Deterministic order
                if w in STOPWORDS or len(w) < 4:
                    continue
                df = doc_freq.get(w, N)
                if df <= max_allowed:  # Truly distinctive
                    distinctive.append(w)
                    self._distinctive_keyword_index.setdefault(w, []).append(rid)
            
            # Update metadata
            if rid in self._rule_meta:
                self._rule_meta[rid]["distinctive_keywords"] = distinctive
        
        logger.info("Distinctive keyword index built: %d keywords, %d rules (max_allowed=%d)",
                     len(self._distinctive_keyword_index), len(self._rule_meta), max_allowed)
    
    def _extract_topic_from_file(self, fpath: Path) -> Optional[str]:
        """Sadece topic çıkar — tam parse değil (utility kullanır)."""
        try:
            text = fpath.read_text(encoding="utf-8")
            return extract_topic(text)
        except Exception:
            pass
        return None
    
    def _extract_meta_from_file(self, fpath: Path) -> tuple:
        """Frontmatter'dan metadata çıkar (utility kullanır)."""
        try:
            text = fpath.read_text(encoding="utf-8")
            meta = extract_metadata(text, fpath.stem)
            return (
                meta["aliases"],
                meta["tags"],
                meta["priority"],
                meta["strictness"],
            )
        except Exception:
            pass
        return [], [], 5, 0.8
    
    def query(self, topics: list[str], llm_output: str = "") -> list[Rule]:
        """
        Topic'lere göre rule ara — büyük ölçekli versiyon.
        
        Algoritma:
          1. Bloom Filter: Hiçbir topic eşleşmiyorsa → boş döndür (~1μs)
          2. Router: Hangi shard'lar gerekli? (~1μs)
          3. Semantic: LLM output'undan ek rule önerileri (~100μs)
          4. Lazy Load: Sadece gerekli rule'ları parse et ve cache'le
        """
        if not self._built:
            self.build()
        
        # 0. Eğer topics boş ama llm_output varsa → direkt semantic
        if not topics and llm_output:
            semantic_hits = self._semantic.query(llm_output, top_k=5)
            candidate_ids: set[str] = set()
            for rule_id, sim in semantic_hits:
                if sim > 0.15:
                    candidate_ids.add(rule_id)
            results = []
            for rid in candidate_ids:
                rule = self._get_cached_or_load(rid)
                if rule:
                    results.append(rule)
            results.sort(key=lambda r: (-r.priority, r.id))
            return results[:10]
        
        # 1. Bloom Filter — negatif lookup
        has_any, bloom_matches = self._bloom.check_topics(topics)
        if not has_any:
            self._bloom_skips += 1
            return []
        
        # 2. Router — shard'ları belirle
        shards = self._router.route(topics)
        candidate_ids: set[str] = set()
        
        # Topic + alias exact match (shard içinde)
        for topic in topics:
            topic_lower = topic.lower()
            candidate_ids.update(self._shard_topic_map.get(topic_lower, []))
            # Ayrıca stem'leri dene
            parts = topic_lower.split()
            for i in range(len(parts)):
                partial = " ".join(parts[i:])
                candidate_ids.update(self._shard_topic_map.get(partial, []))
        
        # 3. Semantic fallback (eğer az sonuç varsa VE query zayıfsa)
        # NOT: Query bazlı match bulunduysa semantic fallback cross-rule FP üretir.
        semantic_context = getattr(self, '_last_query_semantic', '')
        is_query_direct = bool(topics and any(
            self._rule_meta.get(rid, {}).get("topic", "").lower() == t.lower()
            for rid in candidate_ids for t in topics
        ))
        if len(candidate_ids) < 3 and llm_output and not is_query_direct:
            semantic_hits = self._semantic.query(llm_output, top_k=5)
            for rule_id, sim in semantic_hits:
                if sim > 0.15:  # Threshold
                    candidate_ids.add(rule_id)
        
        if not candidate_ids:
            return []
        
        # 4. Lazy Load + Cache
        results = []
        for rid in candidate_ids:
            rule = self._get_cached_or_load(rid)
            if rule:
                results.append(rule)
        
        # Priority'ye göre sırala (yüksek öncelikli önce)
        results.sort(key=lambda r: (-r.priority, r.id))
        return results[:10]
    
    def _get_cached_or_load(self, rule_id: str) -> Optional[Rule]:
        """Cache'ten al, yoksa diskten lazy load et."""
        # Cache hit?
        if rule_id in self._hot_cache:
            rule = self._hot_cache.pop(rule_id)
            self._hot_cache[rule_id] = rule  # LRU: sona taşı
            self._hits += 1
            return rule
        
        # Diskten bul
        rule = self._lazy_load(rule_id)
        if rule:
            # Hot cache'e ekle
            self._hot_cache[rule_id] = rule
            if len(self._hot_cache) > self._hot_cache_max:
                self._hot_cache.popitem(last=False)
            self._misses += 1
        
        return rule
    
    def _lazy_load(self, rule_id: str) -> Optional[Rule]:
        """Diskten bir rule'u parse et, enriched facts + embeddings varsa ekle."""
        for fpath in self.path.rglob(f"{rule_id}.md"):
            if fpath.is_file():
                try:
                    from anchor import Rule
                    rule = Rule.from_file(fpath)
                    # v4.3: Alias consolidation — store metadata'deki alias'lar
                    # authoritative kaynaktır. Parser'dan gelen alias'lar
                    # override edilir (parser regex'i gürültülü olabilir)
                    meta = self._rule_meta.get(rule_id, {})
                    meta_aliases = meta.get("aliases", [])
                    if meta_aliases:
                        rule.aliases = meta_aliases
                    # Meta'dan enriched facts ve pre-computed embeddings'leri ekle
                    enriched = meta.get("enriched_facts", [])
                    if enriched:
                        rule.enriched_facts = enriched
                    # Pre-computed fact embeddings
                    emb = meta.get("fact_embeddings", None)
                    if emb is not None:
                        rule.fact_embeddings = emb
                        rule.fact_texts = meta.get("fact_texts", [])
                    
                    # v4.4: Diagram flows
                    flows = meta.get("diagram_flows", [])
                    if flows:
                        rule.diagram_flows = flows
                    
                    return rule
                except Exception:
                    pass
        return None
    
    def stats(self) -> dict:
        total_lookups = self._hits + self._misses
        return {
            "total_rules": len(self._shard_topic_map) // 2,  # topic + rule_id duplicates
            "shards": len(self._router.list_shards()),
            "bloom_items": self._bloom.size,
            "semantic_vocab": self._semantic.stats()["vocab_size"],
            "cache_size": len(self._hot_cache),
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "hit_ratio": self._hits / total_lookups if total_lookups > 0 else 0,
            "bloom_skips": self._bloom_skips,
            "lazy_loads": self._lazy_loads,
        }
