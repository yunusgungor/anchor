"""
WorkflowMode — Anchor'ın Workflow Governor yeteneğini sergileyen mod.

Bu mod şunları gösterir:
  - Workflow Governor ile adım-adım süreç yönetimi
  - Adım sırası ve eksik adım kontrolü
  - Karmaşık iş akışlarının doğrulanması
  - Adım bazlı output validation
"""

import re
from typing import Any, Optional

from anchor.engine import RectificationResult


# Workflow tanımları (demo amaçlı)
BUILTIN_WORKFLOWS = {
    "anchor-setup": {
        "name": "Anchor Kurulum",
        "steps": [
            "requirements kurulumu (pip install anchor-engine)",
            "rules dizini oluşturma",
            "topic tanımlama",
            "kural yazma (rule.md formatında)",
            "AnchorEngine build",
            "test çalıştırma",
        ],
    },
    "content-creation": {
        "name": "İçerik Üretimi",
        "steps": [
            "konu ve hedef kitle belirleme",
            "ana mesajı belirleme",
            "format seçimi (tweet/post/thread/makale)",
            "ilk taslağı yazma",
            "Anchor ile doğrulama",
            "son düzeltme ve yayın",
        ],
    },
    "fact-checking": {
        "name": "Doğruluk Kontrolü",
        "steps": [
            "sorguyu analiz et",
            "ilgili kuralları yükle",
            "A1: cümlelere ayır + hata tespit",
            "A2: semantic similarity kontrol",
            "A3: causal conflict tree oluştur",
            "A4: rectification uygula",
            "Judge pipeline ile doğrula",
            "rapor oluştur",
        ],
    },
}


class WorkflowMode:
    """
    Workflow Mode — Adım-adım süreç rehberliği.
    
    Anchor'ın Workflow Governor'ını kullanarak:
    - Kullanıcıya adım-adım rehberlik eder
    - Her adımın output'unu validate eder
    - Eksik/atlama varsa uyarır
    """
    
    def __init__(self):
        self.name = "workflow"
        self._stats = {"total_workflows": 0, "errors_caught": 0}
    
    def post_process(
        self,
        query: str,
        raw: str,
        corrected: str,
        anchor_result: "RectificationResult | None" = None,
    ) -> dict:
        """
        Anchor sonrası Workflow özel işleme.
        
        1. Workflow adımlarını parse et
        2. Eksik adım var mı kontrol et
        3. Adım sırası doğru mu kontrol et
        4. Output validation varsa çalıştır
        """
        result = {
            "mode": self.name,
            "workflow_detected": None,
            "steps_found": [],
            "steps_missing": [],
            "step_count": 0,
        }
        
        # Workflow adımlarını parse et
        steps = self._parse_steps(corrected)
        result["steps_found"] = steps
        result["step_count"] = len(steps)
        
        # Builtin workflow ile karşılaştır
        detected = self._detect_workflow(query, steps)
        result["workflow_detected"] = detected
        
        if detected and detected in BUILTIN_WORKFLOWS:
            expected = BUILTIN_WORKFLOWS[detected]["steps"]
            missing = self._find_missing_steps(steps, expected)
            result["steps_missing"] = missing
            
            if missing:
                result["warning"] = f"⚠️ Eksik adımlar: {', '.join(missing)}"
                self._stats["errors_caught"] += 1
        
        self._stats["total_workflows"] += 1
        return result
    
    def enrich_query(self, query: str, context_notes: str | None = None) -> str:
        """Workflow query'sini zenginleştir."""
        enriched = query
        if context_notes:
            enriched = f"{query}\n\n[Context]: {context_notes}"
        return enriched
    
    # -------- Helpers --------
    
    @staticmethod
    def _parse_steps(text: str) -> list[str]:
        """Cevaptaki adımları parse et."""
        steps = []
        
        # Pattern 1: "1️⃣ Adım 1:" veya "1. Adım"
        patterns = [
            r'\d+[\.\)]\s*(?:Adım\s*)?\d*\s*[:-]\s*(.+?)(?=\n\d+[\.\)]|\Z)',
            r'\d+[️⃣]\s*(?:Adım\s*)?\d*\s*[:-]\s*(.+?)(?=\n\d+[️⃣]|\Z)',
            r'(?:1️⃣|2️⃣|3️⃣|4️⃣|5️⃣|6️⃣|7️⃣|8️⃣|9️⃣|🔟)\s*(.+?)(?=\n(?:1️⃣|2️⃣|3️⃣|4️⃣|5️⃣|6️⃣|7️⃣|8️⃣|9️⃣|🔟)|\Z)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                steps = [m.strip().split('\n')[0][:80] for m in matches]
                break
        
        # Pattern 2: line-by-line numbered items
        if not steps:
            for line in text.split('\n'):
                line = line.strip()
                if re.match(r'^\d+[\.\)]\s', line):
                    step_text = re.sub(r'^\d+[\.\)]\s*', '', line)
                    steps.append(step_text[:80])
        
        return steps
    
    @staticmethod
    def _detect_workflow(query: str, steps: list[str]) -> str | None:
        """Hangi workflow olduğunu tespit et."""
        query_lower = query.lower()
        
        for wf_id, wf_info in BUILTIN_WORKFLOWS.items():
            name_lower = wf_info["name"].lower()
            if name_lower in query_lower:
                return wf_id
        
        return None
    
    @staticmethod
    def _find_missing_steps(found: list[str], expected: list[str]) -> list[str]:
        """Beklenen adımlardan hangileri eksik?"""
        missing = []
        found_lower = [s.lower() for s in found]
        
        for exp in expected:
            exp_lower = exp.lower()
            if not any(exp_lower[:10] in f for f in found_lower):
                missing.append(exp)
        
        return missing
    
    @property
    def stats(self) -> dict:
        return dict(self._stats)
