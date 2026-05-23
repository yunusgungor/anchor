"""
Conflict Detection — LLM çıktısı ile Knowledge Base arasındaki çelişkileri tespit.

Strateji:
  1. Topic bazlı claim extraction (LLM'in konu hakkında ne dediği)
  2. KB'deki fact'lerle karşılaştırma
  3. Severity skorlama
"""

import re
from difflib import SequenceMatcher
from typing import Optional

from anchor import Conflict, Rule, Severity, Topic


class ConflictDetector:
    """
    LLM çıktısındaki claim'lerle KB fact'leri arasındaki çelişkileri tespit eder.
    
    Üç seviye analiz:
      1. String-level: Direkt metin karşılaştırma
      2. Pattern-level: Regex ile önemli ifadeleri yakalama
      3. Embedding-level: Semantik mesafe (opsiyonel)
    """
    
    def __init__(self):
        self._total_calls = 0
        self._total_latency_us = 0
    
    def detect(self, llm_output: str, rule: Rule, topics: list[Topic]) -> list[Conflict]:
        """
        Bir rule için LLM çıktısındaki çelişkileri tespit et.
        """
        import time
        t0 = time.perf_counter()
        self._total_calls += 1
        
        conflicts = []
        
        # Rule'un içindeki "Doğru Bilgiler" bölümünü bul
        facts = self._extract_facts(rule.content)
        
        # Rule'un içindeki "Sık Karıştırılan Noktalar" tablosunu bul
        confusion_table = self._extract_confusion_table(rule.content)
        
        # Her fact için LLM çıktısını kontrol et
        for fact in facts:
            conflict = self._check_fact(llm_output, fact, rule.id, rule.topic)
            if conflict:
                conflicts.append(conflict)
        
        # Karıştırılan noktalar tablosundaki her satır için kontrol et
        for row in confusion_table:
            conflict = self._check_confusion_row(llm_output, row, rule.id, rule.topic)
            if conflict:
                conflicts.append(conflict)
        
        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000
        
        return conflicts
    
    def _extract_facts(self, content: str) -> list[dict]:
        """
        Content'ten "Doğru Bilgiler" bölümündeki fact'leri çıkar.
        Her fact: {subject, statement, keywords}
        """
        facts = []
        
        # "Doğru Bilgiler" veya "## Doğru" başlığından sonraki listeyi bul
        section = self._find_section(content, ["Doğru Bilgiler", "Doğru", "Facts", "Correct", "Knowledge"])
        if section:
            for line in section.split('\n'):
                line = line.strip()
                # Liste öğeleri: "- **Mimari:** RISC-V + Systolic Array NPU"
                m = re.match(r'^[-*]\s+\*\*(.+?)\*\*:\s*(.+)$', line)
                if m:
                    facts.append({
                        'subject': m.group(1).strip(),
                        'statement': m.group(2).strip(),
                        'keywords': self._extract_keywords_from_text(m.group(2))
                    })
                # Liste öğeleri: "- Herhangi bir metin"
                m2 = re.match(r'^[-*]\s+(.+)$', line)
                if m2 and not m:
                    text = m2.group(1).strip()
                    if len(text) > 10:  # Çok kısa maddeleri atla
                        facts.append({
                            'subject': '',
                            'statement': text,
                            'keywords': self._extract_keywords_from_text(text)
                        })
        else:
            # Fallback: tüm liste öğelerini tara
            for line in content.split('\n'):
                line = line.strip()
                m = re.match(r'^[-*]\s+(.+)$', line)
                if m and len(m.group(1)) > 15:
                    text = m.group(1).strip()
                    facts.append({
                        'subject': '',
                        'statement': text,
                        'keywords': self._extract_keywords_from_text(text)
                    })
        
        return facts
    
    def _extract_confusion_table(self, content: str) -> list[dict]:
        """
        "Sık Karıştırılan Noktalar" tablosunu parse et.
        Her satır: {topic, common_mistake, correct_fact}
        """
        rows = []
        
        section = self._find_section(content, [
            "Sık Karıştırılan Noktalar", 
            "Sık Karıştırılan", 
            "Confusion",
            "Common Mistakes",
            "Yanlış/Doğru"
        ])
        
        if section:
            lines = section.split('\n')
            in_table = False
            headers = []
            
            for line in lines:
                if line.strip().startswith('|') and line.strip().endswith('|'):
                    cells = [c.strip() for c in line.strip().strip('|').split('|')]
                    
                    if not in_table:
                        # İlk row → başlık kontrolü
                        if any(h in cells[0].lower() for h in ['konu', 'topic', 'llm']):
                            headers = cells
                            in_table = True
                            continue
                    
                    if in_table:
                        # Ayırıcı satırı atla (---|---|---)
                        if all(c.strip().startswith('-') for c in cells if c.strip()):
                            continue
                        
                        if len(cells) >= 3:
                            rows.append({
                                'topic': cells[0].strip(),
                                'common_mistake': cells[1].strip() if len(cells) > 1 else '',
                                'correct_fact': cells[2].strip() if len(cells) > 2 else '',
                            })
        
        return rows
    
    def _check_fact(self, llm_output: str, fact: dict, rule_id: str, topic: str) -> Optional[Conflict]:
        """Bir fact için LLM çıktısını kontrol et."""
        # Subject LLM output'ta geçiyor mu?
        if fact['subject']:
            subject_pattern = re.compile(
                re.escape(fact['subject']), 
                re.IGNORECASE
            )
            if not subject_pattern.search(llm_output):
                return None  # Bu konu LLM çıktısında yok
        
        # Keyword'ler LLM output'ta geçiyor mu?
        keyword_hits = 0
        for kw in fact['keywords']:
            if kw.lower() in llm_output.lower():
                keyword_hits += 1
        
        # Eğer hiçbir keyword eşleşmiyorsa → LLM farklı bir şey söylüyor olabilir
        if fact['keywords'] and keyword_hits == 0:
            # LLM bu konuda bir şey söylemiş mi kontrol et
            if fact['subject']:
                # Subject geçiyorsa ama keyword yok → çelişki
                return Conflict(
                    rule_id=rule_id,
                    topic=topic,
                    severity=Severity.WARNING,
                    llm_claim=f"'{fact['subject']}' hakkında farklı bilgi veriyor",
                    kb_fact=fact['statement']
                )
        
        # Keyword'lerin tersini kontrol et (LLM olumsuzunu söylüyor mu?)
        for kw in fact['keywords']:
            negative_patterns = [
                rf'(?:değil|not|yanlış|wrong|değildir)\s+{re.escape(kw)}',
                rf'{re.escape(kw)}\s+(?:değil|not|yanlış|wrong)',
            ]
            for pat in negative_patterns:
                if re.search(pat, llm_output, re.IGNORECASE):
                    return Conflict(
                        rule_id=rule_id,
                        topic=topic,
                        severity=Severity.CRITICAL,
                        llm_claim=f"'{kw}' için olumsuz ifade kullanıyor",
                        kb_fact=fact['statement']
                    )
        
        return None
    
    def _check_confusion_row(self, llm_output: str, row: dict, rule_id: str, topic: str) -> Optional[Conflict]:
        """Karıştırılan noktalar tablosundaki bir satır için kontrol et."""
        # LLM yaygın hatayı mı söylüyor?
        if row['common_mistake']:
            mistake_keywords = self._extract_keywords_from_text(row['common_mistake'])
            hits = sum(1 for kw in mistake_keywords if kw.lower() in llm_output.lower())
            
            if hits >= len(mistake_keywords) * 0.5:
                # LLM yanlış bilgiyi söylüyor
                return Conflict(
                    rule_id=rule_id,
                    topic=topic,
                    severity=Severity.ERROR,
                    llm_claim=row['common_mistake'],
                    kb_fact=row['correct_fact'] if row['correct_fact'] else row['common_mistake']
                )
        
        return None
    
    def _find_section(self, content: str, headings: list[str]) -> Optional[str]:
        """Bir başlık altındaki bölümü bul."""
        for heading in headings:
            # Markdown başlığı (## veya ###)
            pattern = re.compile(
                rf'^#{{1,3}}\s*{re.escape(heading)}\s*$(.+?)(?=^#|\Z)', 
                re.MULTILINE | re.DOTALL
            )
            m = pattern.search(content)
            if m:
                return m.group(1).strip()
        return None
    
    def _extract_keywords_from_text(self, text: str) -> list[str]:
        """Metinden önemli kelimeleri çıkar."""
        # Küçük/hepsini büyük/karma kelimeleri al, bağlaçları atla
        words = re.findall(r'\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]*(?::?\s*[A-ZÇĞİÖŞÜ][a-zçğıöşü]*)*\b|\b[A-Z]{2,}\b|\b\d+\w*\b', text)
        if not words:
            # Fallback: tüm kelimeler
            words = re.findall(r'\b\w{4,}\b', text)
        return words
    
    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
