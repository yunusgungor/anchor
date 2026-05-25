"""
TaskClassifier — Deterministic query routing for Anchor Agent.

Üç mod arasında routing yapar:
  1. factcheck  → Varsayılan. Doğruluk kontrolü, tutarlılık, fikir muhalefeti
  2. workflow   → Adım-adım iş akışı, süreç, tutorial
  3. creative   → İçerik üretimi, yaratıcı yazarlık, sosyal medya

Felsefe: Deterministic öncelikli, LLM sadece son çare.
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
        "description": "Workflow Governor + Step Validation",
        "color": "green",
    },
    "creative": {
        "name": "Creative",
        "emoji": "🎨",
        "tagline": "Kısıtlar içinde özgürlük",
        "description": "C5 Constraint Engine + Format Enforcement",
        "color": "magenta",
    },
}

# --- Workflow patternleri (en yüksek öncelik) ---
WORKFLOW_KEYWORDS = [
    r"(?i)\bhow (to|do|can|should|would|does)\b",
    r"(?i)\bsteps? (to|for|in|of|required)\b",
    r"(?i)\b(workflow|pipeline|process|procedure|methodology|protocol)\b",
    r"(?i)\b(guide|walkthrough|tutorial|recipe|blueprint|playbook)\b",
    r"(?i)\b(implement|execute|deploy|configure|setup|install|scaffold)\b",
    r"(?i)\b(sequence|chain|phase|stage|step[\s-]by[\s-]step)\b",
]

# --- Creative patternleri ---
CREATIVE_KEYWORDS = [
    r"(?i)\b(write|compose|draft|create|generate|produce|craft)\b.*\b(tweet|post|thread|email|newsletter|article|blog|story|poem|song|script|caption)\b",
    r"(?i)\b(content|copywriting|marketing|brand|social media|seo)\b.*\b(strategy|plan|idea|brief|outline)\b",
    r"(?i)\b(creative|brainstorm|ideate|inspire|innovative|imaginative)\b",
    r"(?i)\b(tagline|slogan|headline|cta|call[\s-]to[\s-]action)\b",
    r"(?i)\b(tweet|post|thread)\b.*\b(about|on|for|regarding)\b",
    r"(?i)\byaz\b.*\b(içerik|makale|yazı|şiir|hikaye|senaryo)\b",
    r"(?i)\b(kampanya|reklam|ilan|duyuru|brief)\b.*\b(hazırla|yaz|oluştur|tasarla)\b",
]

# --- FactCheck keywordleri (opsiyonel override) ---
FACTCHECK_KEYWORDS = [
    r"(?i)\b(doğru\s*mu|yanlış\s*mı|correct|verify|validate|check|fact[\s-]?check)\b",
    r"(?i)\b(is this accurate|is that true|kaynak|source|evidence|proof)\b",
    r"(?i)\b(conflict|contradiction|inconsistency|tutarsız|çelişki)\b",
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
        # 1. Manuel override
        if mode_hint and mode_hint in MODE_REGISTRY:
            return mode_hint
        
        # 2. Workflow keyword check (en yüksek öncelik)
        for pattern in self._workflow_patterns:
            if pattern.search(query):
                return "workflow"
        
        # 3. FactCheck keyword check
        for pattern in self._factcheck_patterns:
            if pattern.search(query):
                return "factcheck"
        
        # 4. Creative keyword check
        for pattern in self._creative_patterns:
            if pattern.search(query):
                return "creative"
        
        # 5. Default: factcheck
        return "factcheck"
    
    def classify_with_llm_fallback(
        self, query: str, llm_client, mode_hint: str | None = None
    ) -> str:
        """
        Deterministic + LLM fallback.
        
        Önce keyword-based dene, ambiguity varsa LLM'e sor.
        """
        # Önce deterministic
        mode = self.classify(query, mode_hint)
        
        # Ambiguity detection: hiçbir keyword eşleşmediyse LLM'e sor
        if mode == "factcheck" and len(query) > 50:
            llm_mode = self._ask_llm(query, llm_client)
            if llm_mode and llm_mode != "factcheck":
                return llm_mode
        
        return mode
    
    def _ask_llm(self, query: str, llm_client) -> str | None:
        """LLM'e ambiguity durumunda sor."""
        prompt = (
            "Classify this user query into one of these categories:\n"
            "- 'factcheck' for factual accuracy, truth-checking, evidence requests\n"
            "- 'workflow' for step-by-step guides, tutorials, processes\n"
            "- 'creative' for content creation, writing, social media posts\n\n"
            f"Query: {query}\n\n"
            "Answer with just the category word:"
        )
        try:
            response = llm_client.chat(prompt).strip().lower()
            if response in MODE_REGISTRY:
                return response
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
