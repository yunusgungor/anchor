"""
C5 Constraint Engine Testleri.

Test coverage:
  - FormatChecker: length, required, forbidden, regex
  - StyleChecker: tone, sentence length, repetition
  - StrategyChecker: CTA, content type, audience
  - ConstraintEngine: integration, auto-fix, report
"""

import pytest

from anchor.compliance import (
    ConstraintEngine,
    ConstraintViolation,
    ViolationSeverity,
    FixStrategy,
)


class TestFormatChecker:
    """Format checker testleri — deterministik."""
    
    def test_max_length_pass(self):
        """Max length ihlali yok."""
        engine = ConstraintEngine()
        constraints = {
            "format": {"max_length": 280}
        }
        text = "Kısa bir metin."
        violations = engine.check(text, constraints)
        assert len(violations) == 0
    
    def test_max_length_fail(self):
        """Max length ihlali — auto-fix truncate."""
        engine = ConstraintEngine()
        constraints = {
            "format": {"max_length": 10}
        }
        text = "Bu metin çok uzun."
        violations = engine.check(text, constraints)
        
        assert len(violations) == 1
        assert violations[0].constraint == "max_length"
        assert violations[0].severity == ViolationSeverity.ERROR
        assert violations[0].fix_strategy == FixStrategy.TRUNCATE
    
    def test_required_emoji_pass(self):
        """Emoji var — ihlal yok."""
        engine = ConstraintEngine()
        constraints = {
            "format": {"required_elements": ["emoji"]}
        }
        text = "Metin ✅"
        violations = engine.check(text, constraints)
        assert len(violations) == 0
    
    def test_required_emoji_fail(self):
        """Emoji eksik — auto-fix insert."""
        engine = ConstraintEngine()
        constraints = {
            "format": {"required_elements": ["emoji"]}
        }
        text = "Emoji yok"
        violations = engine.check(text, constraints)
        
        assert len(violations) == 1
        assert violations[0].constraint == "required_emoji"
        assert violations[0].fix_strategy == FixStrategy.INSERT
    
    def test_required_hashtag_fail(self):
        """Hashtag eksik — auto-fix append."""
        engine = ConstraintEngine()
        constraints = {
            "format": {"required_elements": ["hashtag"]}
        }
        text = "Hashtag yok"
        violations = engine.check(text, constraints)
        
        assert len(violations) == 1
        assert violations[0].constraint == "required_hashtag"
        assert violations[0].fix_strategy == FixStrategy.APPEND
    
    def test_forbidden_question(self):
        """Soru işareti yasak — auto-fix remove."""
        engine = ConstraintEngine()
        constraints = {
            "format": {"forbidden_elements": ["?"]}
        }
        text = "Bu bir soru mu?"
        violations = engine.check(text, constraints)
        
        assert len(violations) == 1
        assert violations[0].constraint == "forbidden_question"
        assert violations[0].fix_strategy == FixStrategy.REMOVE


class TestStyleChecker:
    """Style checker testleri — subjektif, skorlu."""
    
    def test_tone_humor_low(self):
        """Humor skoru düşük — WARNING."""
        engine = ConstraintEngine()
        constraints = {
            "style": {"tone": "humor"}
        }
        text = "Ciddi bir teknik metin."
        violations = engine.check(text, constraints)
        
        humor_violations = [v for v in violations if "humor" in v.constraint]
        assert len(humor_violations) >= 1
        assert humor_violations[0].severity == ViolationSeverity.WARNING
        assert humor_violations[0].score < 0.3
    
    def test_tone_humor_high(self):
        """Humor skoru yüksek — ihlal yok veya INFO."""
        engine = ConstraintEngine()
        constraints = {
            "style": {"tone": "humor"}
        }
        text = "Bu şaka gibi 😂 haha komik"
        violations = engine.check(text, constraints)
        
        # Skor yüksek olmalı, WARNING değil
        humor_violations = [v for v in violations if "humor" in v.constraint]
        for v in humor_violations:
            assert v.severity != ViolationSeverity.WARNING
    
    def test_confident_tone(self):
        """Confident tone tespiti."""
        engine = ConstraintEngine()
        constraints = {
            "style": {"tone": "confident"}
        }
        text = "Bu en iyi yöntem. Kesin dene!"
        violations = engine.check(text, constraints)
        
        # Confident kelimeleri var, skor yüksek olmalı
        conf_violations = [v for v in violations if "confident" in v.constraint]
        # Yüksek skor → WARNING değil
        for v in conf_violations:
            assert v.severity != ViolationSeverity.WARNING
    
    def test_max_sentence_length(self):
        """Uzun cümle tespiti."""
        engine = ConstraintEngine()
        constraints = {
            "style": {"max_sentence_length": 50}
        }
        text = "Bu çok uzun bir cümle ki burada anlatılmak istenen konu önemli detaylar içeriyor ve oldukça fazla karakter sayısına ulaşıyor."
        violations = engine.check(text, constraints)
        
        length_violations = [v for v in violations if "sentence_length" in v.constraint]
        assert len(length_violations) >= 1


class TestStrategyChecker:
    """Strategy checker testleri."""
    
    def test_cta_required_pass(self):
        """CTA var — ihlal yok."""
        engine = ConstraintEngine()
        constraints = {
            "strategy": {"cta_required": True}
        }
        text = "Yorum yap ve beğen!"
        violations = engine.check(text, constraints)
        
        cta_violations = [v for v in violations if "cta" in v.constraint]
        assert len(cta_violations) == 0
    
    def test_cta_required_fail(self):
        """CTA eksik — auto-fix append."""
        engine = ConstraintEngine()
        constraints = {
            "strategy": {
                "cta_required": True,
                "cta_template": "Yorum yap, beğen, kaydet!",
            }
        }
        text = "Sadece bilgi veren metin."
        violations = engine.check(text, constraints)
        
        cta_violations = [v for v in violations if "cta" in v.constraint]
        assert len(cta_violations) == 1
        assert cta_violations[0].fix_strategy == FixStrategy.APPEND
        assert "Yorum yap" in cta_violations[0].fix_suggestion
    
    def test_content_type_detect(self):
        """İçerik tipi tespiti."""
        engine = ConstraintEngine()
        constraints = {
            "strategy": {"content_type": "edutainment"}
        }
        text = "Nasıl yapılır? İşte ipucu!"
        violations = engine.check(text, constraints)
        
        # Edutainment keyword'leri var, uyumsuzluk olmamalı
        content_violations = [v for v in violations if "content_type" in v.constraint]
        for v in content_violations:
            assert v.severity == ViolationSeverity.INFO


class TestAutoFix:
    """Auto-fix integration testleri."""
    
    def test_auto_fix_truncate(self):
        """Uzun metni otomatik kısalt."""
        engine = ConstraintEngine()
        constraints = {
            "format": {"max_length": 20}
        }
        text = "Bu metin yirmi karakterden çok daha uzun."
        violations = engine.check(text, constraints)
        
        fixed, report = engine.apply_fixes(text, violations)
        assert len(fixed) <= 20
        assert report["auto_fixed_count"] == 1
    
    def test_auto_fix_emoji(self):
        """Emoji ekleme."""
        engine = ConstraintEngine()
        constraints = {
            "format": {"required_elements": ["emoji"]}
        }
        text = "Emoji yok"
        violations = engine.check(text, constraints)
        
        fixed, report = engine.apply_fixes(text, violations)
        assert "✅" in fixed
        assert report["auto_fixed_count"] == 1
    
    def test_auto_fix_cta(self):
        """CTA ekleme."""
        engine = ConstraintEngine()
        constraints = {
            "strategy": {
                "cta_required": True,
                "cta_template": "Yorum yap!",
            }
        }
        text = "Bilgi veren metin."
        violations = engine.check(text, constraints)
        
        fixed, report = engine.apply_fixes(text, violations)
        assert "Yorum yap" in fixed
        assert report["auto_fixed_count"] == 1
    
    def test_auto_fix_question(self):
        """Soru işareti kaldırma."""
        engine = ConstraintEngine()
        constraints = {
            "format": {"forbidden_elements": ["?"]}
        }
        text = "Bu bir soru mu?"
        violations = engine.check(text, constraints)
        
        fixed, report = engine.apply_fixes(text, violations)
        assert "?" not in fixed
        assert "!" in fixed  # Replace with !
        assert report["auto_fixed_count"] == 1
    
    def test_flag_only_style(self):
        """Style violation sadece flaglenmeli, auto-fix olmamalı."""
        engine = ConstraintEngine()
        constraints = {
            "style": {"tone": "humor"}
        }
        text = "Ciddi metin."
        violations = engine.check(text, constraints)
        
        fixed, report = engine.apply_fixes(text, violations)
        # Style fix NONE olduğu için metin değişmemeli
        assert fixed == text
        assert report["flagged_count"] >= 1
        assert report["auto_fixed_count"] == 0


class TestLoadConstraintsFromRule:
    """Rule içeriğinden constraint parse etme."""
    
    def test_parse_format_table(self):
        """Markdown table'dan format constraint parse."""
        engine = ConstraintEngine()
        rule_content = """
## Format Kuralları

| constraint | value | severity |
|---|---|---|
| max_length | 280 | ERROR |
| required_elements | [emoji, hashtag] | ERROR |
| forbidden_elements | [?] | CRITICAL |
"""
        constraints = engine.load_constraints_from_rule(rule_content)
        
        assert constraints["format"]["max_length"] == 280
        assert "emoji" in constraints["format"]["required_elements"]
        assert "?" in constraints["format"]["forbidden_elements"]
    
    def test_parse_strategy_table(self):
        """Markdown table'dan strategy constraint parse."""
        engine = ConstraintEngine()
        rule_content = """
## Strategy Kuralları

| constraint | value |
|---|---|
| cta_required | true |
| cta_template | Yorum yap! |
"""
        constraints = engine.load_constraints_from_rule(rule_content)
        
        assert constraints["strategy"]["cta_required"] is True
        assert constraints["strategy"]["cta_template"] == "Yorum yap!"


class TestEndToEnd:
    """End-to-end integration test."""
    
    def test_twitter_fenomen_compliance(self):
        """Twitter fenomeni senaryosu — full compliance check."""
        engine = ConstraintEngine()
        
        constraints = {
            "format": {
                "max_length": 280,
                "required_elements": ["emoji", "hashtag"],
                "forbidden_elements": ["?"],
            },
            "style": {
                "tone": "humor",
                "max_sentence_length": 100,
            },
            "strategy": {
                "cta_required": True,
                "cta_template": "Yorum yap, beğen, kaydet!",
            },
        }
        
        # LLM'in verdiği yanlış metin
        text = "Bugün size çok önemli bir konu anlatacağım. Bu konu hakkında ne düşünüyorsunuz?"
        
        violations = engine.check(text, constraints)
        
        # Olası ihlaller:
        # - Emoji yok → ERROR
        # - Hashtag yok → ERROR  
        # - Soru işareti → ERROR
        # - CTA yok → ERROR
        # - Humor düşük → WARNING
        
        assert len(violations) >= 4  # En az 4 ihlal
        
        # Auto-fix uygula
        fixed, report = engine.apply_fixes(text, violations)
        
        assert report["auto_fixed_count"] >= 3  # Format + strategy auto-fix
        assert report["flagged_count"] >= 1     # Style flag
        
        # Fixed text kontrolü
        assert "?" not in fixed       # Soru işareti kaldırıldı
        assert "✅" in fixed           # Emoji eklendi
        assert "#" in fixed            # Hashtag eklendi
        assert "Yorum yap" in fixed    # CTA eklendi
    
    def test_perfect_compliance(self):
        """Tüm kurallara uygun metin — sıfır ihlal."""
        engine = ConstraintEngine()
        
        constraints = {
            "format": {
                "max_length": 280,
                "required_elements": ["emoji"],
            },
            "style": {
                "tone": "humor",
            },
        }
        
        text = "En iyi ipucu 😂 Kesin dene! #tech #yazılım"
        
        violations = engine.check(text, constraints)
        
        # Humor skoru yüksek olmalı
        humor_violations = [v for v in violations if v.severity == ViolationSeverity.WARNING]
        assert len(humor_violations) == 0
