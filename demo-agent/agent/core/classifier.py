"""
TaskClassifier — Deterministic query routing for Anchor Agent.

Üç mod arasında routing yapar:
  1. factcheck  → Varsayılan. Doğruluk kontrolü, tutarlılık, fikir muhalefeti
  2. workflow   → Adım-adım iş akışı, süreç, tutorial
  3. creative   → İçerik üretimi, yaratıcı yazarlık, sosyal medya

Felsefe: Deterministic öncelikli, LLM sadece son çare.

[v4.5+] Improvements:
  - Genişletilmiş Türkçe pattern desteği
  - Multi-token workflow detection (örn: "bana adım adım anlat")
  - Ambiguity score: %100 deterministik karar için güven skoru
  - LLM fallback: Hiçbir pattern eşleşmezse veya ambiguity yüksekse LLM
"""

import re

MODE_REGISTRY = {
    "factcheck": {
        "name": "FactCheck",
        "emoji": "🔍",
        "tagline": "Gerçeklerin peşinde, hatasız iletişim",
        "description": "Anchor A1-A4 pipeline + Negation Detection + Judge",
        "color": "blue",
    },
    "workflow": {
        "name": "Workflow",
        "emoji": "⚙️",
        "tagline": "Adım adım, sıfır sapma",
        "description": "Workflow Governor + Step Validation + Diagram-Aware Flows",
        "color": "green",
    },
    "creative": {
        "name": "Creative",
        "emoji": "🎨",
        "tagline": "Kısıtlar içinde özgürlük",
        "description": "C5 Constraint Engine + Format Enforcement + Auto-Fix",
        "color": "magenta",
    },
}

# --- Workflow patternleri (en yüksek öncelik) ---
WORKFLOW_KEYWORDS = [
    # English
    r"(?i)\bhow (to|do|can|should|would|does)\b",
    r"(?i)\bsteps? (to|for|in|of|required)\b",
    r"(?i)\b(workflow|pipeline|process|procedure|methodology|protocol)\b",
    r"(?i)\b(guide|walkthrough|tutorial|recipe|blueprint|playbook)\b",
    r"(?i)\b(implement|execute|deploy|configure|setup\b|install|scaffold)\b",
    r"(?i)\b(sequence|chain|phase|stage|step[\s-]by[\s-]step)\b",
    # Turkish
    r"(?i)\b(adım\s*adım|adımlar[ıi]|aşamalar[ıi]|aşama\s*aşama)\b",
    r"(?i)\b(nas[ıi]l\s+yap[ıi]l[ıi]r|nas[ıi]l\s+kurulur|nas[ıi]l\s+kullan[ıi]l[ıi]r)\b",
    r"(?i)\b(bana\s+\w+\s+(anlat|göster|öğret|açıkla))\b",
    r"(?i)\b(bana\s+(anlat|göster|öğret|açıkla))\b",
    r"(?i)\b(iş\s*akış[ıi]|workflow|rehber|k[ıi]lavuz|talimat)\b",
    r"(?i)\b(uygula|çal[ıi]şt[ıi]r|dağ[ıi]t|yap[ıi]land[ıi]r|kurulum|kurmak)\b",
]

# --- Creative patternleri ---
CREATIVE_KEYWORDS = [
    # English
    r"(?i)\b(write|compose|draft|create|generate|produce|craft)\b.*\b(tweet|post|thread|email|newsletter|article|blog|story|poem|song|script|caption)\b",
    r"(?i)\b(content|copywriting|marketing|brand|social media|seo)\b.*\b(strategy|plan|idea|brief|outline)\b",
    r"(?i)\b(creative|brainstorm|ideate|inspire|innovative|imaginative)\b",
    r"(?i)\b(tagline|slogan|headline|cta|call[\s-]to[\s-]action)\b",
    r"(?i)\b(tweet|post|thread)\b.*\b(about|on|for|regarding)\b",
    # Turkish
    r"(?i)\b(yaz|oluştur|hazırla|tasarla|kaleme\s+al)\b.*\b(içerik|makale|yazı|şiir|hikaye|senaryo|tweet|post|thread|e\s*posta|newsletter)\b",
    r"(?i)\b(tweet|içerik|makale|yazı|thread|posta|newsletter)\b.*\b(yaz|oluştur|hazırla|tasarla)\b",  # reverse order
    r"(?i)\b(kampanya|reklam|ilan|duyuru|brief)\b.*\b(hazırla|yaz|oluştur|tasarla)\b",
    r"(?i)\b(sosyal\s*medya|linkedin|x\s*postu)\b.*\b(içerik|paylaşım|gönderi|strateji)\b",
    r"(?i)\b(paylaşım[ı]?|gönderi)\b.*\b(hazırla|yaz|oluştur|tasarla)\b",  # "linkedin paylaşımı hazırla"
    r"(?i)\b(başlık\s*yaz|slogan\s*bul|catchy\s*title)\b",
]

# --- FactCheck keywordleri (opsiyonel override) ---
FACTCHECK_KEYWORDS = [
    # English
    r"(?i)\b(doğru\s*mu|yanlış\s*mı|correct|verify|validate|check|fact[\s-]?check)\b",
    r"(?i)\b(is this accurate|is that true|kaynak|source|evidence|proof)\b",
    r"(?i)\b(conflict|contradiction|inconsistency|tutarsız|çelişki)\b",
    # Turkish
    r"(?i)\b(doğrul[ua]?|kontrol\s*et|teyit|emin\s*misin)\b",
    r"(?i)\b(anlamadım|açıkla\b|detaylı\s*açıkla)\b",  # factcheck altında sorgulama
]


class TaskClassifier:
    """
    Deterministic query classifier.

    Kullanım:
        classifier = TaskClassifier()
        mode = classifier.classify("how to deploy anchor?")
        # → "workflow"

        mode = classifier.classify("write a tweet about AI")
        # → "creative"

        mode = classifier.classify("what is NPX1?")
        # → "factcheck"
    """

    def __init__(self):
        self._workflow_patterns = [re.compile(p) for p in WORKFLOW_KEYWORDS]
        self._creative_patterns = [re.compile(p) for p in CREATIVE_KEYWORDS]
        self._factcheck_patterns = [re.compile(p) for p in FACTCHECK_KEYWORDS]

    def classify(self, query: str, mode_hint: str | None = None) -> str:
        """
        Query'yi analiz et ve uygun mod'u döndür.

        Args:
            query: Kullanıcının girdiği soru/metin
            mode_hint: Kullanıcı tarafından belirtilmiş mod (varsa)

        Returns:
            "factcheck", "workflow", veya "creative"
        """
        # 0. Empty/trivial query guard
        if not query or not query.strip():
            return "factcheck"

        # 1. Manuel override
        if mode_hint and mode_hint in MODE_REGISTRY:
            return mode_hint

        # 2. Workflow keyword check (en yüksek öncelik)
        for pattern in self._workflow_patterns:
            if pattern.search(query):
                return "workflow"

        # 3. Creative keyword check (factcheck'ten önce — içerik üretimi spesifik)
        for pattern in self._creative_patterns:
            if pattern.search(query):
                return "creative"

        # 4. FactCheck keyword check
        for pattern in self._factcheck_patterns:
            if pattern.search(query):
                return "factcheck"

        # 5. Default: factcheck
        return "factcheck"

    def classify_with_confidence(self, query: str, mode_hint: str | None = None) -> tuple[str, float]:
        """
        Güven skoru ile birlikte sınıflandırma.

        Returns:
            (mode, confidence)
            confidence: 0.0 - 1.0 arası
            - 1.0: %100 deterministic (manuel override veya net pattern match)
            - 0.7: Pattern match var ama zayıf
            - 0.5: Default (hiçbir pattern eşleşmedi)
            - 0.0: Fallback (LLM kullanılmalı)
        """
        if not query or not query.strip():
            return "factcheck", 0.5

        if mode_hint and mode_hint in MODE_REGISTRY:
            return mode_hint, 1.0

        # Kaç pattern match etti?
        wf_matches = sum(1 for p in self._workflow_patterns if p.search(query))
        cr_matches = sum(1 for p in self._creative_patterns if p.search(query))
        fc_matches = sum(1 for p in self._factcheck_patterns if p.search(query))

        total_matches = wf_matches + cr_matches + fc_matches

        # Hiç pattern eşleşmedi — default
        if total_matches == 0:
            return "factcheck", 0.5

        # Tek mod eşleşti
        if wf_matches > 0 and cr_matches == 0 and fc_matches == 0:
            return "workflow", min(0.7 + wf_matches * 0.1, 1.0)
        if cr_matches > 0 and wf_matches == 0 and fc_matches == 0:
            return "creative", min(0.7 + cr_matches * 0.1, 1.0)
        if fc_matches > 0 and wf_matches == 0 and cr_matches == 0:
            return "factcheck", min(0.7 + fc_matches * 0.1, 1.0)

        # Çoklu mod eşleşti — en yüksek skorlu mod
        scores = {
            "workflow": wf_matches,
            "creative": cr_matches,
            "factcheck": fc_matches,
        }
        best_mode = max(scores, key=scores.get)
        return best_mode, 0.4  # düşük güven — ambiguity var

    def is_ambiguous(self, query: str) -> bool:
        """Query ambiguity var mı? (hiçbir pattern eşleşmediyse veya çoklu eşleşme varsa)"""
        mode, confidence = self.classify_with_confidence(query)
        return confidence < 0.6

    def classify_with_llm_fallback(
        self, query: str, llm_client, mode_hint: str | None = None
    ) -> str:
        """
        Deterministic + LLM fallback.

        Önce keyword-based dene, ambiguity varsa LLM'e sor.
        """
        # Önce deterministic + confidence
        mode, confidence = self.classify_with_confidence(query, mode_hint)

        # Ambiguity: ya hiç eşleşme yok ya da çoklu eşleşme var
        if confidence < 0.6:
            llm_mode = self._ask_llm(query, llm_client)
            if llm_mode and llm_mode in MODE_REGISTRY:
                return llm_mode

        return mode

    def _ask_llm(self, query: str, llm_client) -> str | None:
        """LLM'e ambiguity durumunda sor."""
        # Dil algılama: Türkçe sorgulara Türkçe prompt
        is_turkish = bool(re.search(r'[çğıöşü]', query.lower()))
        
        if is_turkish:
            prompt = (
                "Bu kullanıcı sorusunu aşağıdaki kategorilerden birine sınıflandır:\n"
                "- 'factcheck': Doğruluk kontrolü, gerçek sorgulama, tanım sorusu, açıklama\n"
                "- 'workflow': Adım-adım rehber, süreç anlatımı, nasıl yapılır, tutorial\n"
                "- 'creative': İçerik üretimi, yazma, yaratıcı çalışma, sosyal medya paylaşımı\n\n"
                f"Soru: {query}\n\n"
                "Sadece kategori kelimesini yaz:"
            )
        else:
            prompt = (
                "Classify this user query into one of these categories:\n"
                "- 'factcheck' for factual accuracy, truth-checking, definitions, explanations\n"
                "- 'workflow' for step-by-step guides, tutorials, how-to, processes\n"
                "- 'creative' for content creation, writing, social media posts, brainstorming\n\n"
                f"Query: {query}\n\n"
                "Answer with just the category word:"
            )
        try:
            response = llm_client.chat(prompt).strip().lower()
            # Temizlik: sadece kelime
            for mode in MODE_REGISTRY:
                if mode in response:
                    return mode
        except Exception:
            pass
        return None

    @staticmethod
    def info(mode: str) -> dict:
        """Bir mod hakkında bilgi döndür."""
        return MODE_REGISTRY.get(mode, MODE_REGISTRY["factcheck"])

    @staticmethod
    def list_modes() -> dict[str, dict]:
        """Tüm modları listele."""
        return dict(MODE_REGISTRY)

    @staticmethod
    def test_classifications() -> list[dict]:
        """
        Test senaryoları — classifier doğruluğunu doğrula.

        Returns:
            Her test için {query, expected, actual, pass}
        """
        test_cases = [
            # Workflow
            ("how to deploy anchor?", "workflow"),
            ("adım adım anlatır mısın kurulumu?", "workflow"),
            ("bana anchor kurulum adımlarını göster", "workflow"),
            ("nasıl yapılır bu işlem?", "workflow"),
            ("steps to implement a feature", "workflow"),
            ("workflow nasıl çalışır?", "workflow"),
            ("tutorial yazar mısın?", "workflow"),
            # Creative
            ("write a tweet about AI", "creative"),
            ("bir tweet yaz anchor hakkında", "creative"),
            ("slogan bul startup için", "creative"),
            ("linkedin paylaşımı hazırla", "creative"),
            ("içerik oluştur blog için", "creative"),
            ("draft a newsletter", "creative"),
            # FactCheck
            ("NPX1 nedir?", "factcheck"),
            ("bu doğru mu: anchor hızlı mı?", "factcheck"),
            ("anlamadım açıklar mısın?", "factcheck"),
            ("what is anchor engine?", "factcheck"),
            ("verify this claim", "factcheck"),
            # Default
            ("merhaba", "factcheck"),
            ("bugün hava nasıl?", "factcheck"),
        ]

        classifier = TaskClassifier()
        results = []
        for query, expected in test_cases:
            actual = classifier.classify(query)
            results.append({
                "query": query,
                "expected": expected,
                "actual": actual,
                "pass": actual == expected,
            })
        return results
