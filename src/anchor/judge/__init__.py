"""
Anchor Judge — Semantic rectification katmanı.

Phase 1: Embedding-based semantic similarity
  FactMatcher'da Jaccard distance yerine sentence-transformer
  embedding cosine similarity kullanır.

Phase 2 (plan): LLM-as-Judge
  Borderline conflict'lerde hafif bir LLM'e danışır.

Kullanım:
    from anchor.judge.embedding import load_model, semantic_distance
    load_model()
    d = semantic_distance("RISC-V mimarili", "RISC-V + Systolic Array NPU")
"""

from anchor.judge import embedding

__all__ = ["embedding"]
