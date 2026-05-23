"""
Rectification v2 — Sentence-level patch engine.

Stratejiler:
  - INFO:     Dipnot ekle (append annotation)
  - WARNING:  Ekleme yap (insert after sentence)
  - ERROR:    Cümle düzelt (patch sentence inline)
  - CRITICAL: Cümle override (replace sentence with KB fact)
"""

from .patch_engine import PatchEngine, PatchStrategy

__all__ = ["PatchEngine", "PatchStrategy"]
