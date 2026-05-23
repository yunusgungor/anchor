"""
Anchor Engine — End-to-end pipeline testleri.
"""

import pytest
from pathlib import Path

from anchor.engine import AnchorEngine

RULES_PATH = str(Path(__file__).parent.parent / "rules")
INDEX_PATH = str(Path(__file__).parent.parent / ".anchor_test.idx")


class TestAnchorEngine:
    @pytest.fixture
    def engine(self):
        e = AnchorEngine(rules_path=RULES_PATH, index_path=INDEX_PATH)
        e.build()
        yield e

    def test_no_topic_no_change(self, engine):
        result = engine.process(
            user_query="Hava nasıl?",
            llm_output="Bugün güneşli."
        )
        assert not result.modified
        assert result.corrected == "Bugün güneşli."

    def test_critical_conflict_override(self, engine):
        result = engine.process(
            user_query="NPX1 nedir?",
            llm_output="NPX1, TSMC 7nm'de üretilir."
        )
        assert result.modified
        assert "SKY130" in result.corrected

    def test_latency_budget(self, engine):
        result = engine.process(
            user_query="NPX1 nedir?",
            llm_output="NPX1 hakkında bilgi."
        )
        total = result.latency_us.get('total', 0)
        assert total < 100_000  # < 100ms

    def test_stats(self, engine):
        engine.process("NPX1 nedir?", "NPX1, Edge AI.")
        stats = engine.stats
        assert "engine" in stats
        assert "total_processed" in stats["engine"]
