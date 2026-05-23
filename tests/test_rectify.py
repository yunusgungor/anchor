"""
Anchor Rectification — PatchEngine testleri.
"""

import pytest
from anchor.rectify import PatchEngine, PatchStrategy
from anchor import Conflict, Severity


class TestPatchEngine:
    @pytest.fixture
    def patcher(self):
        return PatchEngine()

    def test_no_conflict_no_change(self, patcher):
        text, patches = patcher.apply("Hiçbir çelişki yok.", [])
        assert text == "Hiçbir çelişki yok."
        assert len(patches) == 0

    def test_critical_override(self, patcher):
        conflict = Conflict(
            rule_id="test", topic="NPX1",
            severity=Severity.CRITICAL,
            llm_claim="NPX1, TSMC'de.",
            kb_fact="SKY130'da üretiliyor.",
        )
        text, patches = patcher.apply("NPX1, TSMC'de.", [conflict])
        assert "SKY130" in text
        assert len(patches) == 1
        assert patches[0].strategy == PatchStrategy.OVERRIDE_SENTENCE

    def test_error_patch(self, patcher):
        conflict = Conflict(
            rule_id="test", topic="NPX1",
            severity=Severity.ERROR,
            llm_claim="NPX1, genel amaçlı.",
            kb_fact="Edge AI.",
        )
        text, patches = patcher.apply("NPX1, genel amaçlı.", [conflict])
        assert "doğrusu" in text
        assert len(patches) == 1
        assert patches[0].strategy == PatchStrategy.PATCH_SENTENCE

    def test_multiple_conflicts(self, patcher):
        c1 = Conflict(
            rule_id="a", topic="NPX1",
            severity=Severity.CRITICAL,
            llm_claim="TSMC.", kb_fact="SKY130.",
        )
        c2 = Conflict(
            rule_id="b", topic="NPX1",
            severity=Severity.ERROR,
            llm_claim="genel.", kb_fact="Edge.",
        )
        text, patches = patcher.apply("NPX1, TSMC. genel.", [c1, c2])
        assert len(patches) == 2

    def test_latency_budget(self, patcher):
        c = Conflict(
            rule_id="test", topic="NPX1",
            severity=Severity.CRITICAL,
            llm_claim="a", kb_fact="b",
        )
        patcher.apply("a", [c])
        assert patcher.avg_latency_us < 10_000  # < 10ms
