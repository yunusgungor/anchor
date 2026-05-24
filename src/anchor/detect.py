"""
Anchor Conflict Detection — Sentence-level claim extraction + edit distance.

Bileşenler:
  ClaimExtractor: LLM output'undan konuyla ilgili cümleleri çıkar
  FactMatcher: KB fact'leriyle claim'leri karşılaştır
  SeverityEngine: Distance → severity mapping
  ConflictDetector: Üst seviye detector (tüm bileşenleri koordine eder)
"""

import re
import time
from difflib import SequenceMatcher
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from anchor import Conflict, Severity


@dataclass
class MatchResult:
    claim: str
    fact: str
    edit_distance: float      # 0-1 normalize edilmiş
    semantic_distance: float  # 0-1
    negative_distance: float  # 0-1
    combined_distance: float  # Ağırlıklı toplam
    is_conflict: bool         # Çelişki var mı?


@dataclass
class Claim:
    """LLM'in bir konu hakkında söylediği bir cümle."""
    text: str
    position: int
    keywords_found: list[str]
    confidence: float = 1.0


class ClaimExtractor:
    """
    LLM çıktısından, topic'le ilgili cümleleri çıkarır.
    Deterministic — hiçbir LLM çağrısı yok.
    """

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
        """Yeni API — doğrudan topic ve alias ile claim çıkar."""
        t0 = time.perf_counter()
        self._total_calls += 1

        all_terms = [topic.lower()] + [a.lower() for a in aliases]
        all_terms.sort(key=len, reverse=True)

        sentences = self._segment_sentences(llm_output)
        claims = []

        for sent, pos in sentences:
            sent_lower = sent.lower()
            found_terms = []
            for term in all_terms:
                if term in sent_lower:
                    found_terms.append(term)

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
    """KB'deki bir fact ile LLM'in claim'i arasındaki mesafeyi ölçer."""

    def __init__(self, alpha: float = 0.4, beta: float = 0.4, gamma: float = 0.2):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self._total_calls = 0
        self._total_latency_us = 0

    def match(self, claim: str, fact: str) -> MatchResult:
        t0 = time.perf_counter()
        self._total_calls += 1

        d_edit = self._compute_edit_distance(claim, fact)
        d_sem = self._compute_semantic_distance(claim, fact)
        d_neg = self._compute_negative_distance(claim)
        d_combined = self.alpha * d_edit + self.beta * d_sem + self.gamma * d_neg
        is_conflict = d_combined > 0.4

        result = MatchResult(
            claim=claim, fact=fact,
            edit_distance=d_edit, semantic_distance=d_sem,
            negative_distance=d_neg, combined_distance=d_combined,
            is_conflict=is_conflict,
        )

        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000
        return result

    def _compute_edit_distance(self, claim: str, fact: str) -> float:
        sm = SequenceMatcher(None, claim.lower(), fact.lower())
        return 1.0 - sm.ratio()

    def _compute_semantic_distance(self, claim: str, fact: str) -> float:
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

    def __init__(self, extractor: Optional["ClaimExtractor"] = None):
        self.extractor = extractor or ClaimExtractor()
        self.matcher = FactMatcher()
        self.severity = SeverityEngine()
        self._total_calls = 0
        self._total_latency_us = 0

    def detect(self, llm_output: str, rule, topics: list) -> list[Conflict]:
        """
        LLM output'unda rule'la ilgili çelişkileri tespit et.

        Args:
            llm_output: LLM'in ürettiği ham metin
            rule: KB'deki Rule objesi
            topics: Bulunan topic'ler

        Returns:
            Çelişki listesi
        """
        t0 = time.perf_counter()
        self._total_calls += 1

        conflicts = []

        # 1. Claim extraction
        claims = self.extractor.extract(llm_output, rule.topic, rule.aliases)

        if not claims:
            return []

        # 2. Rule'dan fact'leri parse et
        facts = self._extract_facts(rule.content)

        # 3. Her claim'i her fact'le karşılaştır
        for claim in claims:
            for fact in facts:
                match = self.matcher.match(claim.text, fact)

                if match.is_conflict:
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
        return conflicts

    def _extract_facts(self, content: str) -> list[str]:
        """Rule içeriğinden fact'leri çıkar.
        
        Desteklenen pattern'ler:
          - Liste öğeleri: ``- fact``, ``* fact``
          - Kalın metin: ``**label:** value``
          - Pipe tablosu: ``| Konu | Doğrusu |`` (3. sütun)
          - Kod blokları: ``kodu`` (içerik)
          - Normal paragraflar (boş satırla ayrılmış)
        """
        facts = []
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Liste öğeleri: - veya * ile başlayan
            if line.startswith('- ') or line.startswith('* '):
                fact = line[2:].strip()
                if fact and len(fact) > 5:
                    facts.append(fact)
            
            # Kalın metin: **label:** value
            elif re.match(r'\*\*[^*]+\*\*:', line):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    fact = parts[1].strip().strip('*').strip()
                    if fact and len(fact) > 3:
                        facts.append(fact)
            
            # Pipe tablosu: | Konu | LLM'in Dediği | Doğrusu |
            elif line.startswith('|') and line.count('|') >= 3:
                cols = [c.strip() for c in line.split('|') if c.strip()]
                # Son sütun doğru bilgi
                if len(cols) >= 3 and cols[-1] not in ('Doğrusu', '---', ''):
                    facts.append(cols[-1])
            
            # Kod bloğu içeriği
            elif line.startswith('```'):
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_line = lines[i].strip()
                    if code_line and len(code_line) > 5:
                        facts.append(code_line)
                    i += 1
            
            i += 1
        
        return facts if facts else [content.strip()]

    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
