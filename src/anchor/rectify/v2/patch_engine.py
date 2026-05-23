r"""
Patch Engine v2 — Sentence-level text rectification.

Matematik:
  - $T_{orig}$: LLM output
  - $C$: Claim (yanlış cümle)
  - $F$: Fact (doğru bilgi)
  - $P$: Patch strategy

Output:
  $T_{rect} = \text{apply}(T_{orig}, C, F, P)$

Stratejiler:
  INFO:     $T_{rect} = T_{orig} + \text{annotation}(F)$
  WARNING:  $T_{rect} = \text{insert_after}(T_{orig}, C, F)$
  ERROR:    $T_{rect} = \text{replace}(T_{orig}, C, C + F)$
  CRITICAL: $T_{rect} = \text{replace}(T_{orig}, C, F)$
"""

from enum import Enum
from dataclasses import dataclass

from anchor import Conflict, Severity


class PatchStrategy(Enum):
    """Düzeltme stratejisi."""
    APPEND_NOTE = 1      # Dipnot ekle
    INSERT_AFTER = 2     # Cümleden sonra doğruyu ekle
    PATCH_SENTENCE = 3   # Cümleyi düzelt (yanlış + doğru)
    OVERRIDE_SENTENCE = 4  # Cümleyi tamamen değiştir


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
            conflicts: ConflictDetectorV2'den gelen çelişkiler
            
        Returns:
            (düzeltilmiş metin, uygulanan patch'ler)
        """
        import time
        t0 = time.perf_counter()
        self._total_calls += 1
        
        if not conflicts:
            return llm_output, []
        
        # Severity'ye göre sırala (yüksek önce, son pozisyondan başla)
        sorted_conflicts = sorted(
            conflicts,
            key=lambda c: (-c.severity.value, -c.patch_position)
        )
        
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
        
        original = conflict.llm_claim
        
        if strategy == PatchStrategy.APPEND_NOTE:
            replacement = self._format_note(conflict.kb_fact)
        elif strategy == PatchStrategy.INSERT_AFTER:
            replacement = self._format_insertion(conflict.kb_fact)
        elif strategy == PatchStrategy.PATCH_SENTENCE:
            replacement = self._format_patch(original, conflict.kb_fact)
        elif strategy == PatchStrategy.OVERRIDE_SENTENCE:
            replacement = self._format_override(conflict.kb_fact)
        else:
            return None
        
        return Patch(
            original=original,
            replacement=replacement,
            position=conflict.patch_position,
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
            # Metin sonuna ekle
            text = text.rstrip() + "\n\n" + patch.replacement
        elif patch.strategy == PatchStrategy.INSERT_AFTER:
            # Orijinal cümlenin SONUNA ekle (noktadan sonra)
            original = patch.original
            if original in text:
                # Orijinal cümleyi bul, sonuna ekle
                end_pos = text.find(original) + len(original)
                text = text[:end_pos] + " " + patch.replacement + text[end_pos:]
            else:
                # Bulunamazsa sona ekle
                text = text.rstrip() + " " + patch.replacement
        elif patch.strategy in (PatchStrategy.PATCH_SENTENCE, PatchStrategy.OVERRIDE_SENTENCE):
            # Orijinal cümleyi değiştir
            original = patch.original
            if original in text:
                text = text.replace(original, patch.replacement, 1)
            else:
                # Fuzzy match dene
                text = self._fuzzy_replace(text, original, patch.replacement)
        
        patch.applied = True
        return text
    
    def _fuzzy_replace(self, text: str, old: str, new: str) -> str:
        """
        Tam eşleşme bulunamazsa yaklaşık eşleşme dene.
        
        Strateji: old'un ilk 30 karakterini bul, o cümleyi değiştir.
        """
        if len(old) > 30:
            prefix = old[:30]
            idx = text.find(prefix)
            if idx >= 0:
                # Cümlenin sonunu bul (nokta, ünlem, soru işareti)
                end_idx = idx + len(prefix)
                for i in range(end_idx, min(end_idx + 200, len(text))):
                    if text[i] in '.!?':
                        end_idx = i + 1
                        break
                else:
                    end_idx = min(end_idx + 100, len(text))
                
                return text[:idx] + new + text[end_idx:]
        
        # Hâlâ bulunamazsa sona ekle
        return text.rstrip() + "\n\n" + new
    
    def _format_note(self, fact: str) -> str:
        """> 📝 Not formatında dipnot."""
        return f"> 📝 **Not:** {fact.strip()}"
    
    def _format_insertion(self, fact: str) -> str:
        """Cümleden sonra eklenecek doğru bilgi."""
        return f"Ancak kayıtlarıma göre: {fact.strip()}."
    
    def _format_patch(self, original: str, fact: str) -> str:
        """Cümleyi düzelt — orijinal + doğru."""
        return f"{original.strip().rstrip('.')} (doğrusu: {fact.strip()})."
    
    def _format_override(self, fact: str) -> str:
        """Cümleyi tamamen değiştir — sadece doğru bilgi."""
        return fact.strip()
    
    @property
    def avg_latency_us(self) -> float:
        if self._total_calls == 0:
            return 0
        return self._total_latency_us / self._total_calls
