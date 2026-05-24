"""
C5: Constraint Engine — Creative Compliance Layer.

Her türlü kuralı (format, style, strategy) LLM çıktısına uygular.
Deterministik auto-fix + flag + suggest.

Mimari:
  ┌─────────────────────────────────────────────────────────────┐
  │  ConstraintEngine                                           │
  ├─────────────────────────────────────────────────────────────┤
  │  • FormatChecker    — length, regex, structure              │
  │  • StyleChecker     — lexicon, pattern, tone                │
  │  • StrategyChecker  — CTA, audience, content type          │
  ├─────────────────────────────────────────────────────────────┤
  │  Auto-Fix: Deterministik → otomatik düzelt                 │
  │  Flag:     Subjektif → rapor et, öneri sun                   │
  └─────────────────────────────────────────────────────────────┘
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional
import re


class ViolationSeverity(Enum):
    """Kural ihlali şiddeti."""
    INFO = auto()      # Bilgi — rapor et
    WARNING = auto()   # Uyarı — öneri sun
    ERROR = auto()     # Hata — auto-fix yap
    CRITICAL = auto()  # Kritik — auto-fix, kullanıcıya bildir


class FixStrategy(Enum):
    """Düzeltme stratejisi."""
    NONE = auto()          # Sadece flag — elle düzelt
    TRUNCATE = auto()      # Uzunluğu kısalt
    INSERT = auto()        # Eksik element ekle
    REMOVE = auto()        # Yasak element sil
    APPEND = auto()        # Sonuna ekle (CTA vb.)
    REPLACE = auto()       # Değiştir


@dataclass
class ConstraintViolation:
    """Tek bir kural ihlali."""
    rule_type: str           # "format", "style", "strategy"
    constraint: str          # "max_length", "tone_humor", "cta_required"
    severity: ViolationSeverity
    message: str             # İnsan-okunabilir açıklama
    fix_strategy: FixStrategy
    fix_suggestion: str      # Auto-fix metni veya öneri
    position: Optional[tuple] = None  # (start, end) metin içinde
    score: float = 0.0       # 0-1, subjektif kurallar için


# ==================== FORMAT CHECKER ====================

class FormatChecker:
    """
    Deterministik format kontrolleri.
    Her şey kesin (regex, length, count) → auto-fix yapılabilir.
    """
    
    def check(self, text: str, constraints: dict) -> list[ConstraintViolation]:
        """Format constraint'lerini kontrol et."""
        violations = []
        
        # 1. Length constraints
        if "max_length" in constraints:
            max_len = constraints["max_length"]
            if len(text) > max_len:
                violations.append(ConstraintViolation(
                    rule_type="format",
                    constraint="max_length",
                    severity=ViolationSeverity.ERROR,
                    message=f"Metin {len(text)} karakter, max {max_len}",
                    fix_strategy=FixStrategy.TRUNCATE,
                    fix_suggestion=text[:max_len],
                ))
        
        if "min_length" in constraints:
            min_len = constraints["min_length"]
            if len(text) < min_len:
                violations.append(ConstraintViolation(
                    rule_type="format",
                    constraint="min_length",
                    severity=ViolationSeverity.WARNING,
                    message=f"Metin {len(text)} karakter, min {min_len}",
                    fix_strategy=FixStrategy.NONE,
                    fix_suggestion=f"En az {min_len} karakter yazın",
                ))
        
        # 2. Required elements
        if "required_elements" in constraints:
            for elem in constraints["required_elements"]:
                if elem == "emoji":
                    if not self._has_emoji(text):
                        violations.append(ConstraintViolation(
                            rule_type="format",
                            constraint="required_emoji",
                            severity=ViolationSeverity.ERROR,
                            message="Emoji eksik",
                            fix_strategy=FixStrategy.INSERT,
                            fix_suggestion="✅",
                        ))
                elif elem == "hashtag":
                    if not self._has_hashtag(text):
                        violations.append(ConstraintViolation(
                            rule_type="format",
                            constraint="required_hashtag",
                            severity=ViolationSeverity.ERROR,
                            message="Hashtag eksik",
                            fix_strategy=FixStrategy.APPEND,
                            fix_suggestion="#topic",
                        ))
        
        # 3. Forbidden elements
        if "forbidden_elements" in constraints:
            for elem in constraints["forbidden_elements"]:
                if elem == "soru işareti" or elem == "?":
                    if "?" in text:
                        violations.append(ConstraintViolation(
                            rule_type="format",
                            constraint="forbidden_question",
                            severity=ViolationSeverity.ERROR,
                            message="Soru işareti yasak",
                            fix_strategy=FixStrategy.REMOVE,
                            fix_suggestion=text.replace("?", "!"),
                        ))
                elif elem == "küfür":
                    # Türkçe + İngilizce küfür tespiti
                    bad_words = [
                        # Türkçe
                        "amk", "aq", "siktir", "sikik", "orospu", "piç", "göt", 
                        "yarrak", "ibne", "pezevenk", "ananı", "babanı",
                        "mal", "gerizekalı", "salak", "aptal", "embesil",
                        # İngilizce
                        "fuck", "shit", "asshole", "bastard", "bitch",
                        "motherfucker", "dickhead", "cocksucker",
                    ]
                    for bad in bad_words:
                        if bad in text.lower():
                            violations.append(ConstraintViolation(
                                rule_type="format",
                                constraint="forbidden_swearing",
                                severity=ViolationSeverity.CRITICAL,
                                message=f"Yasak kelime: {bad}",
                                fix_strategy=FixStrategy.REMOVE,
                                fix_suggestion="[SILINDI]",
                            ))
        
        # 4. Regex pattern
        if "regex_pattern" in constraints:
            pattern = constraints["regex_pattern"]
            if not re.search(pattern, text):
                violations.append(ConstraintViolation(
                    rule_type="format",
                    constraint="regex_pattern",
                    severity=ViolationSeverity.ERROR,
                    message=f"Regex pattern eşleşmedi: {pattern}",
                    fix_strategy=FixStrategy.NONE,
                    fix_suggestion="Pattern'i kontrol edin",
                ))
        
        return violations
    
    def _has_emoji(self, text: str) -> bool:
        """Metinde emoji var mı?"""
        # Basit emoji tespiti — Unicode emoji range'leri
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        return bool(emoji_pattern.search(text))
    
    def _has_hashtag(self, text: str) -> bool:
        """Metinde hashtag var mı?"""
        return bool(re.search(r"#\w+", text))


# ==================== STYLE CHECKER ====================

class StyleChecker:
    """
    Üslup kontrolleri — subjektif, ama ölçülebilir.
    Tespit eder, flagler, öneri sunar. Auto-fix yapmaz (creativity gerekir).
    """
    
    LEXICONS = {
        "humor": ["😂", "🤣", "😄", "😅", "haha", "hehe", "şaka", "ironik", "komik", 
                  "gül", "kahkaha", "mizah", "espiri", "eğlenceli", "absürt", "grotesk",
                  "parodi", "karikatür", "gırgır", "dalga geç", "espri", "komedi"],
        "confident": ["kesin", "en iyi", "dene", "mutlaka", "garanti", "hallederiz", 
                      "başarırız", "emin", "şüphesiz", "tartışmasız", "net", "açık",
                      "kesinlikle", "tabii ki", "elbette", "kuşkusuz", "muhakkak"],
        "casual": ["ya", "falan", "işte", "bi", "bişey", "neyse", "hani", "yani",
                   "bence", "şey", "yok artık", "oha", "valla", "baya", "çok", "süper"],
        "formal": ["saygılarımla", "hususi", "münhasır", "bilhassa", "özellikle",
                   "rica ederim", "teşekkür ederim", "arz ederim", "bilgilerinize",
                   "saygıdeğer", "kıymetli", "değerli", "hitaben", "takdim"],
        "urgent": ["hemen", "acele", "son tarih", "bitmedi", "erteleme", "acil",
                   "önemli", "kritik", "ivedi", "derhal", "zaman daralıyor",
                   "son gün", "kaçırma", "fırsat", "sınırlı"],
        "analytical": ["veri", "analiz", "rapor", "istatistik", "sonuç", "bulgu",
                       "inceleme", "değerlendirme", "parametre", "metrik", "ölçüm",
                       "korelasyon", "tahmin", "projeksiyon", "trend", "grafik"],
        "empathetic": ["anlıyorum", "hissediyorum", "üzgünüm", "geçmiş olsun",
                       "tebrik ederim", "sevindim", "başın sağolsun", "yanındayım",
                       "destek", "anlayış", "empati", "duyarlı"],
    }
    
    def check(self, text: str, constraints: dict) -> list[ConstraintViolation]:
        """Style constraint'lerini kontrol et."""
        violations = []
        
        # 1. Tone check — lexicon matching
        if "tone" in constraints:
            expected_tone = constraints["tone"]
            score = self._tone_score(text, expected_tone)
            
            if score < 0.3:
                violations.append(ConstraintViolation(
                    rule_type="style",
                    constraint=f"tone_{expected_tone}",
                    severity=ViolationSeverity.WARNING,
                    message=f"Ton '{expected_tone}' çok düşük (skor: {score:.2f})",
                    fix_strategy=FixStrategy.NONE,
                    fix_suggestion=f"'{expected_tone}' lexicon'undan kelimeler ekle: {self.LEXICONS.get(expected_tone, [])[:5]}",
                    score=score,
                ))
            elif score < 0.6:
                violations.append(ConstraintViolation(
                    rule_type="style",
                    constraint=f"tone_{expected_tone}",
                    severity=ViolationSeverity.INFO,
                    message=f"Ton '{expected_tone}' orta (skor: {score:.2f})",
                    fix_strategy=FixStrategy.NONE,
                    fix_suggestion=f"Daha fazla '{expected_tone}' kelimesi eklenebilir",
                    score=score,
                ))
        
        # 2. Sentence length check
        if "max_sentence_length" in constraints:
            max_len = constraints["max_sentence_length"]
            sentences = re.split(r'[.!?\n]+', text)
            for sent in sentences:
                sent = sent.strip()
                if len(sent) > max_len:
                    violations.append(ConstraintViolation(
                        rule_type="style",
                        constraint="max_sentence_length",
                        severity=ViolationSeverity.WARNING,
                        message=f"Cümle {len(sent)} karakter, max {max_len}",
                        fix_strategy=FixStrategy.NONE,
                        fix_suggestion="Cümleyi iki parçaya bölün",
                    ))
        
        # 3. Repetition check
        if "max_repetition" in constraints:
            words = text.lower().split()
            word_counts = {}
            for w in words:
                word_counts[w] = word_counts.get(w, 0) + 1
            
            for word, count in word_counts.items():
                if count > constraints["max_repetition"] and len(word) > 3:
                    violations.append(ConstraintViolation(
                        rule_type="style",
                        constraint="max_repetition",
                        severity=ViolationSeverity.INFO,
                        message=f"'{word}' {count} kez tekrarlandı",
                        fix_strategy=FixStrategy.NONE,
                        fix_suggestion=f"'{word}' yerine eş anlamlı kelimeler kullanın",
                    ))
        
        return violations
    
    def _tone_score(self, text: str, tone: str) -> float:
        """Metnin belirli bir ton'a uygunluk skoru (0-1)."""
        lexicon = self.LEXICONS.get(tone, [])
        if not lexicon:
            return 0.5  # Bilinmeyen ton → nötr
        
        text_lower = text.lower()
        matches = sum(1 for word in lexicon if word.lower() in text_lower)
        
        # Normalize: 0-5 matches → 0-1
        score = min(matches / 3, 1.0)
        return round(score, 2)


# ==================== STRATEGY CHECKER ====================

class StrategyChecker:
    """
    Strateji kontrolleri — content-level, deterministik.
    CTA, audience, content type.
    """
    
    def check(self, text: str, constraints: dict) -> list[ConstraintViolation]:
        """Strategy constraint'lerini kontrol et."""
        violations = []
        
        # 1. CTA required
        if constraints.get("cta_required", False):
            if not self._has_cta(text):
                cta_template = constraints.get("cta_template", "Yorum yap, beğen, kaydet!")
                violations.append(ConstraintViolation(
                    rule_type="strategy",
                    constraint="cta_required",
                    severity=ViolationSeverity.ERROR,
                    message="CTA (Call-to-Action) eksik",
                    fix_strategy=FixStrategy.APPEND,
                    fix_suggestion=cta_template,
                ))
        
        # 2. Content type
        if "content_type" in constraints:
            expected = constraints["content_type"]
            detected = self._detect_content_type(text)
            if detected != expected:
                violations.append(ConstraintViolation(
                    rule_type="strategy",
                    constraint="content_type",
                    severity=ViolationSeverity.INFO,
                    message=f"İçerik tipi '{detected}', beklenen '{expected}'",
                    fix_strategy=FixStrategy.NONE,
                    fix_suggestion=f"Daha fazla '{expected}' elementleri ekleyin",
                ))
        
        # 3. Target audience keywords
        if "target_audience" in constraints:
            audience = constraints["target_audience"]
            score = self._audience_score(text, audience)
            if score < 0.3:
                violations.append(ConstraintViolation(
                    rule_type="strategy",
                    constraint="target_audience",
                    severity=ViolationSeverity.WARNING,
                    message=f"Hedef kitle '{audience}' ile uyumsuzluk (skor: {score:.2f})",
                    fix_strategy=FixStrategy.NONE,
                    fix_suggestion=f"'{audience}' jargon'u kullanın",
                ))
        
        return violations
    
    def _has_cta(self, text: str) -> bool:
        """Metinde CTA var mı?"""
        cta_patterns = [
            r"\byorum\b", r"\bbeğen\b", r"\bkaydet\b",
            r"\btakip\b", r"\bpaylaş\b", r"\babone\b",
            r"\bdm\b", r"\biletişim\b", r"\blink\b",
            r"\bbio\b", r"\byorumlara\b",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in cta_patterns)
    
    def _detect_content_type(self, text: str) -> str:
        """Basit içerik tipi tespiti."""
        scores = {
            "edutainment": len(re.findall(r"\b(öğren|bilgi|ipucu|teknik|nasıl|neden)\b", text, re.I)),
            "promotional": len(re.findall(r"\b(indirim|fiyat|satın al|sipariş|kampanya)\b", text, re.I)),
            "entertainment": len(re.findall(r"\b(eğlence|komik|gül|mizah|şaka)\b", text, re.I)),
            "news": len(re.findall(r"\b(haber|son dakika|gelişme|açıkladı|duyurdu)\b", text, re.I)),
        }
        return max(scores, key=scores.get) if scores else "unknown"
    
    def _audience_score(self, text: str, audience: str) -> float:
        """Hedef kitle uygunluk skoru."""
        audience_keywords = {
            "25-35 tech çalışanı": ["startup", "yazılım", "kod", "developer", "tech", "ai", "yapay zeka"],
            "genç": ["okul", "ders", "sınav", "genç", "trend", "tiktok"],
            "profesyonel": ["kariyer", "iş", "proje", "müşteri", "rapor", "toplantı"],
        }
        
        keywords = audience_keywords.get(audience, [])
        if not keywords:
            return 0.5
        
        text_lower = text.lower()
        matches = sum(1 for kw in keywords if kw in text_lower)
        return round(min(matches / 2, 1.0), 2)


# ==================== MAIN ENGINE ====================

class ConstraintEngine:
    """
    C5: Constraint Engine — Tüm checker'ları koordine eder.
    
    Kullanım:
        engine = ConstraintEngine()
        
        # Rules'dan constraint'leri yükle
        constraints = engine.load_constraints(rule_file)
        
        # Kontrol et
        violations = engine.check(text, constraints)
        
        # Auto-fix
        fixed_text, report = engine.apply_fixes(text, violations)
    """
    
    def __init__(self):
        self.format_checker = FormatChecker()
        self.style_checker = StyleChecker()
        self.strategy_checker = StrategyChecker()
    
    def check(self, text: str, constraints: dict) -> list[ConstraintViolation]:
        """Tüm constraint'leri kontrol et."""
        violations = []
        
        # Format
        if "format" in constraints:
            violations.extend(
                self.format_checker.check(text, constraints["format"])
            )
        
        # Style
        if "style" in constraints:
            violations.extend(
                self.style_checker.check(text, constraints["style"])
            )
        
        # Strategy
        if "strategy" in constraints:
            violations.extend(
                self.strategy_checker.check(text, constraints["strategy"])
            )
        
        # Severity sırala: CRITICAL → ERROR → WARNING → INFO
        severity_order = {
            ViolationSeverity.CRITICAL: 0,
            ViolationSeverity.ERROR: 1,
            ViolationSeverity.WARNING: 2,
            ViolationSeverity.INFO: 3,
        }
        violations.sort(key=lambda v: severity_order[v.severity])
        
        return violations
    
    def apply_fixes(self, text: str, violations: list[ConstraintViolation]) -> tuple[str, dict]:
        """
        Deterministik violation'ları auto-fix et.
        Subjektif olanları raporla.
        
        Returns:
            (fixed_text, report)
        """
        fixed = text
        auto_fixed = []
        flagged = []
        
        for v in violations:
            if v.fix_strategy == FixStrategy.TRUNCATE:
                # max_length truncate
                if v.constraint == "max_length":
                    fixed = v.fix_suggestion  # Zaten kısaltılmış
                    auto_fixed.append(v)
            
            elif v.fix_strategy == FixStrategy.INSERT:
                # Eksik element ekle
                if "emoji" in v.constraint:
                    fixed = fixed + " " + v.fix_suggestion
                    auto_fixed.append(v)
            
            elif v.fix_strategy == FixStrategy.APPEND:
                # Sonuna ekle
                fixed = fixed + "\n\n" + v.fix_suggestion
                auto_fixed.append(v)
            
            elif v.fix_strategy == FixStrategy.REMOVE:
                # Yasak element sil
                if "question" in v.constraint:
                    fixed = fixed.replace("?", "!")
                    auto_fixed.append(v)
            
            elif v.fix_strategy == FixStrategy.REPLACE:
                fixed = fixed.replace(v.position[0] if v.position else "", v.fix_suggestion)
                auto_fixed.append(v)
            
            elif v.fix_strategy == FixStrategy.NONE:
                # Subjektif — flagle
                flagged.append(v)
        
        report = {
            "auto_fixed_count": len(auto_fixed),
            "flagged_count": len(flagged),
            "auto_fixed": [
                {"constraint": v.constraint, "message": v.message}
                for v in auto_fixed
            ],
            "flagged": [
                {"constraint": v.constraint, "message": v.message, "suggestion": v.fix_suggestion}
                for v in flagged
            ],
        }
        
        return fixed, report
    
    def load_constraints_from_rule(self, rule_content: str) -> dict:
        """
        Rule içeriğinden constraint'leri parse et.
        Markdown table formatını destekler.
        """
        constraints = {"format": {}, "style": {}, "strategy": {}}
        
        lines = rule_content.split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Section tespiti
            if "## Format" in line or "## 🎨 Format" in line:
                current_section = "format"
                continue
            elif "## Style" in line or "## 🎭 Üslup" in line:
                current_section = "style"
                continue
            elif "## Strategy" in line or "## 🎯 Strateji" in line:
                current_section = "strategy"
                continue
            
            # Table row parse (| key | value | severity |)
            if line.startswith("|") and current_section:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2 and parts[0] not in ("constraint", "value", "Kural"):
                    key = parts[0]
                    val = parts[1]
                    
                    # Değer tipi convert
                    if val.isdigit():
                        val = int(val)
                    elif val.replace(".", "").isdigit():
                        val = float(val)
                    elif val.startswith("[") and val.endswith("]"):
                        val = [v.strip().strip("'\"") for v in val[1:-1].split(",")]
                    elif val.lower() in ("true", "evet"):
                        val = True
                    elif val.lower() in ("false", "hayır"):
                        val = False
                    
                    constraints[current_section][key] = val
        
        return constraints
