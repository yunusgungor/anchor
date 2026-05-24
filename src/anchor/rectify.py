"""
Anchor Rectification — Patch Engine.

Stratejiler:
  INFO:    dipnot ekle (append)
  WARNING: bilgi ekle (insert after sentence)
  ERROR:   cümleyi düzelt (patch inline)
  CRITICAL: cümleyi override et (replace)
"""

import re
from dataclasses import dataclass
from enum import Enum, auto

from anchor import Severity, Conflict


class PatchStrategy(Enum):
    APPEND_NOTE = auto()
    INSERT_AFTER = auto()
    PATCH_SENTENCE = auto()
    OVERRIDE_SENTENCE = auto()
    INSERT_BEFORE = auto()  # v4.0: Insert content BEFORE a specific position
    REORDER = auto()        # v4.0: Reorder steps within the text


@dataclass
class Patch:
    """Bir düzeltme operasyonu."""
    original: str       # Orijinal cümle
    replacement: str    # Yeni cümle
    position: int       # Metindeki pozisyon
    strategy: PatchStrategy
    applied: bool = False


class PatchEngine:
    """
    LLM output'una cümle-level patch uygular.
    Deterministic — hiçbir LLM çağrısı yok.
    """

    def __init__(self):
        self._total_calls = 0
        self._total_latency_us = 0

    def apply(self, llm_output: str, conflicts: list[Conflict]) -> tuple[str, list[Patch]]:
        """
        LLM output'una patch'leri uygula.

        Args:
            llm_output: LLM'in ürettiği ham metin
            conflicts: ConflictDetector'dan gelen çelişkiler

        Returns:
            (düzeltilmiş metin, uygulanan patch'ler)
        """
        import time
        t0 = time.perf_counter()
        self._total_calls += 1

        if not conflicts:
            return llm_output, []

        # Severity'ye göre sırala (yüksek önce, pozisyonu varsa son pozisyondan başla)
        def _sort_key(c):
            pos = c.position[0] if c.position else 0
            return (-c.severity.value, -pos)

        sorted_conflicts = sorted(conflicts, key=_sort_key)

        patches = []
        modified_text = llm_output

        for conflict in sorted_conflicts:
            patch = self._create_patch(conflict)
            if patch:
                modified_text = self._apply_patch(modified_text, patch)
                patches.append(patch)

        t1 = time.perf_counter()
        self._total_latency_us += (t1 - t0) * 1_000_000

        return modified_text, patches

    def _create_patch(self, conflict: Conflict) -> Patch | None:
        """Bir conflict'ten patch oluştur."""
        strategy = self._select_strategy(conflict.severity)

        # v4.0: Workflow violations may specify strategy via conflict attributes
        if conflict.violation_type is not None:
            # Workflow violations use INSERT_BEFORE or REORDER
            vt = conflict.violation_type.value if hasattr(conflict.violation_type, 'value') else str(conflict.violation_type)
            if vt in ('missing_step', 'incomplete_step'):
                strategy = PatchStrategy.INSERT_BEFORE
            elif vt == 'order_violation':
                strategy = PatchStrategy.REORDER

        original = conflict.claim
        pos = conflict.position[0] if conflict.position else 0

        if strategy == PatchStrategy.APPEND_NOTE:
            replacement = self._format_note(conflict.fact)
        elif strategy == PatchStrategy.INSERT_AFTER:
            replacement = self._format_insertion(conflict.fact)
        elif strategy == PatchStrategy.INSERT_BEFORE:
            replacement = self._format_insertion_before(conflict.fact)
        elif strategy == PatchStrategy.REORDER:
            replacement = self._format_reorder(conflict.fact)
        elif strategy == PatchStrategy.PATCH_SENTENCE:
            replacement = self._format_patch(original, conflict.fact)
        elif strategy == PatchStrategy.OVERRIDE_SENTENCE:
            replacement = self._format_override(conflict.fact)
        else:
            return None

        return Patch(
            original=original,
            replacement=replacement,
            position=pos,
            strategy=strategy,
        )

    def _select_strategy(self, severity: Severity) -> PatchStrategy:
        """Severity → strateji eşleştirme."""
        mapping = {
            Severity.INFO: PatchStrategy.APPEND_NOTE,
            Severity.WARNING: PatchStrategy.INSERT_AFTER,
            Severity.ERROR: PatchStrategy.PATCH_SENTENCE,
            Severity.CRITICAL: PatchStrategy.OVERRIDE_SENTENCE,
        }
        return mapping.get(severity, PatchStrategy.APPEND_NOTE)

    def _apply_patch(self, text: str, patch: Patch) -> str:
        """Patch'i metne uygula."""
        if patch.strategy == PatchStrategy.APPEND_NOTE:
            text = text.rstrip() + "\n\n" + patch.replacement
        elif patch.strategy == PatchStrategy.INSERT_AFTER:
            original = patch.original
            if original in text:
                end_pos = text.find(original) + len(original)
                text = text[:end_pos] + " " + patch.replacement + text[end_pos:]
            else:
                text = text.rstrip() + " " + patch.replacement
        elif patch.strategy == PatchStrategy.INSERT_BEFORE:
            # Insert replacement BEFORE the original text position
            original = patch.original
            if original in text:
                start_pos = text.find(original)
                text = text[:start_pos] + patch.replacement + " " + text[start_pos:]
            else:
                # If original not found, prepend
                text = patch.replacement + "\n\n" + text
        elif patch.strategy == PatchStrategy.REORDER:
            # Replace the ordered section (reorder steps)
            # For reorder, replacement contains the corrected section
            original = patch.original
            if original in text:
                text = text.replace(original, patch.replacement, 1)
            else:
                # If original not found at top level, check for fuzzy match
                text = self._fuzzy_replace(text, original, patch.replacement)
        elif patch.strategy in (PatchStrategy.PATCH_SENTENCE, PatchStrategy.OVERRIDE_SENTENCE):
            original = patch.original
            if original in text:
                text = text.replace(original, patch.replacement, 1)
            else:
                text = self._fuzzy_replace(text, original, patch.replacement)

        patch.applied = True
        return text

    def _fuzzy_replace(self, text: str, old: str, new: str) -> str:
        """Tam eşleşme bulunamazsa yaklaşık eşleşme dene."""
        if len(old) > 30:
            prefix = old[:30]
            idx = text.find(prefix)
            if idx >= 0:
                end_idx = idx + len(prefix)
                for i in range(end_idx, min(end_idx + 200, len(text))):
                    if text[i] in '.!?':
                        end_idx = i + 1
                        break
                else:
                    end_idx = min(end_idx + 100, len(text))
                return text[:idx] + new + text[end_idx:]

        return text.rstrip() + "\n\n" + new

    def _format_note(self, fact: str) -> str:
        return f"> 📝 **Not:** {fact.strip()}"

    def _format_insertion(self, fact: str) -> str:
        return f"Ancak kayıtlarıma göre: {fact.strip()}."

    def _format_insertion_before(self, fact: str) -> str:
        """Format for INSERT_BEFORE strategy — prepend a note."""
        return f"📋 **Eksik Adım:** {fact.strip()}"

    def _format_reorder(self, fact: str) -> str:
        """Format for REORDER strategy — corrected step order."""
        return f"📋 **Sıralama Düzeltmesi:** {fact.strip()}"

    def _format_patch(self, original: str, fact: str) -> str:
        return f"{original.strip().rstrip('.')} (doğrusu: {fact.strip()})."

    def _format_override(self, fact: str) -> str:
        return fact.strip()

    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
