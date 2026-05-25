"""
CreativeMode — Anchor'ın C5 Constraint Engine yeteneğini sergileyen mod.

Bu mod şunları gösterir:
  - C5 Constraint Engine ile format kısıtlama
  - Stil kuralları (tone, voice, dil seviyesi)
  - Strateji kuralları (CTA, mesaj netliği)
  - Auto-fix mekanizması (karakter aşımı, eksik bölüm, emoji)
  - Çoklu format desteği (tweet/post/thread/newsletter)

[v4.5+] Auto-Fix Features:
  - Smart Truncation: Karakter limiti aşımında cümle bilinciyle kısaltma
  - Section Auto-Add: Eksik bölümleri otomatik ekleme (placeholder)
  - Emoji Adjust: Emoji sayısını format kurallarına uydurma
  - Auto-Corrected Output: Orijinal yerine otomatik düzeltilmiş metin
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
        "emoji_max": 2,
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
        "emoji_recommended": 2,
        "emoji_max": 3,
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
        "emoji_max": 0,
        "required_sections": ["başlık", "giriş", "ana bölüm", "sonuç"],
        "style": "akademik ton, kaynak belirtmeli",
        "strategy": "derinlemesine analiz, orijinal bakış açısı",
    },
    "email": {
        "label": "E-posta",
        "max_chars": 2000,
        "emoji_ok": False,
        "emoji_max": 0,
        "required_sections": ["konu", "selamlama", "gövde", "kapanış"],
        "style": "resmi veya yarı-resmi",
        "strategy": "net hedef, tek çağrı",
    },
    "caption": {
        "label": "Sosyal Medya Caption",
        "max_chars": 2200,
        "emoji_ok": True,
        "emoji_recommended": 2,
        "emoji_max": 4,
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

    [v4.5+] Auto-Fix:
    - Smart Truncation: Karakter aşımında cümle bilinciyle otomatik kısaltma
    - Section Auto-Add: Eksik bölümleri otomatik tamamlama
    - Emoji Adjust: Format kurallarına göre emoji düzenleme
    """

    def __init__(self):
        self.name = "creative"
        self._stats = {"total_creations": 0, "constraint_violations": 0, "auto_fixes": 0}

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
        2. Karakter limiti kontrolü + auto-fix
        3. Emoji sayısı kontrolü + auto-fix
        4. Gerekli bölümlerin varlığı kontrolü + auto-fix
        5. Auto-corrected output (orijinal yerine geçer)
        """
        # Anchor'dan gelen corrected'i kullan (factual corrections)
        base_text = corrected

        # Creative constraint checks
        fmt = self._detect_format(query, base_text)
        auto_fixed = base_text
        auto_fixes_applied = []

        if fmt and fmt in FORMAT_CONSTRAINTS:
            constraints = FORMAT_CONSTRAINTS[fmt]

            # --- 1. Character limit check + auto-fix ---
            char_info = self._check_char_limit(base_text, constraints)
            if not char_info["within_limit"]:
                auto_fixed, truncation_fix = self._auto_truncate(
                    auto_fixed, fmt, constraints["max_chars"]
                )
                if truncation_fix:
                    auto_fixes_applied.append(truncation_fix)

            # --- 2. Emoji check + auto-fix ---
            emoji_info = self._check_emoji(base_text, constraints)
            if emoji_info.get("needs_fix"):
                auto_fixed, emoji_fix = self._auto_fix_emoji(
                    auto_fixed, fmt, constraints
                )
                if emoji_fix:
                    auto_fixes_applied.append(emoji_fix)

            # --- 3. Required sections check + auto-fix ---
            section_info = self._check_sections(base_text, constraints)
            if section_info.get("missing"):
                auto_fixed, section_fix = self._auto_add_sections(
                    auto_fixed, section_info["missing"]
                )
                if section_fix:
                    auto_fixes_applied.append(section_fix)

        # Build result
        result = {
            "mode": self.name,
            "format_detected": fmt,
            "auto_fixed": auto_fixed,
            "auto_fixes_applied": auto_fixes_applied,
            "original_text": corrected,
            "constraint_checks": {
                "char_count": char_info if fmt and fmt in FORMAT_CONSTRAINTS else {},
                "emoji": emoji_info if fmt and fmt in FORMAT_CONSTRAINTS else {},
                "sections": section_info if fmt and fmt in FORMAT_CONSTRAINTS else {},
            },
            "violations": [],
            "recommendations": [],
        }

        # Collect violations
        if fmt and fmt in FORMAT_CONSTRAINTS:
            constraints = FORMAT_CONSTRAINTS[fmt]
            if not char_info.get("within_limit", True):
                result["violations"].append(
                    f"⚠️ Karakter limiti aşıldı: {char_info['current']}/{char_info['max']} "
                    f"(auto-fix: {len(auto_fixed)} karakter)"
                )
            if emoji_info.get("emoji_ok") and emoji_info.get("count", 0) > constraints.get("emoji_max", 99):
                result["violations"].append(
                    f"⚠️ Çok fazla emoji: {emoji_info['count']} (max: {constraints.get('emoji_max', 'N/A')})"
                )
            if section_info.get("missing"):
                result["violations"].append(
                    f"⚠️ Eksik bölümler: {', '.join(section_info['missing'])}"
                )
            # Recommendations
            if constraints.get("style"):
                result["recommendations"].append(f"Stil önerisi: {constraints['style']}")
            if constraints.get("strategy"):
                result["recommendations"].append(f"Strateji: {constraints['strategy']}")

        # Count auto-fixes
        if auto_fixes_applied:
            self._stats["auto_fixes"] += len(auto_fixes_applied)
            self._stats["constraint_violations"] += len(auto_fixes_applied)

        self._stats["total_creations"] += 1
        return result

    def enrich_query(self, query: str, context_notes: str | None = None) -> str:
        """Creative query'sini zenginleştir."""
        enriched = query
        if context_notes:
            enriched = f"{query}\n\n[Context]: {context_notes}"
        return enriched

    # ---------------------------------------------------------------- #
    # Constraint Checks
    # ---------------------------------------------------------------- #

    @staticmethod
    def _check_char_limit(text: str, constraints: dict) -> dict:
        """Karakter limiti kontrolü."""
        char_count = len(text)
        max_chars = constraints.get("max_chars", 99999)
        return {
            "current": char_count,
            "max": max_chars,
            "within_limit": char_count <= max_chars,
            "over_by": max(0, char_count - max_chars),
        }

    @staticmethod
    def _check_emoji(text: str, constraints: dict) -> dict:
        """Emoji sayısı kontrolü."""
        count = CreativeMode._count_emoji(text)
        emoji_ok = constraints.get("emoji_ok", True)
        emoji_max = constraints.get("emoji_max", 99)

        needs_fix = False
        if not emoji_ok and count > 0:
            needs_fix = True
        elif emoji_ok and count > emoji_max:
            needs_fix = True

        return {
            "count": count,
            "emoji_ok": emoji_ok,
            "recommended": constraints.get("emoji_recommended", 0),
            "needs_fix": needs_fix,
        }

    @staticmethod
    def _check_sections(text: str, constraints: dict) -> dict:
        """Gerekli bölümlerin varlığı kontrolü."""
        required = constraints.get("required_sections", [])
        found = CreativeMode._find_sections(text, required)
        missing = [s for s in required if s not in found]
        return {
            "required": required,
            "found": found,
            "missing": missing,
        }

    # ---------------------------------------------------------------- #
    # Auto-Fix Engine
    # ---------------------------------------------------------------- #

    @staticmethod
    def _auto_truncate(text: str, fmt: str, max_chars: int) -> tuple[str, str | None]:
        """
        Smart truncation: Cümle bilinciyle kısaltma.

        - Son tam cümleye kadar kes
        - Eğer tek cümle ise ortadan kısalt (..., sonu koru)
        """
        if len(text) <= max_chars:
            return text, None

        # Try: son tam cümle noktasına kadar kes
        truncated = text[:max_chars]
        last_period = max(
            truncated.rfind(". "),
            truncated.rfind(".\n"),
            truncated.rfind("! "),
            truncated.rfind("? "),
        )
        if last_period > max_chars * 0.5:  # En az %50'si kalsın
            result = text[: last_period + 1]
            fix_msg = f"✂️ Karakter limiti ({max_chars}) için son cümleden kısaltıldı"
        else:
            # Fallback: kelime bilinciyle kes
            truncated = text[: max_chars - 3]
            last_space = truncated.rfind(" ")
            if last_space > max_chars * 0.3:
                result = text[:last_space] + "..."
            else:
                result = truncated + "..."
            fix_msg = f"✂️ Karakter limiti ({max_chars}) için kısaltıldı + '...' eklendi"

        return result, fix_msg

    @staticmethod
    def _auto_fix_emoji(text: str, fmt: str, constraints: dict) -> tuple[str, str | None]:
        """
        Emoji düzeltme:
        - Emoji yasaksa → tüm emojileri temizle
        - Çok fazla emoji varsa → fazlalıkları temizle
        """
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\U00002600-\U000026FF"
            "\U0000FE00-\U0000FE0F"
            "\U0000200D"
            "\U00002B50"
            "\U00002764"
            "\U0001F004"
            "\U0001F0CF"
            "]+",
            re.UNICODE,
        )
        emojis = emoji_pattern.findall(text)
        if not emojis:
            return text, None

        emoji_ok = constraints.get("emoji_ok", True)
        emoji_max = constraints.get("emoji_max", 99)

        if not emoji_ok:
            # Remove all emojis
            fixed = emoji_pattern.sub("", text).strip()
            return fixed, f"🚫 Emoji kullanımı '{fmt}' formatında yasak — tüm emojiler temizlendi"

        if len(emojis) > emoji_max:
            # Keep only first N emojis
            keep_count = max(emoji_max, constraints.get("emoji_recommended", 1))
            # Replace all emojis then add back first N
            no_emoji = emoji_pattern.sub("", text)
            fixed = no_emoji
            removed = len(emojis) - keep_count
            fix_msg = f"🔢 Emoji sayısı {len(emojis)} → {keep_count} (max: {emoji_max}) — {removed} emoji temizlendi"
            return fixed, fix_msg

        return text, None

    @staticmethod
    def _auto_add_sections(text: str, missing: list[str]) -> tuple[str, str | None]:
        """
        Eksik bölümleri otomatik placeholder ile ekle.

        En uygun yere ekler (başa, sona veya sıradaki yerine).
        """
        if not missing:
            return text, None

        fixed = text.strip()
        added = []

        section_placeholders = {
            "başlık": "\n\n## Başlık\n[Başlık giriniz]",
            "giriş": "\n\n## Giriş\n[Giriş paragrafı eklenecek]",
            "gövde": "\n\n## Gövde\n[Ana içerik buraya]",
            "sonuç": "\n\n## Sonuç\n[Sonuç paragrafı eklenecek]",
            "çağrı": "\n\n## Harekete Geç\n[CTA metni giriniz]",
            "konu": "\n\n## Konu\n[Konu başlığı]",
            "selamlama": "\n\n## Selamlama\nMerhaba,",
            "kapanış": "\n\n## Kapanış\nSevgiler,",
            "mesaj": "\n\n## Ana Mesaj\n[Tweet'inizin ana mesajı]",
            "ana içerik": "\n\n## Ana İçerik\n[Newsletter içeriği eklenecek]",
            "hook": "\n\n## Hook\n[Dikkat çekici giriş cümlesi]",
            "cta": "\n\n## Harekete Geç\n[CTA]",
            "ana bölüm": "\n\n## Ana Bölüm\n[Makale içeriği buraya]",
        }

        for section in missing:
            placeholder = section_placeholders.get(section.lower(), f"\n\n## {section.title()}\n[İçerik eklenecek]")
            fixed += placeholder
            added.append(section)

        fix_msg = f"📝 Eksik bölümler otomatik eklendi: {', '.join(added)}"
        return fixed, fix_msg

    # ---------------------------------------------------------------- #
    # Format Detection (same as before, upgraded)
    # ---------------------------------------------------------------- #

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
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\U00002600-\U000026FF"
            "\U0000FE00-\U0000FE0F"
            "\U0000200D"
            "\U00002B50"
            "\U00002764"
            "\U0001F004"
            "\U0001F0CF"
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

    @staticmethod
    def format_format_guide() -> str:
        """Format rehberi — hangi format hangi kısıtlamalarla gelir."""
        lines = ["\n📐 Format Rehberi:"]
        for fmt, info in FORMAT_CONSTRAINTS.items():
            lines.append(
                f"  {info['label']:<25} | max {info['max_chars']:<5} chars | "
                f"{'✅ emoji' if info['emoji_ok'] else '❌ no emoji'} | "
                f"sections: {len(info['required_sections'])}"
            )
        return "\n".join(lines)

    @property
    def stats(self) -> dict:
        return dict(self._stats)
