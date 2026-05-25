"""
WorkflowMode — Anchor'ın Workflow Governor yeteneğini sergileyen mod.

Bu mod şunları gösterir:
  - Workflow Governor ile adım-adım süreç yönetimi
  - Adım sırası ve eksik adım kontrolü (ORDER_VIOLATION / MISSING_STEP)
  - Karmaşık iş akışlarının doğrulanması (INCOMPLETE_STEP)
  - Gerçek anchor_result.step_violations ile entegrasyon

[v4.5+] Enhanced Features:
  - Real Anchor Governor: BUILTIN_WORKFLOWS yerine gerçek engine step_violations
  - Step Progress Bar: Adımların tamamlanma yüzdesini görselleştir
  - Violation Detail: Her ihlal için tip, adım, mesaj + fix önerisi
  - Flow Path Display: Diagram-aware flow paths'i göster
"""

import re
from typing import Any, Optional

from anchor.engine import RectificationResult

# Violation type display
VIOLATION_DISPLAY = {
    "MISSING_STEP": {"emoji": "⭕", "label": "Eksik Adım", "color": "\033[93m"},
    "ORDER_VIOLATION": {"emoji": "🔀", "label": "Sıra Hatası", "color": "\033[91m"},
    "INCOMPLETE_STEP": {"emoji": "⚠️", "label": "Eksik İçerik", "color": "\033[94m"},
}
RESET = "\033[0m"


class WorkflowMode:
    """
    Workflow Mode — Adım-adım süreç rehberliği.

    Anchor'ın Workflow Governor'ını kullanarak:
    - Kullanıcıya adım-adım rehberlik eder
    - Her adımın output'unu validate eder
    - Eksik/atlama varsa uyarır
    - Gerçek engine.step_violations ile çalışır

    [v4.5+] Artık BUILTIN_WORKFLOWS yerine Anchor engine'in
    ürettiği gerçek step_violations'ları kullanır.
    """

    def __init__(self):
        self.name = "workflow"
        self._stats = {"total_workflows": 0, "errors_caught": 0, "total_steps_validated": 0}

    def post_process(
        self,
        query: str,
        raw: str,
        corrected: str,
        anchor_result: "RectificationResult | None" = None,
    ) -> dict:
        """
        Anchor sonrası Workflow özel işleme.

        1. anchor_result.step_violations'ları oku
        2. Her ihlali violation tipine göre sınıflandır
        3. Step progress yüzdesi hesapla
        4. Flow path varsa diagram-aware info ekle
        5. Fix önerileri oluştur
        """
        result = {
            "mode": self.name,
            "workflow_found": False,
            "workflow_name": None,
            "violations": [],
            "violation_breakdown": {},
            "step_progress": {"completed": 0, "total": 0, "percentage": 0},
            "violation_types": set(),
            "flow_paths": [],
            "fix_suggestions": [],
        }

        if anchor_result and hasattr(anchor_result, 'step_violations'):
            step_violations = anchor_result.step_violations or []

            if step_violations:
                result["workflow_found"] = True

                # --- Violations list ---
                violations = self._parse_violations(step_violations)
                result["violations"] = violations

                # --- Violation breakdown ---
                breakdown = self._violation_breakdown(violations)
                result["violation_breakdown"] = breakdown
                result["violation_types"] = list(breakdown.keys())

                # --- Step progress ---
                progress = self._calculate_progress(violations)
                result["step_progress"] = progress

                # --- Flow paths (diagram-aware) ---
                if hasattr(anchor_result, 'flow_conflicts'):
                    result["flow_paths"] = anchor_result.flow_conflicts

                # --- Fix suggestions ---
                result["fix_suggestions"] = self._generate_fixes(violations, step_violations)

                # Stats
                self._stats["errors_caught"] += len(violations)
                self._stats["total_steps_validated"] += progress["total"]

        self._stats["total_workflows"] += 1
        return result

    def enrich_query(self, query: str, context_notes: str | None = None) -> str:
        """Workflow query'sini zenginleştir."""
        enriched = query
        if context_notes:
            enriched = f"{query}\n\n[Context]: {context_notes}"
        return enriched

    # ---------------------------------------------------------------- #
    # Violation Parsing
    # ---------------------------------------------------------------- #

    @staticmethod
    def _parse_violations(step_violations: list) -> list[dict]:
        """
        StepViolation nesnelerini dict listesine çevir.

        Her ihlal:
            {
                "type": "MISSING_STEP",
                "step_id": "step-2",
                "step_title": "Hatayı tanımla",
                "severity": "ERROR",
                "message": "...",
                "display": "⭕ [Eksik Adım] step-2: Hatayı tanımla",
            }
        """
        parsed = []
        for sv in step_violations:
            vtype = sv.violation_type.value if hasattr(sv.violation_type, 'value') else str(sv.violation_type)
            sev = sv.severity.name if hasattr(sv.severity, 'name') else "ERROR"
            display_info = VIOLATION_DISPLAY.get(vtype, {"emoji": "❓", "label": vtype})

            entry = {
                "type": vtype,
                "step_id": sv.step_id,
                "step_title": sv.step_title,
                "severity": sev,
                "message": sv.message if hasattr(sv, 'message') else f"{display_info['label']}: {sv.step_title}",
                "display": f"{display_info['emoji']} [{display_info['label']}] {sv.step_title}",
            }
            parsed.append(entry)
        return parsed

    @staticmethod
    def _violation_breakdown(violations: list[dict]) -> dict:
        """İhlal tiplerine göre dağılım."""
        breakdown = {}
        for v in violations:
            vtype = v["type"]
            if vtype not in breakdown:
                breakdown[vtype] = 0
            breakdown[vtype] += 1
        return breakdown

    @staticmethod
    def _calculate_progress(violations: list[dict]) -> dict:
        """
        Adım ilerleme yüzdesi hesapla.

        Toplam adım sayısı = tüm ihlallerin step_id'lerinin uniqueness'i
        + tamamlanan adımlar. Basit model: her ihlal = 1 eksik adım.
        """
        total_steps = max(len(set(v["step_id"] for v in violations)), 1)
        missing = len(violations)
        completed = max(0, total_steps - missing)
        return {
            "completed": completed,
            "total": total_steps,
            "percentage": round((completed / total_steps) * 100),
        }

    @staticmethod
    def _generate_fixes(violations: list[dict], raw_violations: list) -> list[str]:
        """Her ihlal için fix önerisi üret."""
        suggestions = []
        for v in violations:
            vtype = v["type"]
            title = v["step_title"]
            if vtype == "MISSING_STEP":
                suggestions.append(f"➕ '{title}' adımını ekleyin")
            elif vtype == "ORDER_VIOLATION":
                suggestions.append(f"🔀 '{title}' adımını doğru sıraya taşıyın")
            elif vtype == "INCOMPLETE_STEP":
                suggestions.append(f"📝 '{title}' adımını detaylandırın")
        return suggestions

    @staticmethod
    def format_workflow_report(violations: list[dict], progress: dict) -> str:
        """Workflow raporu formatla (terminal için)."""
        lines = ["\n📋 Workflow Validation Report"]
        lines.append(f"{'─'*40}")

        # Progress bar
        pct = progress["percentage"]
        bar_width = 20
        filled = int(pct / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"  İlerleme: {bar} {pct}% ({progress['completed']}/{progress['total']})")

        if violations:
            lines.append(f"\n  ⚠️  {len(violations)} ihlal tespit edildi:")
            for v in violations:
                lines.append(f"    {v['display']}")
                if v.get("message"):
                    lines.append(f"      → {v['message']}")
        else:
            lines.append("\n  ✅ Tüm adımlar tamam!")

        return "\n".join(lines)

    @property
    def stats(self) -> dict:
        return dict(self._stats)
