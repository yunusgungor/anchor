"""
Anchor v5.0 — Structured Feedback Generation (GaaA-inspired).

Guardian-as-Advisor (arxiv 2604.07655) paradigması:
  - Tespit edilen her violation için:
    - Kural adı (rule)
    - İhlal açıklaması (violation)
    - Ciddiyet (severity)
    - Doğru versiyon / düzeltme (correction)
    - Güven skoru (confidence)

  Content type classification:
    - Educational: öğretici içerik → workflow step'leri atlanır
    - Factual: salt bilgi → tüm kontroller
    - Creative: yaratıcı → sadece domain kuralları
    - Procedural: prosedürel → workflow ağırlıklı
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from anchor import Conflict, Severity, Correction

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Content Type Classification
# ──────────────────────────────────────────────


class ContentType(Enum):
    """LLM çıktısının içerik tipi — hangi kuralların uygulanacağını belirler.

    Educational: öğretici, eğitim amaçlı → workflow rule'ları atlanır
    Factual:     salt bilgi aktarımı → tüm rule'lar aktif
    Creative:    yaratıcı/metin üretimi → sadece domain kuralları
    Procedural:  adım-adım işlem anlatımı → workflow ağırlıklı
    """
    EDUCATIONAL = "educational"
    FACTUAL = "factual"
    CREATIVE = "creative"
    PROCEDURAL = "procedural"


def classify_content(llm_output: str, user_query: str = "") -> ContentType:
    """LLM çıktısını analiz ederek içerik tipini belirle.

    Strateji:
      1. Output'ta yaratıcı desenler varsa VEYA query'de yaratıcı talep varsa → CREATIVE
      2. Output'ta adım numarası/liste varsa → PROCEDURAL
      3. Query'de öğretici kelimeler VE output'ta öğretici yapı varsa → EDUCATIONAL
      4. Varsayılan → FACTUAL
    """
    output_lower = llm_output.lower()
    query_lower = user_query.lower()

    # --- Creative (check first — most distinctive) ---
    creative_markers = [
        "story", "hikaye", "poem", "şiir", "creative", "yaratıcı",
        "imagine", "düşle", "fictional", "kurgu",
    ]
    output_has_creative = any(m in output_lower for m in creative_markers)
    query_has_creative = any(m in query_lower for m in creative_markers)
    if output_has_creative or query_has_creative:
        return ContentType.CREATIVE

    # --- Educational (check before procedural — educational content often uses steps) ---
    edu_markers = [
        "nedir", "ne demek", "nasıl çalışır", "örnek", "açıkla",
        "explain", "what is", "how does", "example", "tutorial",
        "öğren", "öğret", "ders", "rehber", "guide",
        "adım adım", "step by step",
    ]
    query_has_edu = any(m in query_lower for m in edu_markers)

    # Output teaching structure (multi-sentence explanation, examples, etc.)
    output_has_edu_structure = (
        len(llm_output) > 200 or
        output_lower.count("örneğin") > 0 or
        output_lower.count("for example") > 0 or
        output_lower.count("şöyle") > 0
    )

    if query_has_edu and output_has_edu_structure:
        return ContentType.EDUCATIONAL

    # --- Procedural ---
    proc_markers = [
        "adım", "step", "önce", "sonra", "ardından", "aşama",
        "first", "then", "next", "finally", "şu şekilde",
    ]
    output_has_proc = sum(1 for m in proc_markers if m in output_lower)
    if output_has_proc >= 3:
        return ContentType.PROCEDURAL

    return ContentType.FACTUAL


# ──────────────────────────────────────────────
# Structured Feedback Types
# ──────────────────────────────────────────────


@dataclass
class FeedbackItem:
    """Tek bir violation için yapılandırılmış geribildirim (GaaA formatı).

    Attributes:
        rule:       Kural ID'si (örn. "tdd-cycle")
        rule_type:  Kural tipi (domain | workflow | hybrid)
        violation:  İhlal açıklaması (insan tarafından okunabilir)
        severity:   Ciddiyet etiketi (INFO | WARNING | ERROR | CRITICAL)
        correction: Doğru versiyon / düzeltme önerisi
        original:   LLM'in yanlış söylediği kısım
        confidence: Tespit güven skoru (0-1)
        step_violation: Varsa step violation detayı
    """
    rule: str
    rule_type: str
    violation: str
    severity: str
    correction: str
    original: str = ""
    confidence: float = 0.0
    step_violation: Optional[dict] = None  # ViolationType, step_id, step_title

    def to_gaaa_string(self) -> str:
        """GaaA formatında insan-okunabilir string.

        Format (GaaA inspired):
          Kural [tdd-cycle] İhlal: önce test yazılmadı.
          Doğrusu: RED test yazıp sonra geçir.
          Severity: HIGH
        """
        lines = [
            f"Kural [{self.rule}] İhlal: {self.violation}",
            f"Doğrusu: {self.correction}",
            f"Severity: {self.severity}",
            f"Güven: %{self.confidence * 100:.0f}",
        ]
        if self.original:
            lines.insert(0, f"Yanlış: {self.original}")
        if self.step_violation:
            sv = self.step_violation
            lines.append(f"Adım [{sv.get('step_id', '?')}]: {sv.get('step_title', '')}")
        return "\n".join(lines)

    @classmethod
    def from_conflict(cls, conflict: Conflict) -> "FeedbackItem":
        """Bir Conflict objesinden FeedbackItem oluştur."""
        from anchor import ViolationType

        # Severity etiketi
        severity_label = conflict.severity.name  # INFO, WARNING, ERROR, CRITICAL

        # Violation açıklaması
        if conflict.violation_type:
            vt = conflict.violation_type
            if isinstance(vt, ViolationType):
                vt_labels = {
                    ViolationType.MISSING_STEP: "Eksik adım",
                    ViolationType.ORDER_VIOLATION: "Sıra ihlali",
                    ViolationType.EXTRA_STEP: "Gereksiz adım",
                    ViolationType.INCOMPLETE_STEP: "Eksik uygulanmış adım",
                }
                violation_str = f"{vt_labels.get(vt, vt.value)}: {conflict.claim or conflict.llm_claim}"
            else:
                violation_str = f"{vt}: {conflict.claim or conflict.llm_claim}"
        else:
            # Factual conflict
            violation_str = f"Bilgi çelişkisi: {conflict.claim or conflict.llm_claim}"

        # Step violation detayı
        step_detail = None
        if conflict.step_violation:
            sv = conflict.step_violation
            step_detail = {
                "step_id": sv.step_id if hasattr(sv, 'step_id') else str(sv),
                "step_title": sv.step_title if hasattr(sv, 'step_title') else "",
                "violation_type": sv.violation_type.value if hasattr(sv, 'violation_type') and hasattr(sv.violation_type, 'value') else str(getattr(sv, 'violation_type', '')),
            }

        return cls(
            rule=conflict.rule_id,
            rule_type=conflict.rule_type or "domain",
            violation=violation_str,
            severity=severity_label,
            correction=conflict.fact or conflict.kb_fact,
            original=conflict.claim or conflict.llm_claim,
            confidence=conflict.confidence,
            step_violation=step_detail,
        )


@dataclass
class StructuredFeedback:
    """Bir turdaki tüm geribildirimlerin toplamı.

    Attributes:
        feedback_items:  Her violation için FeedbackItem
        rule_count:      Kaç farklı rule ihlal edilmiş
        total_violations: Toplam violation sayısı
        max_severity:    En yüksek ciddiyet
        content_type:    İçerik tipi
        has_workflow_violations: Workflow ihlali var mı?
        has_factual_conflicts:   Factual çelişki var mı?
        feedback_text:   İnsan tarafından okunabilir metin (tüm item'lar birleşik)
    """
    feedback_items: list[FeedbackItem] = field(default_factory=list)
    rule_count: int = 0
    total_violations: int = 0
    max_severity: Severity = Severity.NONE
    content_type: ContentType = ContentType.FACTUAL
    has_workflow_violations: bool = False
    has_factual_conflicts: bool = False
    feedback_text: str = ""

    def __post_init__(self):
        """Feedback text'ini otomatik oluştur."""
        if not self.feedback_text and self.feedback_items:
            self.feedback_text = self._build_feedback_text()

    def _build_feedback_text(self) -> str:
        """Tüm feedback item'larını birleşik bir metne dönüştür.

        Output format — LLM'e gönderilecek prompt eki:
        ```
        ⚓ Anchor Düzeltme Önerileri:
        
        [1] Kural [tdd-cycle] (ERROR)
            İhlal: Adım 2 atlanmış — RED test yazılmadı
            Doğrusu: Önce RED test yaz, sonra implement et
            Güven: %92
        
        [2] Kural [clean-arch] (WARNING)
            İhlal: Controller domain'e bağımlı değil
            Doğrusu: Controller domain katmanına bağımlı olmalı
        ```
        """
        if not self.feedback_items:
            return ""

        lines = ["⚓ **Anchor Düzeltme Önerileri:**", ""]

        # Group by severity
        severity_order = ["CRITICAL", "ERROR", "WARNING", "INFO"]
        sorted_items = sorted(
            self.feedback_items,
            key=lambda x: severity_order.index(x.severity) if x.severity in severity_order else 99,
        )

        for i, item in enumerate(sorted_items, 1):
            severity_icon = {
                "CRITICAL": "🔴",
                "ERROR": "🟠",
                "WARNING": "🟡",
                "INFO": "🔵",
            }.get(item.severity, "⚪")

            lines.append(f"[{i}] {severity_icon} Kural [{item.rule}] ({item.severity})")
            lines.append(f"    İhlal: {item.violation}")
            lines.append(f"    Doğrusu: {item.correction}")
            lines.append(f"    Güven: %{item.confidence * 100:.0f}")
            if item.step_violation:
                sv = item.step_violation
                lines.append(f"    Adım: [{sv.get('step_id', '?')}] {sv.get('step_title', '')}")
            lines.append("")

        return "\n".join(lines).strip()

    @classmethod
    def from_conflicts(
        cls,
        conflicts: list[Conflict],
        content_type: ContentType = ContentType.FACTUAL,
    ) -> "StructuredFeedback":
        """Conflict listesinden StructuredFeedback oluştur."""
        items = [FeedbackItem.from_conflict(c) for c in conflicts]

        # Dedup by (rule, violation) — aynı ihlal tekrarlanmamalı
        seen: set[tuple[str, str]] = set()
        unique_items: list[FeedbackItem] = []
        for item in items:
            key = (item.rule, item.violation)
            if key not in seen:
                seen.add(key)
                unique_items.append(item)

        # Max severity
        max_sev = Severity.NONE
        has_wf = False
        has_factual = False
        for c in conflicts:
            if c.severity.value > max_sev.value:
                max_sev = c.severity
            if c.violation_type is not None:
                has_wf = True
            if c.violation_type is None:
                has_factual = True

        return cls(
            feedback_items=unique_items,
            rule_count=len(set(i.rule for i in unique_items)),
            total_violations=len(unique_items),
            max_severity=max_sev,
            content_type=content_type,
            has_workflow_violations=has_wf,
            has_factual_conflicts=has_factual,
        )


# ──────────────────────────────────────────────
# GaaA Formatter
# ──────────────────────────────────────────────


class GaaAFormatter:
    """GaaA (Guardian-as-Advisor) formatında feedback üretir.

    İki mod:
      - Telefon:   LLM prompt'una append edilecek metin
      - Structured: Makine tarafından işlenebilir dict
    """

    def format_feedback(self, feedback: StructuredFeedback) -> str:
        """StructuredFeedback'i LLM prompt'una append edilecek metne dönüştür.

        Returns:
            Prompt sonuna eklenecek metin. Boş olabilir (violation yoksa).
        """
        if not feedback.feedback_items:
            return ""

        header = self._build_header(feedback)
        body = feedback.feedback_text

        return f"{header}\n\n{body}"

    def _build_header(self, feedback: StructuredFeedback) -> str:
        """Feedback başlığını oluştur — tur bazında istatistik."""
        sev_labels = {
            Severity.NONE: "temiz",
            Severity.INFO: "bilgi",
            Severity.WARNING: "uyarı",
            Severity.ERROR: "hata",
            Severity.CRITICAL: "kritik",
        }
        sev_label = sev_labels.get(feedback.max_severity, "bilinmiyor")
        return (
            f"Aşağıdaki {feedback.total_violations} düzeltme önerisi "
            f"({feedback.rule_count} kural, seviye: {sev_label}) "
            f"uygulanmalıdır. Lütfen yanıtınızı buna göre düzenleyin."
        )

    def format_to_dict(self, conflicts: list[Conflict]) -> list[dict]:
        """Conflict'leri makine tarafından işlenebilir dict listesine dönüştür.

        Hermes plugin'i veya API tüketicileri için.
        """
        feedback = StructuredFeedback.from_conflicts(conflicts)
        return [
            {
                "rule": item.rule,
                "rule_type": item.rule_type,
                "violation": item.violation,
                "severity": item.severity,
                "correction": item.correction,
                "original": item.original,
                "confidence": item.confidence,
                "step_violation": item.step_violation,
            }
            for item in feedback.feedback_items
        ]
