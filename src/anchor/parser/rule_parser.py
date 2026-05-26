"""
Rule Parser — Format-agnostik kural dosyası parser'ı.

Her türlü dosyayı otomatik tespit edip, normalize edilmiş Rule objesine çevirir.

Desteklenen formatlar:
  1. .md + YAML frontmatter (mevcut)
  2. .md (düz markdown — akıllı extraction)
  3. .txt (düz metin — akıllı extraction)
  4. .json (yapılandırılmış)
  5. .yaml / .yml (yapılandırılmış)
  6. .csv (tablo)

Kullanım:
    parser = RuleParser()
    rule = parser.parse_file("/path/to/rules.txt")
    # veya
    rule = parser.parse_text(text_content, filename="rules.txt")
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json
import re

from anchor.parser.frontmatter import (
    parse_frontmatter,
    extract_content,
    extract_metadata,
)


@dataclass
class ParsedRule:
    """Normalize edilmiş kural çıktısı."""
    id: str
    topic: str
    content: str
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    priority: int = 5
    strictness: float = 0.8
    source_format: str = ""  # "md_frontmatter", "plain_text", "json", "yaml", "csv"
    steps: list = field(default_factory=list)  # v4.0: workflow adımları
    domain: str = ""
    rule_type: str = "domain"  # v1.2.0: domain | workflow | hybrid


class RuleParser:
    """
    Format-agnostik rule parser.
    
    Kullanıcı herhangi bir format yazabilir — parser otomatik anlar.
    """
    
    def parse_file(self, fpath: Path) -> ParsedRule:
        """Dosyayı oku, formatını tespit et, parse et."""
        text = fpath.read_text(encoding="utf-8")
        parsed = self.parse_text(text, filename=fpath.name)
        try:
            rel_parent = Path(fpath).parent.name
            if rel_parent and rel_parent != ".":
                parsed.domain = rel_parent
        except Exception:
            pass
        return parsed
    
    def parse_text(self, text: str, filename: str) -> ParsedRule:
        """Metni parse et — formatı otomatik tespit."""
        rule_id = Path(filename).stem
        ext = Path(filename).suffix.lower()
        
        # 1. JSON
        if ext in (".json",):
            return self._parse_json(text, rule_id)
        
        # 2. YAML
        if ext in (".yaml", ".yml"):
            return self._parse_yaml(text, rule_id)
        
        # 3. CSV
        if ext in (".csv",):
            return self._parse_csv(text, rule_id)
        
        # 4. Markdown veya düz metin — akıllı tespit
        return self._parse_smart(text, rule_id)
    
    def _parse_json(self, text: str, rule_id: str) -> ParsedRule:
        """JSON formatını parse et."""
        data = json.loads(text)
        
        if isinstance(data, dict):
            return ParsedRule(
                id=rule_id,
                topic=data.get("topic", rule_id),
                content=data.get("content", ""),
                aliases=data.get("aliases", []),
                tags=data.get("tags", []),
                priority=data.get("priority", 5),
                strictness=data.get("strictness", 0.8),
                source_format="json",
                domain=data.get("domain", ""),
            )
        
        return ParsedRule(
            id=rule_id,
            topic=rule_id,
            content=text,
            source_format="json",
        )
    
    def _parse_yaml(self, text: str, rule_id: str) -> ParsedRule:
        """YAML formatını parse et."""
        try:
            import yaml
            data = yaml.safe_load(text)
            
            if isinstance(data, dict):
                return ParsedRule(
                    id=rule_id,
                    topic=data.get("topic", rule_id),
                    content=data.get("content", ""),
                    aliases=data.get("aliases", []),
                    tags=data.get("tags", []),
                    priority=data.get("priority", 5),
                    strictness=data.get("strictness", 0.8),
                    source_format="yaml",
                    domain=data.get("domain", ""),
                )
        except ImportError:
            pass
        
        return ParsedRule(
            id=rule_id,
            topic=rule_id,
            content=text,
            source_format="yaml_fallback",
        )
    
    def _parse_csv(self, text: str, rule_id: str) -> ParsedRule:
        """CSV formatını parse et."""
        import csv
        import io
        
        lines = text.strip().split("\n")
        if not lines:
            return ParsedRule(id=rule_id, topic=rule_id, content="", source_format="csv")
        
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        
        if rows:
            first = rows[0]
            topic = first.get("topic", rule_id)
            content = "\n".join(
                f"{k}: {v}" for k, v in first.items() if k != "topic"
            )
            
            return ParsedRule(
                id=rule_id,
                topic=topic,
                content=content,
                source_format="csv",
                domain=first.get("domain", ""),
            )
        
        return ParsedRule(id=rule_id, topic=rule_id, content=text, source_format="csv")
    
    def _parse_smart(self, text: str, rule_id: str) -> ParsedRule:
        """
        Akıllı parser — düz metin veya markdown.
        
        Strateji:
          1. YAML frontmatter var mı? → Mevcut parser
          2. Yoksa → Akıllı extraction (topic, facts, confusions)
        """
        from anchor.parser.frontmatter import parse_frontmatter
        
        fm = parse_frontmatter(text)
        if fm:
            return self._parse_frontmatter(text, rule_id, fm)
        
        return self._parse_plain(text, rule_id)
    
    def _parse_frontmatter(self, text: str, rule_id: str, fm: dict | None = None) -> ParsedRule:
        """YAML frontmatter'lı markdown parse et (utility kullanır)."""
        from anchor.parser.frontmatter import parse_frontmatter, extract_content, extract_metadata
        
        if fm is None:
            fm = parse_frontmatter(text)
        
        content = extract_content(text)
        meta = extract_metadata(text, rule_id)
        
        # Steps from frontmatter
        steps = fm.get("steps", [])
        from anchor import Step
        normalized = []
        if isinstance(steps, list):
            for s in steps:
                if isinstance(s, dict) and "id" in s:
                    normalized.append(Step(
                        id=s["id"],
                        title=s.get("title", s["id"]),
                        mandatory=s.get("mandatory", True),
                        depends_on=s.get("depends_on", []),
                        options=s.get("options", []),
                        checks=s.get("checks", []),
                        aliases=s.get("aliases", []),
                    ))
        
        return ParsedRule(
            id=rule_id,
            topic=meta["topic"],
            content=content,
            aliases=meta["aliases"],
            tags=meta["tags"],
            priority=meta["priority"],
            strictness=meta["strictness"],
            source_format="md_frontmatter",
            steps=normalized,
            domain=fm.get("domain", ""),
            rule_type=fm.get("type", "domain"),
        )
    
    def _parse_plain(self, text: str, rule_id: str) -> ParsedRule:
        """
        Düz metin dosyası — akıllı extraction.
        
        Başlıkları, madde işaretlerini, kalın metinleri analiz ederek
        topic, facts, confusions çıkarır.
        """
        lines = text.strip().split("\n")
        
        topic = rule_id
        if lines:
            first = lines[0].strip()
            if first.startswith("#"):
                topic = first.lstrip("#").strip()
            elif first.startswith("**") and first.endswith("**"):
                topic = first.strip("*")
            elif len(first) < 80 and not first.startswith(("-", "*", ">")):
                topic = first
        
        aliases = []
        for match in re.finditer(r'\(([A-Z]{2,6})\)', text):
            alias = match.group(1).strip()
            if alias and alias not in aliases:
                aliases.append(alias)
        for match in re.finditer(r'\(([A-Z][a-zA-Z0-9\s_-]{2,48})\)', text):
            alias = match.group(1).strip()
            if (alias and alias not in aliases 
                and len(alias) >= 3 and len(alias) <= 40
                and not any(w in alias.lower() for w in ['e.g', 'i.e', 'aka', 'etc'])):
                aliases.append(alias)
        for pattern in [r'also known as[::\s]+([^,\n]+)', r'aka[::\s]+([^,\n]+)']:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                alias = match.group(1).strip().strip('"\'')
                if alias and len(alias) > 2 and alias not in aliases:
                    aliases.append(alias)
        
        tags = list(set(re.findall(r"#([a-zA-Z0-9_]+)", text)))
        
        return ParsedRule(
            id=rule_id,
            topic=topic,
            content=text,
            aliases=aliases,
            tags=tags,
            priority=5,
            strictness=0.8,
            source_format="plain_text",
        )
