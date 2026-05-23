"""
Format-Agnostic Rule Parser Testleri.

Her format için parse testi:
  - .md + YAML frontmatter
  - .md düz (akıllı extraction)
  - .txt (düz metin)
  - .json
  - .yaml
  - .csv
"""

import tempfile
from pathlib import Path

import pytest

from anchor.parser import RuleParser, ParsedRule


class TestRuleParser:
    """Format-agnostik parser testleri."""
    
    def test_md_frontmatter(self):
        """YAML frontmatter'lı markdown parse et."""
        parser = RuleParser()
        text = """---
topic: "Neural Processor X1"
aliases: ["NPX1", "npx1"]
tags: [hardware, chip]
priority: 10
strictness: 0.9
---

# Neural Processor X1

Edge AI işlemcisidir.
"""
        parsed = parser.parse_text(text, "riscv-npu.md")
        
        assert parsed.topic == "Neural Processor X1"
        assert "NPX1" in parsed.aliases
        assert parsed.priority == 10
        assert parsed.strictness == 0.9
        assert parsed.source_format == "md_frontmatter"
    
    def test_md_plain(self):
        """Düz markdown — akıllı extraction."""
        parser = RuleParser()
        text = """# Neural Processor X1

Edge AI işlemcisidir.
- RISC-V mimarili
- SKY130 PDK
"""
        parsed = parser.parse_text(text, "riscv-npu.md")
        
        assert parsed.topic == "Neural Processor X1"
        assert "Edge AI" in parsed.content
        assert parsed.source_format == "plain_text"
    
    def test_txt_plain(self):
        """Düz metin dosyası."""
        parser = RuleParser()
        text = """NPX1 — Edge AI İşlemcisi

RISC-V mimarili, SKY130 PDK'da üretilir.
also known as: Neural Processor X1
"""
        parsed = parser.parse_text(text, "npx1.txt")
        
        assert "NPX1" in parsed.topic
        assert any("Neural Processor" in a for a in parsed.aliases)
        assert parsed.source_format == "plain_text"
    
    def test_json(self):
        """JSON formatı."""
        parser = RuleParser()
        text = """{
    "topic": "SKY130 PDK",
    "aliases": ["sky130", "130nm"],
    "content": "Açık kaynak PDK",
    "priority": 8
}"""
        parsed = parser.parse_text(text, "sky130.json")
        
        assert parsed.topic == "SKY130 PDK"
        assert parsed.priority == 8
        assert parsed.source_format == "json"
    
    def test_yaml(self):
        """YAML formatı."""
        pytest.importorskip("yaml")
        
        parser = RuleParser()
        text = """topic: StateGuard Agent
aliases:
  - StateGuard
  - SG
priority: 9
content: |
  LLM operatörü ve orkestratörü.
"""
        parsed = parser.parse_text(text, "state-guard.yaml")
        
        assert parsed.topic == "StateGuard Agent"
        assert "StateGuard" in parsed.aliases
        assert parsed.priority == 9
        assert parsed.source_format == "yaml"
    
    def test_csv(self):
        """CSV formatı."""
        parser = RuleParser()
        text = """topic,fact1,fact2
NPX1,RISC-V,Edge AI
SKY130,130nm,OpenLane
"""
        parsed = parser.parse_text(text, "chips.csv")
        
        assert parsed.topic == "NPX1"
        assert parsed.source_format == "csv"
    
    def test_file_parse(self):
        """Gerçek dosyadan parse et."""
        parser = RuleParser()
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# Test Topic\n\nSome facts here.\n")
            tmp_path = f.name
        
        parsed = parser.parse_file(Path(tmp_path))
        
        assert parsed.topic == "Test Topic"
        assert "facts" in parsed.content
        
        Path(tmp_path).unlink()
    
    def test_alias_extraction_parentheses(self):
        """Parantez içi alias tespiti."""
        parser = RuleParser()
        text = "NPX1 (Neural Processor X1) — Edge AI işlemcisi"
        parsed = parser.parse_text(text, "test.txt")
        
        assert any("Neural Processor" in a for a in parsed.aliases)
    
    def test_tag_extraction_hashtag(self):
        """#hashtag tag tespiti."""
        parser = RuleParser()
        text = "#hardware #chip #riscv NPX1 işlemci"
        parsed = parser.parse_text(text, "test.txt")
        
        assert "hardware" in parsed.tags
        assert "chip" in parsed.tags
        assert "riscv" in parsed.tags


class TestRuleFromFileIntegration:
    """Rule.from_file() ile parser entegrasyonu."""
    
    def test_rule_from_txt_file(self):
        """.txt dosyasından Rule oluştur."""
        from anchor import Rule
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# My Chip\n\nRISC-V based.\n")
            tmp_path = f.name
        
        rule = Rule.from_file(Path(tmp_path))
        
        assert rule.topic == "My Chip"
        assert "RISC-V" in rule.content
        
        Path(tmp_path).unlink()
    
    def test_rule_from_json_file(self):
        """.json dosyasından Rule oluştur."""
        from anchor import Rule
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write('{"topic": "JSON Rule", "priority": 7}')
            tmp_path = f.name
        
        rule = Rule.from_file(Path(tmp_path))
        
        assert rule.topic == "JSON Rule"
        assert rule.priority == 7
        
        Path(tmp_path).unlink()
