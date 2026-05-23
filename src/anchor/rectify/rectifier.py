"""
Rectifier — Tespit edilen çelişkileri düzelterek çıktıyı iyileştirir.

Strateji:
  - Kritik/Error çelişkileri → direkt düzelt (override)
  - Warning → dipnot ekle
  - Info → sessiz geç (veya dipnot)
"""

import re
from typing import Optional

from anchor import Conflict, Correction, RectificationResult, Severity


class Rectifier:
    """
    Conflict'leri alır, LLM çıktısını düzeltir.
    
    Düzeltme stratejileri:
      CRITICAL → Override: yanlış ifadeyi KB'deki doğruyla değiştir
      ERROR → Patch: hatalı cümleyi düzelt
      WARNING → Annotate: dipnot ekle
      INFO → Skip: ek bilgi varsa isteğe bağlı dipnot
    """
    
    def __init__(self):
        self._total_calls = 0
        self._total_latency_us = 0
    
    def rectify(self, text: str, conflicts: list[Conflict]) -> RectificationResult:
        """
        Ana rectification metodu.
        
        Args:
            text: LLM çıktısı (ham)
            conflicts: ConflictDetector'dan gelen çelişkiler
            
        Returns:
            RectificationResult (düzeltilmiş metin + rapor)
        """
        import time
        t0 = time.perf_counter()
        self._total_calls += 1
        
        if not conflicts:
            result = RectificationResult(
                original=text,
                corrected=text,
                modified=False,
            )
            t1 = time.perf_counter()
            result.latency_us['rectify'] = (t1 - t0) * 1_000_000
            return result
        
        corrections: list[Correction] = []
        current_text = text
        
        # Önce severity'e göre sırala (önce kritik)
        sorted_conflicts = sorted(conflicts, key=lambda c: -c.severity.value)
        
        for conflict in sorted_conflicts:
            if conflict.severity == Severity.CRITICAL:
                corr = self._override(current_text, conflict)
            elif conflict.severity == Severity.ERROR:
                corr = self._patch(current_text, conflict)
            elif conflict.severity == Severity.WARNING:
                corr = self._annotate(current_text, conflict)
            else:
                continue  # INFO → pas geç
            
            if corr:
                corrections.append(corr)
                current_text = corr.corrected_text
        
        result = RectificationResult(
            original=text,
            corrected=current_text,
            corrections=corrections,
            modified=len(corrections) > 0,
        )
        
        t1 = time.perf_counter()
        result.latency_us['rectify'] = (t1 - t0) * 1_000_000
        
        return result
    
    def _override(self, text: str, conflict: Conflict) -> Optional[Correction]:
        """
        CRITICAL: Doğrudan override.
        
        LLM'in yanlış ifadesini bul, KB'deki doğruyla değiştir.
        """
        # Yanlış ifadeyi metinde bulmaya çalış
        claim_keywords = self._extract_claim_keywords(conflict.llm_claim)
        
        for kw in claim_keywords:
            if kw and kw.lower() in text.lower():
                # Bu keyword'ü içeren cümleyi bul
                sentences = re.split(r'(?<=[.!?])\s+', text)
                for i, sentence in enumerate(sentences):
                    if kw.lower() in sentence.lower():
                        # Cümleyi düzelt
                        old_sentence = sentence
                        new_sentence = self._replace_in_sentence(
                            sentence, kw, conflict.kb_fact
                        )
                        
                        if new_sentence != old_sentence:
                            sentences[i] = new_sentence
                            corrected = ' '.join(sentences)
                            
                            # Dipnot ekle
                            note = (
                                f"\n\n> ⚠️ **ANCHOR Düzeltmesi:** "
                                f"'{conflict.topic}' hakkında KB'de farklı bilgi var. "
                                f"LLM '{conflict.llm_claim}' derken, "
                                f"doğrusu: {conflict.kb_fact}"
                            )
                            
                            return Correction(
                                conflict=conflict,
                                original_text=old_sentence,
                                corrected_text=sentence,
                                edit_distance=len(old_sentence.split())
                            )
        
        # Keyword bulunamazsa → sona dipnot ekle
        note = (
            f"\n\n> ⚠️ **ANCHOR Düzeltmesi:** "
            f"'{conflict.topic}' hakkında: "
            f"KB'ye göre {conflict.kb_fact}"
        )
        
        return Correction(
            conflict=conflict,
            original_text=text,
            corrected_text=text + note,
            edit_distance=0
        )
    
    def _patch(self, text: str, conflict: Conflict) -> Optional[Correction]:
        """
        ERROR: Hatalı kısmı düzelt, dipnot ekle.
        """
        note = (
            f"\n\n> 📝 **ANCHOR Notu:** "
            f"'{conflict.topic}': {conflict.kb_fact}"
        )
        
        return Correction(
            conflict=conflict,
            original_text=text,
            corrected_text=text + note,
            edit_distance=0
        )
    
    def _annotate(self, text: str, conflict: Conflict) -> Optional[Correction]:
        """
        WARNING: Sadece dipnot ekle (metni değiştirme).
        """
        note = (
            f"\n\n> 💡 **ANCHOR Ek Bilgi:** "
            f"'{conflict.topic}': {conflict.kb_fact}"
        )
        
        return Correction(
            conflict=conflict,
            original_text=text,
            corrected_text=text + note,
            edit_distance=0
        )
    
    def _extract_claim_keywords(self, claim: str) -> list[str]:
        """Claim'den önemli keyword'leri çıkar."""
        # Özel isimler, büyük harfli kelimeler, sayılar
        keywords = re.findall(r'\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]*(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]*)*\b', claim)
        keywords += re.findall(r'\b\d+\s*(?:nm|mm|cm|GHz|MHz|MB|GB|TB|W|V|A)\b', claim, re.IGNORECASE)
        return keywords
    
    def _replace_in_sentence(self, sentence: str, keyword: str, replacement: str) -> str:
        """Bir cümlede keyword ile ilgili kısmı replacement ile değiştir."""
        # Keyword'ün bulunduğu kısmı bul
        idx = sentence.lower().find(keyword.lower())
        if idx == -1:
            return sentence
        
        # Keyword'ü içeren tam ifadeyi bul (cümle parçası)
        start = max(0, sentence.rfind(' ', 0, idx))
        end = min(len(sentence), sentence.find(' ', idx + len(keyword)) if sentence.find(' ', idx + len(keyword)) > 0 else len(sentence))
        
        if start == end:
            return sentence
        
        phrase = sentence[start:end].strip().strip(',;')
        
        if phrase:
            new_sentence = sentence.replace(phrase, f"{phrase} [{replacement}]", 1)
            return new_sentence
        
        return sentence
    
    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
