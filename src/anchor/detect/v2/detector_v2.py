"""
Conflict Detector v2 — Sentence-level claim extraction + edit distance.

Pipeline:
  1. Extract facts from rule
  2. Extract claims from LLM output (sentence-level)
  3. Match each claim against each fact
  4. Score severity based on distance metrics
  5. Return conflicts with positional information
"""

import re
import time
from typing import Optional

from anchor import Conflict, Rule, Severity, Topic

from .claim_extractor import ClaimExtractor
from .fact_matcher import FactMatcher
from .severity_engine import SeverityEngine


class ConflictDetectorV2:
    """
    v2 conflict detector.
    
    Mevcut detector keyword matching yaparken,
    bu versiyon sentence-level claim extraction + edit distance kullanır.
    """
    
    def __init__(self):
        self.extractor = ClaimExtractor()
        self.matcher = FactMatcher()
        self.severity = SeverityEngine()
        
        self._total_calls = 0
        self._total_latency_us = 0
    
    def detect(self, llm_output: str, rule: Rule, topics: list[Topic]) -> list[Conflict]:
        """
        LLM çıktısındaki çelişkileri tespit et.
        
        Args:
            llm_output: LLM'in ürettiği ham metin
            rule: Kontrol edilecek rule
            topics: Çıkarılan topic'ler
            
        Returns:
            Çelişki listesi (cümle-level pozisyon bilgisiyle)
        """
        t0 = time.perf_counter()
        self._total_calls += 1
        
        # 1. Rule'dan fact'leri çıkar
        facts = self._extract_facts(rule.content)
        
        # 2. Confusion table'dan "yanlış bilgi" pattern'lerini çıkar
        confusion_rows = self._extract_confusion_rows(rule.content)
        
        # 3. LLM output'undan claim'leri çıkar
        aliases = rule.aliases + [rule.topic]
        claims = self.extractor.extract(llm_output, rule.topic, aliases)
        
        conflicts = []
        
        # 4. Her claim'i her fact ile karşılaştır
        for claim in claims:
            for fact_text in facts:
                match = self.matcher.match(claim.text, fact_text)
                
                if match.is_conflict:
                    sev = self.severity.compute(match)
                    
                    conflicts.append(Conflict(
                        rule_id=rule.id,
                        topic=rule.topic,
                        severity=sev,
                        llm_claim=claim.text,
                        kb_fact=fact_text,
                        patch_position=claim.position,
                        confidence=match.combined_distance,
                    ))
        
        # 5. Confusion table: LLM yaygın hatayı söylüyor mu?
        for row in confusion_rows:
            if self._claim_matches_mistake(llm_output, row["common_mistake"]):
                # LLM yanlış bilgiyi söylüyor
                conflicts.append(Conflict(
                    rule_id=rule.id,
                    topic=rule.topic,
                    severity=Severity.ERROR,
                    llm_claim=row["common_mistake"],
                    kb_fact=row["correct_fact"],
                    patch_position=0,
                    confidence=0.9,
                ))
        
        # Duplicate'leri temizle (aynı pozisyondaki çelişkileri birleştir)
        conflicts = self._deduplicate(conflicts)
        
        # En yüksek severity'yi tut
        conflicts.sort(key=lambda c: (-c.severity.value, -c.confidence))
        
        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000
        
        return conflicts
    
    def _extract_facts(self, content: str) -> list[str]:
        """Rule content'ten 'Doğru Bilgiler' fact'lerini çıkar."""
        facts = []
        
        # "Doğru Bilgiler" veya "## Doğru" başlığından sonraki listeyi bul
        section = self._find_section(content, ["Doğru Bilgiler", "Doğru", "Facts", "Correct", "Knowledge"])
        if section:
            for line in section.split('\n'):
                line = line.strip()
                # Liste öğeleri: "- **Subject:** Statement"
                m = re.match(r'^[-*]\s+\*\*(.+?)\*\*:\s*(.+)$', line)
                if m:
                    facts.append(f"{m.group(1).strip()}: {m.group(2).strip()}")
                # Basit liste öğeleri
                m2 = re.match(r'^[-*]\s+(.+)$', line)
                if m2 and len(m2.group(1)) > 10:
                    facts.append(m2.group(1).strip())
        
        return facts
    
    def _extract_confusion_rows(self, content: str) -> list[dict]:
        """Karıştırılan noktalar tablosundan hata pattern'lerini çıkar."""
        rows = []
        section = self._find_section(content, [
            "Sık Karıştırılan Noktalar", "Sık Karıştırılan", "Confusion", "Common Mistakes"
        ])
        
        if section:
            lines = section.split('\n')
            in_table = False
            
            for line in lines:
                if line.strip().startswith('|') and line.strip().endswith('|'):
                    cells = [c.strip() for c in line.strip().strip('|').split('|')]
                    
                    if not in_table:
                        if any(h in cells[0].lower() for h in ['konu', 'topic', 'llm']):
                            in_table = True
                            continue
                    
                    if in_table:
                        if all(c.strip().startswith('-') for c in cells if c.strip()):
                            continue
                        if len(cells) >= 3:
                            rows.append({
                                'topic': cells[0],
                                'common_mistake': cells[1],
                                'correct_fact': cells[2],
                            })
        
        return rows
    
    def _claim_matches_mistake(self, llm_output: str, mistake: str) -> bool:
        """LLM output'unda yaygın hata pattern'i var mı?"""
        if not mistake:
            return False
        
        # Anahtar kelimeleri çıkar
        keywords = re.findall(r'\b\w{3,}\b', mistake.lower())
        if not keywords:
            return False
        
        # LLM output'ta bu keyword'lerin çoğu var mı?
        llm_lower = llm_output.lower()
        hits = sum(1 for kw in keywords if kw in llm_lower)
        return hits >= len(keywords) * 0.5
    
    def _find_section(self, content: str, headings: list[str]) -> Optional[str]:
        """Bir başlık altındaki bölümü bul."""
        for heading in headings:
            pattern = re.compile(
                rf'^#{{1,3}}\s*{re.escape(heading)}\s*$(.+?)(?=^#|\Z)',
                re.MULTILINE | re.DOTALL
            )
            m = pattern.search(content)
            if m:
                return m.group(1).strip()
        return None
    
    def _deduplicate(self, conflicts: list[Conflict]) -> list[Conflict]:
        """Aynı pozisyondaki duplicate çelişkileri temizle."""
        seen_positions = set()
        unique = []
        for c in conflicts:
            key = (c.patch_position, c.llm_claim[:50])
            if key not in seen_positions:
                seen_positions.add(key)
                unique.append(c)
        return unique
    
    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
