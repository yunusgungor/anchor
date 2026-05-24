"""
Rule Enricher — Build-time rule enrichment using LLM.

Phase 3: Her rule'daki fact'lerin paraphrase'leri build-time'da
LLM tarafından üretilir ve binary index'e kaydedilir.

Runtime'da SIFIR LLM çağrısı — tüm paraphrase'lar hazır.

Kullanım:
    from anchor.judge.enricher import RuleEnricher

    enricher = RuleEnricher(llm_provider="openai")
    enriched = enricher.enrich_facts(["SKY130'da üretiliyor", ...])
    # → ["SKY130'da üretiliyor", "SKY130 ile üretilir", ...]
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Varsayılan prompt — Türkçe teknik metinler için
DEFAULT_PROMPT = (
    "Aşağıdaki teknik ifadeyi anlamını BOZMADAN "
    "{count} farklı şekilde yeniden yaz. "
    "Her paraphrase'ı ayrı bir satıra yaz. "
    "Sadece paraphrase'lar, ek açıklama yok, numara yok.\n\n"
    'Orijinal: "{fact}"\n'
    "Paraphrase'lar:"
)

# İngilizce prompt (opsiyonel)
EN_PROMPT = (
    "Rewrite the following technical statement in {count} different ways "
    "without changing its meaning. "
    "One paraphrase per line. "
    "Only the paraphrases, no explanations or numbering.\n\n"
    'Original: "{fact}"\n'
    "Paraphrases:"
)


class RuleEnricher:
    """
    Build-time rule enricher.
    
    Her rule'daki fact'lerin paraphrase'lerini üretir.
    Sonuçlar binary index'e kaydedilir, runtime'da kullanılır.
    
    Args:
        llm_provider: "openai", "anthropic", "ollama", "mock"
        llm_model: Model adı
        llm_api_key: API key (None = env var)
        paraphrases_per_fact: Her fact için kaç paraphrase (default: 3)
        prompt_template: "default" veya "en"
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4o-mini",
        llm_api_key: Optional[str] = None,
        paraphrases_per_fact: int = 3,
        prompt_template: str = "default",
    ):
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.paraphrases_per_fact = paraphrases_per_fact
        self._client = None
        self._total_calls = 0

        if prompt_template == "en":
            self._prompt = EN_PROMPT
        else:
            self._prompt = DEFAULT_PROMPT

    def enrich_facts(self, facts: list[str]) -> list[str]:
        """
        Fact listesini genişlet: orijinal + paraphrase'lar.

        Args:
            facts: Rule'dan extracted orijinal fact'ler

        Returns:
            Tüm fact'ler (orijinal + paraphrase'lar)
        """
        enriched = []
        for fact in facts:
            enriched.append(fact)  # orijinal
            if self._client is not None or self.llm_provider != "mock":
                paraphrases = self._generate_paraphrases(fact)
                enriched.extend(paraphrases)
            else:
                # Mock: faktüel olarak doğru olanı koru
                enriched.append(fact)
        return enriched

    def enrich_rule(self, rule_content: str) -> list[str]:
        """
        Bir rule dosyasının tüm fact'lerini genişlet.

        Args:
            rule_content: Rule içeriği (markdown)

        Returns:
            enriched_facts: Tüm fact'ler (orijinal + paraphrase'lar)
        """
        from anchor.detect import ConflictDetector
        det = ConflictDetector()
        facts = det._extract_facts(rule_content)
        return self.enrich_facts(facts)

    def _generate_paraphrases(self, fact: str) -> list[str]:
        """Bir fact için paraphrase'lar üret."""
        if len(fact) < 10:
            return []

        prompt = self._prompt.format(
            fact=fact,
            count=self.paraphrases_per_fact,
        )

        try:
            response = self._call_llm(prompt)
            self._total_calls += 1

            # Her satırı paraphrase olarak al
            lines = []
            for line in response.strip().split("\n"):
                line = line.strip().strip('"').strip("'").strip("- ").strip("* ")
                # Numara varsa temizle: "1. paraphrase" → "paraphrase"
                line = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                if line and len(line) > 5 and line != fact:
                    lines.append(line)

            logger.debug("Generated %d paraphrases for fact: %s", len(lines), fact[:40])
            return lines[:self.paraphrases_per_fact]

        except Exception as e:
            logger.warning("Paraphrase generation failed for '%s': %s", fact[:30], e)
            return []

    def _call_llm(self, prompt: str) -> str:
        """LLM'e istek gönder."""
        if self.llm_provider == "mock":
            # Mock: orijinalin aynısını döndür
            return prompt.split('"')[1] if '"' in prompt else "mock"

        if self._client is None:
            self._client = self._create_client()

        return self._client(prompt)

    def _create_client(self):
        """LLM client factory."""
        api_key = self.llm_api_key or os.getenv("OPENAI_API_KEY")

        if self.llm_provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            return lambda p: client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": p}],
                temperature=0.3,
                max_tokens=200,
            ).choices[0].message.content

        elif self.llm_provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            return lambda p: client.messages.create(
                model=self.llm_model,
                max_tokens=200,
                temperature=0.3,
                messages=[{"role": "user", "content": p}],
            ).content[0].text

        elif self.llm_provider == "ollama":
            import requests
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            return lambda p: requests.post(
                f"{host}/api/generate",
                json={"model": self.llm_model, "prompt": p, "stream": False},
                timeout=30,
            ).json().get("response", "")

        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")

    @property
    def stats(self) -> dict:
        return {
            "provider": self.llm_provider,
            "model": self.llm_model,
            "paraphrases_per_fact": self.paraphrases_per_fact,
            "total_llm_calls": self._total_calls,
        }
