"""
LLM Client — Farklı LLM provider'ları için unified interface.

Desteklenen provider'lar:
  - openai (GPT-4, GPT-3.5)
  - anthropic (Claude)
  - ollama (Lokal: Llama, Mistral, vb.)
  - http (Generic HTTP POST API)

Kullanım:
    client = LLMClient(provider="openai", api_key="...")
    response = client.chat("NPX1 nedir?")
    # → "NPX1, genel amaçlı bir AI hızlandırıcısıdır..."
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMClient(ABC):
    """Tüm LLM client'ların implemente etmesi gereken arayüz."""
    
    @abstractmethod
    def chat(self, prompt: str, system: Optional[str] = None) -> str:
        """Tek mesajlı chat."""
        pass
    
    @abstractmethod
    def stream_chat(self, prompt: str, system: Optional[str] = None):
        """Streaming chat — chunk'lar döndürür."""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        
        if not self.api_key:
            raise ValueError("OpenAI API key gerekli. OPENAI_API_KEY env var veya api_key parametresi.")
    
    def chat(self, prompt: str, system: Optional[str] = None) -> str:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"OpenAI API hatası: {e}")
    
    def stream_chat(self, prompt: str, system: Optional[str] = None):
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise RuntimeError(f"OpenAI streaming hatası: {e}")


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        
        if not self.api_key:
            raise ValueError("Anthropic API key gerekli.")
    
    def chat(self, prompt: str, system: Optional[str] = None) -> str:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            
            kwargs = {"model": self.model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}
            if system:
                kwargs["system"] = system
            
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            raise RuntimeError(f"Anthropic API hatası: {e}")
    
    def stream_chat(self, prompt: str, system: Optional[str] = None):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            
            kwargs = {"model": self.model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}
            if system:
                kwargs["system"] = system
            
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            raise RuntimeError(f"Anthropic streaming hatası: {e}")


class OllamaClient(BaseLLMClient):
    """Ollama lokal LLM client."""
    
    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3"):
        self.host = host.rstrip("/")
        self.model = model
    
    def chat(self, prompt: str, system: Optional[str] = None) -> str:
        import requests
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
        }
        
        try:
            response = requests.post(f"{self.host}/api/generate", json=payload, timeout=60)
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            raise RuntimeError(f"Ollama hatası: {e}")
    
    def stream_chat(self, prompt: str, system: Optional[str] = None):
        import requests
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or "",
            "stream": True,
        }
        
        try:
            response = requests.post(f"{self.host}/api/generate", json=payload, stream=True, timeout=60)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
        except Exception as e:
            raise RuntimeError(f"Ollama streaming hatası: {e}")


class LLMClient:
    """
    Unified LLM client factory.
    
    Kullanım:
        client = LLMClient(provider="openai", api_key="sk-...")
        text = client.chat("Merhaba")
    """
    
    PROVIDERS = {
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
        "ollama": OllamaClient,
    }
    
    def __init__(self, provider: str = "openai", **kwargs):
        if provider not in self.PROVIDERS:
            raise ValueError(f"Bilinmeyen provider: {provider}. Desteklenen: {list(self.PROVIDERS.keys())}")
        
        self._client = self.PROVIDERS[provider](**kwargs)
        self.provider = provider
    
    def chat(self, prompt: str, system: Optional[str] = None) -> str:
        return self._client.chat(prompt, system)
    
    def stream_chat(self, prompt: str, system: Optional[str] = None):
        yield from self._client.stream_chat(prompt, system)
