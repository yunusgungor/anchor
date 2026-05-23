"""
Anchor Agent — Anchor-özgü AI Agent.

Bileşenler:
  - SafeLLMAgent: LLM + Anchor wrapper
  - LLMClient: OpenAI, Claude, Ollama abstraction
  - RuleManager: Rules CRUD + öneri

Kullanım:
    from anchor.agent import SafeLLMAgent
    
    agent = SafeLLMAgent(
        rules_path="rules/",
        llm_provider="openai",
        llm_api_key="sk-..."
    )
    
    result = agent.ask("NPX1 nedir?")
    print(result.corrected)
    print(result.report)
"""

from .safe_llm import SafeLLMAgent, AgentResult
from .llm_client import LLMClient
from .rule_manager import RuleManager

__all__ = ["SafeLLMAgent", "AgentResult", "LLMClient", "RuleManager"]
