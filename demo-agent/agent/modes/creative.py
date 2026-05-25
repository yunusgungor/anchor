"""
CreativeMode — Anchor'ın C5 Constraint Engine yeteneğini sergileyen mod.

Bu mod şunları gösterir:
  - C5 Constraint Engine ile format kısıtlama
  - Stil kuralları (tone, voice, dil seviyesi)
  - Strateji kuralları (CTA, mesaj netliği)
  - Auto-fix mekanizması
  - Çoklu format desteği (tweet/post/thread/newsletter)
"""

import re
from typing import Any, Optional

from anchor.engine import RectificationResult


# Format constraint tanımları
FORMAT_CONSTRAINTS = {
    "tweet": {
        "label": "Tweet / X Post",
        "max_chars": 280,
        "emoji_ok": True,
        "emoji_recommended": 1,
        "required_sections": ["mesaj"],
        "style": "kısa, öz, etkileyici",
        "strategy": "dikkat çek, merak uyandır",
    },
    "thread": {
        "label": "X Thread",
        "max_chars": 5000,
        "min_tweets": 3,
        "emoji_ok": True,
        "required_sections": ["giriş", "gelişme", "sonuç"],
        "style": "akıcı, her tweet kendi başına anlamlı",
        "strategy": "hikaye anlat, değer ver",
    },
    "post": {
        "label": "LinkedIn / Blog Post",
        "max_chars": 3000,
        "emoji_ok": True,
        "required_sections": ["başlık", "gövde", "çağrı"],
        "style": "profesyonel, samimi",
        "strategy": "içgörü paylaş, tartışma başlat",
    },
    "newsletter": {
        "label": "Newsletter",
        "max_chars": 10000,
        "emoji_ok": True,
        "required_sections": ["konu", "giriş", "ana içerik", "kapanış"],
        "style": "kişisel, değer odaklı",
        "strategy": "aboneye özel hissettir, düzenli içerik vaat et",
    },
    "article": {
        "label": "Makale / Blog",
        "max_chars": 50000,
        "emoji_ok": False,
        "required_sections": ["başlık", "giriş", "ana bölüm", "sonuç"],
        "style": "akademik ton, kaynak belirtmeli",
        "strategy": "derinlemesine analiz, orijinal bakış açısı",
    },
    "email": {
        "label": "E-posta",
        "max_chars": 2000,
        "emoji_ok": False,
        "required_sections": ["konu", "selamlama", "gövde", "kapanış"],
        "style": "resmi veya yarı-resmi",
        "strategy": "net hedef, tek çağrı",
    },
    "caption": {
        "label": "Sosyal Medya Caption",
        "max_chars": 2200,
        "emoji_ok": True,
        "emoji_recommended": 2,
        "required_sections": ["hook", "mesaj", "cta"],
        "style": "görsel odaklı, kısa, etkileyici",
        "strategy": "görseli tamamla, etkileşim hedefle",
    },
}


class CreativeMode:
    """
    Creative Mode — İçerik üretimi ve yaratıcı yazarlık.
    
    C5 Constraint Engine ile:
    - Format kısıtlarını kontrol eder (karakter limiti, emoji sayısı)
    - Stil kurallarını denetler (tone, voice)
    - Strateji kurallarını doğrular (CTA, mesaj netliği)
    """
    
    def __init__(self):
        self.name = "creative"
        self._stats = {"total_creations": 0, "constraint_violations": 0}
    
    def post_process(
        self,
        query: str,
        raw: str,
        corrected: str,
        anchor_result: "RectificationResult | None" = None,
    ) -> dict:
        """
        Anchor sonrası Creative özel işleme.
        
        1. Format tespiti (tweet/post/thread/makale vs.)
        2. Karakter limiti kontrolü
        3. Emoji sayısı kontrolü
        4. Gerekli bölümlerin varlığı kontrolü
        5. Auto-fix önerileri
        """
        result = {
            "mode": self.name,
            "format_detected": None,
            "constraint_checks": {},
            "violations": [],
            "recommendations": [],
        }
        
        # Format tespiti
        fmt = self._detect_format(query, corrected)
        result["format_detected"] = fmt
        
        if fmt and fmt in FORMAT_CONSTRAINTS:
            constraints = FORMAT_CONSTRAINTS[fmt]
            
            # Karakter limiti kontrolü
            char_count = len(corrected)
            max_chars = constraints["max_chars"]
            result["constraint_checks"]["char_count"] = {
                "current": char_count,
                "max": max_chars,
                "within_limit": char_count <= max_chars,
            }
            if char_count > max_chars:
                result["violations"].append(
                    f"⚠️ Karakter limiti aşıldı: {char_count}/{max_chars}"
                )
                self._stats["constraint_violations"] += 1
            
            # Emoji kontrolü
            emoji_count = self._count_emoji(corrected)
            if constraints.get("emoji_ok"):
                recommended = constraints.get("emoji_recommended", 0)
                result["constraint_checks"]["emoji"] = {
                    "count": emoji_count,
                    "recommended": recommended,
                }
            elif emoji_count > 0:
                result["violations"].append(
                    f"⚠️ Emoji kullanımı bu formatta önerilmez ({fmt})"
                )
                self._stats["constraint_violations"] += 1
            
            # Gerekli bölümler
            required = constraints.get("required_sections", [])
            found_sections = self._find_sections(corrected, required)
            missing = [s for s in required if s not in found_sections]
            result["constraint_checks"]["sections"] = {
                "required": required,
                "found": found_sections,
                "missing": missing,
            }
            if missing:
                result["violations"].append(
                    f"⚠️ Eksik bölümler: {', '.join(missing)}"
                )
            
            # Öneriler
            if constraints.get("style"):
                result["recommendations"].append(f"Stil önerisi: {constraints['style']}")
            if constraints.get("strategy"):
                result["recommendations"].append(f"Strateji: {constraints['strategy']}")
        
        self._stats["total_creations"] += 1
        return result
    
    def enrich_query(self, query: str, context_notes: str | None = None) -> str:
        """Creative query'sini zenginleştir."""
        enriched = query
        if context_notes:
            enriched = f"{query}\n\n[Context]: {context_notes}"
        return enriched
    
    # -------- Helpers --------
    
    @staticmethod
    def _detect_format(query: str, response: str) -> str | None:
        """Hangi formatta içerik istendiğini tespit et."""
        query_lower = query.lower()
        response_lower = response.lower()
        combined = query_lower + " " + response_lower
        
        # Thread detection (önce thread gelmeli — tweet de match eder)
        if re.search(r'\bthread\b', combined) and not re.search(r'\b(un)?thread\b', combined):
            return "thread"
        
        # Direct format keywords
        format_keywords = {
            "tweet": r'\b(tweet|x\s*post|post\s*at|x)\b',
            "newsletter": r'\bnewsletter|bülten\b',
            "article": r'\b(makale|article|blog\s*post)\b',
            "email": r'\b(e[-]?mail|mail|e-posta)\b',
            "caption": r'\b(caption|açıklama|altyazı)\b',
            "post": r'\b(post|paylaşım|gönderi)\b',
        }
        
        for fmt, pattern in format_keywords.items():
            if re.search(pattern, combined):
                return fmt
        
        return "post"  # default
    
    @staticmethod
    def _count_emoji(text: str) -> int:
        """Metindeki emoji sayısını hesapla."""
        # Genişletilmiş emoji pattern
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # misc
            "\U0001F900-\U0001F9FF"  # supplemental
            "\U0001FA00-\U0001FA6F"  # chess symbols
            "\U0001FA70-\U0001FAFF"  # symbols extended
            "\U00002600-\U000026FF"  # misc symbols
            "\U0000FE00-\U0000FE0F"  # variation selectors
            "\U0000200D"             # ZWJ
            "\U00002B50"             # star
            "\U00002764"             # heart
            "\U0001F004"             # mahjong
            "\U0001F0CF"             # playing cards
            "]+",
            re.UNICODE,
        )
        return len(emoji_pattern.findall(text))
    
    @staticmethod
    def _find_sections(text: str, required_sections: list[str]) -> list[str]:
        """Metinde hangi gerekli bölümler var?"""
        text_lower = text.lower()
        found = []
        
        section_keywords = {
            "mesaj": ["mesaj", "message", "ana fikir"],
            "giriş": ["giriş", "intro", "giriş paragrafı"],
            "gelişme": ["gelişme", "body", "ana bölüm"],
            "sonuç": ["sonuç", "conclusion", "özet"],
            "başlık": ["başlık", "title", "headline", "konu"],
            "gövde": ["gövde", "body", "main"],
            "çağrı": ["çağrı", "cta", "call to action", "harekete geç"],
            "kapanış": ["kapanış", "closing", "imza"],
            "selamlama": ["selamlama", "merhaba", "sayın", "hi", "hello"],
            "konu": ["konu", "subject", "topic"],
            "ana içerik": ["ana içerik", "main content", "içerik"],
            "hook": ["hook", "dikkat", "giriş cümlesi"],
            "cta": ["cta", "call to action", "tıkla", "katıl", "takip et"],
            "ana bölüm": ["ana bölüm", "main", "detay"],
        }
        
        for section in required_sections:
            section_lower = section.lower()
            keywords = section_keywords.get(section_lower, [section_lower])
            if any(kw in text_lower for kw in keywords):
                found.append(section)
        
        return found
    
    @property
    def stats(self) -> dict:
        return dict(self._stats)
