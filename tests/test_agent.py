"""
Anchor AI Agent — SafeLLMAgent testleri.
"""

import pytest
from pathlib import Path

from anchor.agent import SafeLLMAgent, AgentResult
from anchor.agent.llm_client import LLMClient

RULES_PATH = str(Path(__file__).parent.parent / "rules")


class MockLLMClient:
    """LLM API çağrısı yapmadan test."""

    def __init__(self, response_text: str = "Test cevap"):
        self.response_text = response_text
        self._total_calls = 0
        self._total_latency = 0

    def chat(self, prompt: str, system=None) -> str:
        self._total_calls += 1
        return self.response_text

    def stream_chat(self, prompt: str, system=None):
        words = self.response_text.split()
        for word in words:
            yield word + " "


class TestSafeLLMAgent:
    @pytest.fixture
    def mock_agent(self):
        mock_client = MockLLMClient("correct")
        agent = SafeLLMAgent(rules_path=RULES_PATH, llm_client=mock_client)
        yield agent

    def test_ask_no_correction(self, mock_agent):
        mock_agent.llm = MockLLMClient("correct")
        result = mock_agent.ask("Merhaba")
        assert isinstance(result, AgentResult)
        assert result.confidence >= 0

    def test_ask_stream(self, mock_agent):
        chunks = list(mock_agent.ask_stream("Test"))
        assert len(chunks) > 0

    def test_batch_ask(self, mock_agent):
        results = mock_agent.batch_ask(["Soru 1", "Soru 2"])
        assert len(results) == 2

    def test_stats(self, mock_agent):
        mock_agent.ask("Test")
        stats = mock_agent.stats
        assert "total_queries" in stats
