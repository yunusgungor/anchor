"""
Claim Extractor v2 — LLM output'undan topic'le ilgili cümleleri çıkar.

Strateji:
  1. Cümle segmentasyonu
  2. Her cümlede topic/alias keyword'lerini ara
  3. Eşleşen cümleleri claim olarak döndür
"""

import re
from dataclasses import dataclass


@dataclass
class Claim:
    """LLM'in bir konu hakkında söylediği bir cümle."""
    text: str
    position: int           # Cümlenin metindeki başlangıç pozisyonu
    keywords_found: list[str]  # Hangi keyword'ler eşleşti
    confidence: float = 1.0  # Bu cümlede topic geçtiğine dair güven


class ClaimExtractor:
    """
    LLM çıktısından, topic'le ilgili cümleleri çıkarır.
    
    Deterministic — hiçbir LLM çağrısı yok.
    """
    
    def __init__(self):
        self._total_calls = 0
        self._total_latency_us = 0
    
    def extract(self, llm_output: str, topic: str, aliases: list[str]) -> list[Claim]:
        """
        LLM output'undan topic'le ilgili cümleleri çıkar.
        
        Args:
            llm_output: LLM'in ürettiği ham metin
            topic: Ana konu başlığı (örn: "Neural Processor X1")
            aliases: Alternatif isimler (örn: ["NPX1", "riscv-npu"])
            
        Returns:
            Topic'le ilgili claim'ler (cümleler)
        """
        import time
        t0 = time.perf_counter()
        self._total_calls += 1
        
        # Tüm eşleştirilecek terimler
        all_terms = [topic.lower()] + [a.lower() for a in aliases]
        # Çok kelimeliler önce (daha spesifik)
        all_terms.sort(key=len, reverse=True)
        
        # Cümlelere böl
        sentences = self._segment_sentences(llm_output)
        
        claims = []
        for sent, pos in sentences:
            sent_lower = sent.lower()
            found_terms = []
            
            for term in all_terms:
                if term in sent_lower:
                    found_terms.append(term)
            
            if found_terms:
                # Confidence: ne kadar spesifik term bulundu?
                # Uzun/çok kelimeli term → daha yüksek confidence
                avg_term_len = sum(len(t.split()) for t in found_terms) / len(found_terms)
                confidence = min(1.0, 0.5 + avg_term_len * 0.15)
                
                claims.append(Claim(
                    text=sent,
                    position=pos,
                    keywords_found=found_terms,
                    confidence=confidence,
                ))
        
        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000
        
        return claims
    
    def _segment_sentences(self, text: str) -> list[tuple[str, int]]:
        """
        Metni cümlelere böl. Her cümle (text, start_position) döndür.
        """
        # Regex: .!? ile biten cümleler
        pattern = re.compile(r'[^.!?]+[.!?]+')
        sentences = []
        
        for m in pattern.finditer(text):
            sent = m.group().strip()
            if len(sent) > 10:  # Çok kısa cümleleri atla
                sentences.append((sent, m.start()))
        
        # Eğer hiç cümle bulunamazsa → tüm metin bir cümle olsun
        if not sentences and text.strip():
            sentences.append((text.strip(), 0))
        
        return sentences
    
    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
