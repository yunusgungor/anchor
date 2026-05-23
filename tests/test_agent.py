"""
Anchor Agent Testleri — SafeLLMAgent, RuleManager.
"""

import os
import pytest
from pathlib import Path

from anchor.agent import SafeLLMAgent, AgentResult, RuleManager
from anchor.agent.llm_client import BaseLLMClient


RULES_PATH = str(Path(__file__).parent.parent / "rules")
INDEX_PATH = str(Path(__file__).parent.parent / ".anchor_agent_test.idx")


class MockLLMClient(BaseLLMClient):
    """Test için mock LLM — deterministik cevaplar."""
    
    def __init__(self, responses: dict[str, str] = None):
        self.responses = responses or {}
    
    def chat(self, prompt: str, system=None) -> str:
        # Soruya göre sabit cevap
        for key, value in self.responses.items():
            if key.lower() in prompt.lower():
                return value
        return f"Mock cevap: {prompt}"
    
    def stream_chat(self, prompt: str, system=None):
        text = self.chat(prompt, system)
        for word in text.split():
            yield word + " "


@pytest.fixture
def mock_agent():
    """Mock LLM ile agent oluştur."""
    # Temizle
    for f in [INDEX_PATH, INDEX_PATH.replace(".idx", ".idx.npz")]:
        if os.path.exists(f):
            os.unlink(f)
    
    agent = SafeLLMAgent(
        rules_path=RULES_PATH,
        llm_provider="openai",
        llm_api_key="mock",
        index_path=INDEX_PATH,
    )
    
    # LLM client'ı mock ile değiştir
    agent.llm._client = MockLLMClient({
        "npx1": "NPX1, genel amaçlı bir AI hızlandırıcısıdır.",
        "tsmc": "NPX1, TSMC'de üretilen bir işlemcidir.",
        "doğru": "NPX1, edge AI işlemcisidir.",
    })
    
    return agent


class TestSafeLLMAgent:
    """SafeLLMAgent testleri."""
    
    def test_ask_with_correction(self, mock_agent):
        """Yanlış bilgi veren LLM → Anchor düzeltmeli."""
        result = mock_agent.ask("NPX1 nedir?")
        
        assert isinstance(result, AgentResult)
        assert result.query == "NPX1 nedir?"
        assert "genel amaçlı" in result.raw.lower()
        assert result.modified == True
        assert result.corrected != result.raw
        assert len(result.corrections) >= 1
        assert result.confidence < 1.0
        assert result.latency_ms > 0
    
    def test_ask_no_correction_needed(self, mock_agent):
        """Exact fact veren LLM → düzeltme gerekmez."""
        # Mock'ı exact rule fact'i verecek şekilde ayarla
        mock_agent.llm._client = MockLLMClient({
            "exact": "**Mimari:** RISC-V + Systolic Array NPU",
        })
        result = mock_agent.ask("exact NPX1 nedir?")
        
        assert result.modified == False
        assert result.confidence == 1.0
    
    def test_ask_report_generated(self, mock_agent):
        """Rapor oluşturulmalı."""
        result = mock_agent.ask("NPX1 nedir?")
        
        assert "Soru:" in result.report
        assert "Topic'ler:" in result.report
        assert "Düzeltme:" in result.report
    
    def test_batch_ask(self, mock_agent):
        """Birden fazla soruyu batch işle."""
        questions = ["NPX1 nedir?", "tsmc NPX1 üretimi"]
        results = mock_agent.batch_ask(questions)
        
        assert len(results) == 2
        for r in results:
            assert isinstance(r, AgentResult)
            assert r.latency_ms > 0
    
    def test_stats(self, mock_agent):
        """Stats çalışmalı."""
        mock_agent.ask("NPX1 nedir?")
        mock_agent.ask("doğru NPX1 nedir?")
        
        stats = mock_agent.stats
        assert stats["total_queries"] == 2
        assert stats["total_modified"] >= 0
        assert "anchor_stats" in stats
    
    def test_stream_ask(self, mock_agent):
        """Streaming çalışmalı."""
        chunks = []
        final = None
        
        for item in mock_agent.ask_stream("NPX1 nedir?"):
            if item["type"] == "chunk":
                chunks.append(item["content"])
            elif item["type"] == "final":
                final = item
        
        assert len(chunks) > 0
        assert final is not None
        assert "corrected" in final


class TestRuleManager:
    """RuleManager testleri."""
    
    def test_list_rules(self):
        """Rule listeleme çalışmalı."""
        rm = RuleManager(RULES_PATH)
        rules = rm.list_rules()
        
        # En az 1 rule bulunmalı (hardware/riscv-npu.md)
        assert len(rules) >= 1, f"Rule bulunamadı. Path: {RULES_PATH}, içerik: {os.listdir(RULES_PATH) if os.path.exists(RULES_PATH) else 'YOK'}"
        assert all("topic" in r for r in rules)
    
    def test_create_and_delete_rule(self):
        """Rule oluştur ve sil."""
        rm = RuleManager("/tmp/anchor_test_rules")
        
        path = rm.create_rule(
            topic="Test Konu",
            aliases=["test"],
            facts={"Özellik": "Değer"},
            confusions={"Yanlış": ("LLM söyler", "Doğrusu")},
            domain="test",
        )
        
        assert os.path.exists(path)
        
        # Oluşturulan rule'u oku
        with open(path) as f:
            content = f.read()
        assert "Test Konu" in content
        assert "Özellik" in content
        
        # Sil
        deleted = rm.delete_rule("test-konu")
        assert deleted == True
    
    def test_suggest_rules(self):
        """Rule önerisi çalışmalı."""
        rm = RuleManager(RULES_PATH)
        suggestions = rm.suggest_rules("TSMC 7nm üretim düğümü hakkında")
        
        assert len(suggestions) >= 1
        assert any("Üretim" in s["reason"] for s in suggestions)
    
    def test_domain_stats(self):
        """Domain istatistikleri."""
        rm = RuleManager(RULES_PATH)
        stats = rm.domain_stats()
        
        assert "hardware" in stats or "projects" in stats or "concepts" in stats
