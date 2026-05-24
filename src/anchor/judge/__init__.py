"""
Anchor Judge — Semantic rectification katmanı.

Phase 1: Embedding-based semantic similarity
  FactMatcher'da Jaccard distance yerine sentence-transformer
  embedding cosine similarity kullanır.

Phase 2: LLM-as-Judge
  Borderline conflict'lerde (0.5 <= d_emb <= 0.7) hafif bir
  LLM'e danışır. Sonuçlar cache'lenir (determinizm).

Kullanım:
    from anchor.judge import JudgeConfig, LLMJudge, JudgeVerdict
    from anchor.judge.cache import JudgeCache
    from anchor.judge.embedding import load_model, semantic_distance
    
    config = JudgeConfig(use_llm=True, llm_provider="openai")
    judge = LLMJudge(config)
    verdict = judge.judge(claim_text, fact_text)
"""

from anchor.judge.cache import JudgeCache, JudgeVerdict
from anchor.judge.llm_judge import JudgeConfig, LLMJudge
from anchor.judge import embedding

__all__ = [
    "embedding",
    "JudgeCache",
    "JudgeVerdict",
    "JudgeConfig",
    "LLMJudge",
]
