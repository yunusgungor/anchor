"""
LLM-as-Judge — Borderline conflict'lerde LLM'e danış.

Phase 2 of the Judge pipeline: embedding hala emin değilse
(0.5 <= d_emb <= 0.7 aralığı), hafif bir LLM'e basit bir
YES/NO sorusu sorulur.

Tasarım prensipleri:
  - MINIMAL: Tek cümlelik prompt, tek tokenlı yanıt (YES/NO)
  - CACHE'Lİ: Aynı (claim, fact) çifti → aynı sonuç
  - MODEL-AGNOSTIC: Herhangi bir LLM provider'ı ile çalışır
  - DÜŞÜK MALİYET: Sadece borderline case'lerde çağrı
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from anchor.judge.cache import JudgeCache, JudgeVerdict

logger = logging.getLogger(__name__)

# Varsayılan prompt — iki cümle arasında çelişki var mı?
DEFAULT_PROMPT_TEMPLATE = (
    "Bir LLM'in çıktısı ile bir bilgi tabanı arasındaki çelişkiyi tespit ediyoruz.\n\n"
    'LLM Çıktısı: "{claim}"\n'
    'Bilgi Tablosu: "{fact}"\n\n'
    "Bu iki ifade BİRBİRİYLE ÇELİŞİYOR mu?\n"
    "Cevap (sadece EVET veya HAYIR):"
)

# Daha kısa, daha az token harcayan alternatif
SHORT_PROMPT_TEMPLATE = (
    'Cümle A: "{claim}"\n'
    'Cümle B: "{fact}"\n\n'
    "Çelişiyor mu? Sadece EVET/HAYIR:"
)


@dataclass
class JudgeConfig:
    """LLM-as-Judge yapılandırması.
    
    Varsayılan: embedding + cache aktif, LLM kapalı.
    LLM'i etkinleştirmek için provider ve model belirtilmeli.
    """
    # Embedding
    use_embedding: bool = True
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    
    # LLM-as-Judge
    use_llm: bool = False
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: Optional[str] = None
    
    # Prompt
    prompt_template: str = "short"  # "short" veya "default"
    max_calls_per_session: int = 10
    
    # Cache
    cache_max_size: int = 1000
    cache_path: Optional[str] = None  # diske kaydetmek için
    
    # Eşikler (embedding distance)
    similar_threshold: float = 0.5    # d_emb < bu → benzer
    different_threshold: float = 0.7  # d_emb > bu → farklı


class LLMJudge:
    """
    LLM-as-Judge — borderline conflict kararları için.
    
    Kullanım:
        judge = LLMJudge(config)
        verdict = judge.judge(claim_text, fact_text)
        if verdict.is_conflict:
            # LLM çelişki var dedi
    """

    def __init__(self, config: Optional[JudgeConfig] = None):
        self.config = config or JudgeConfig()
        self.cache = JudgeCache(max_size=self.config.cache_max_size)
        self._total_llm_calls = 0
        self._llm_client = None

        # Cache'i diskten yükle
        if self.config.cache_path:
            self.cache.load(self.config.cache_path)

        # Prompt template
        if self.config.prompt_template == "short":
            self._prompt_fn = SHORT_PROMPT_TEMPLATE
        else:
            self._prompt_fn = DEFAULT_PROMPT_TEMPLATE

    def judge(self, claim: str, fact: str,
              embedding_distance: Optional[float] = None) -> JudgeVerdict:
        """
        İki metin arasında çelişki var mı?
        
        1. Önce cache'e bak (deterministik)
        2. LLM yoksa embedding_distance'a göre karar ver
        3. LLM varsa sor (borderline case'lerde)
        4. Sonucu cache'le
        
        Args:
            claim: LLM claim cümlesi
            fact: Rule fact'i
            embedding_distance: Detect() tarafından hesaplanmış embedding distance
                               (varsa, embedding tekrar hesaplanmaz)
        """
        # 1. Cache kontrolü
        cached = self.cache.get(claim, fact)
        if cached is not None:
            return cached

        # 2. Embedding distance verilmişse LLM'e sormaya gerek var mı?
        if embedding_distance is not None:
            if embedding_distance < self.config.similar_threshold:
                verdict = JudgeVerdict(
                    is_conflict=False,
                    reason=f"embedding: d={embedding_distance:.3f} < {self.config.similar_threshold}",
                    confidence=1.0 - embedding_distance,
                )
                self.cache.put(claim, fact, verdict)
                return verdict
            elif embedding_distance > self.config.different_threshold:
                verdict = JudgeVerdict(
                    is_conflict=True,
                    reason=f"embedding: d={embedding_distance:.3f} > {self.config.different_threshold}",
                    confidence=embedding_distance,
                )
                self.cache.put(claim, fact, verdict)
                return verdict
            # Borderline: LLM'e sor
            if self.config.use_llm:
                verdict = self._ask_llm(claim, fact)
                if verdict is not None:
                    self.cache.put(claim, fact, verdict)
                    return verdict
        
        # 3. Embedding distance yok → kendimiz hesapla
        if self.config.use_embedding and embedding_distance is None:
            from anchor.judge.embedding import semantic_distance
            d_emb = semantic_distance(claim, fact)
            if d_emb is not None:
                return self.judge(claim, fact, embedding_distance=d_emb)
        
        # 4. LLM yoksa ve embedding yoksa → güvenli taraf
        verdict = JudgeVerdict(
            is_conflict=True,
            reason="fallback: no signals available",
            confidence=0.0,
        )
        self.cache.put(claim, fact, verdict)
        return verdict

    def _ask_llm(self, claim: str, fact: str) -> Optional[JudgeVerdict]:
        """LLM'e soru sor ve yanıtı parse et."""
        if not self.config.use_llm:
            return None

        # Lazy client initialization
        if self._llm_client is None:
            self._llm_client = self._create_client()

        prompt = self._prompt_fn.format(claim=claim, fact=fact)

        try:
            response = self._llm_client(prompt)
            self._total_llm_calls += 1
            logger.info("LLM judge call #%d: %s", self._total_llm_calls, response[:50])

            # Parse: EVET = conflict, HAYIR = no conflict
            response_clean = response.strip().upper()
            if "EVET" in response_clean:
                return JudgeVerdict(
                    is_conflict=True,
                    reason=f"llm_judge: {response_clean[:30]}",
                    confidence=0.8,
                )
            elif "HAYIR" in response_clean or "NO" in response_clean:
                return JudgeVerdict(
                    is_conflict=False,
                    reason=f"llm_judge: {response_clean[:30]}",
                    confidence=0.8,
                )
            else:
                logger.warning("Unexpected LLM response: %s", response)
                return None

        except Exception as e:
            logger.error("LLM judge call failed: %s", e)
            return None

    def _create_client(self):
        """
        LLM client factory.
        
        Desteklenen provider'lar:
          - openai: OpenAI API
          - anthropic: Anthropic Claude API
          - ollama: Local LLM
          - http: Custom HTTP endpoint
        
        Varsayılan: mock (sadece embedding kullan, LLM yok)
        """
        provider = self.config.llm_provider
        api_key = self.config.llm_api_key or os.getenv("OPENAI_API_KEY")
        model = self.config.llm_model

        if provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            return lambda p: client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": p}],
                temperature=0.0,
                max_tokens=10,
            ).choices[0].message.content

        elif provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            return lambda p: client.messages.create(
                model=model,
                max_tokens=10,
                temperature=0.0,
                messages=[{"role": "user", "content": p}],
            ).content[0].text

        elif provider == "ollama":
            import requests
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            return lambda p: requests.post(
                f"{host}/api/generate",
                json={"model": model, "prompt": p, "stream": False},
                timeout=30,
            ).json().get("response", "")

        elif provider == "mock":
            # Mock: tüm sorgulara EVET döndür
            logger.info("Using mock LLM judge (always returns EVET)")
            return lambda p: "EVET"

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def save_cache(self):
        """Cache'i diske kaydet."""
        if self.config.cache_path:
            self.cache.save(self.config.cache_path)

    @property
    def stats(self) -> dict:
        return {
            "use_embedding": self.config.use_embedding,
            "use_llm": self.config.use_llm,
            "llm_calls": self._total_llm_calls,
            "max_calls": self.config.max_calls_per_session,
            "cache": self.cache.stats,
        }
