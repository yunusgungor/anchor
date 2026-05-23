"""
ANCHOR — LLM Çıktıları için Deterministik Rectification Çerçevesi

Core tanımlar ve tipler.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Severity(Enum):
    """Çelişki şiddet seviyesi."""
    NONE = 0        # Çelişki yok
    INFO = 1        # Ek bilgi var, çelişki yok
    WARNING = 2     # LLM eksik söylemiş
    ERROR = 3       # LLM yanlış söylemiş
    CRITICAL = 4    # KB net, LLM tam tersini söylüyor


@dataclass
class Topic:
    """Çıkarılmış konu."""
    name: str
    confidence: float = 1.0
    source: str = "query"  # query | content | alias | tag


@dataclass
class Rule:
    """Bir rules dosyasını temsil eder."""
    id: str
    topic: str
    content: str
    file_path: str
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    priority: int = 5
    strictness: float = 0.8

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Rule) and self.id == other.id
    
    @classmethod
    def from_file(cls, fpath: Path) -> "Rule":
        """Bir dosyadan Rule oluştur — format-agnostik."""
        from anchor.parser import RuleParser
        
        parser = RuleParser()
        parsed = parser.parse_file(fpath)
        
        return cls(
            id=parsed.id,
            topic=parsed.topic,
            content=parsed.content,
            file_path=str(fpath),
            aliases=parsed.aliases,
            tags=parsed.tags,
            priority=parsed.priority,
            strictness=parsed.strictness,
        )


@dataclass
class Conflict:
    """Tespit edilmiş çelişki."""
    rule_id: str
    topic: str
    severity: Severity
    llm_claim: str          # LLM'in söylediği (eski)
    kb_fact: str            # KB'deki doğru bilgi (eski)
    patch_position: int = 0  # Düzeltmenin yapılacağı pozisyon
    confidence: float = 0.5  # Çelişki tespit güven skoru (0-1)
    # Yeni attribute'lar (detect.py uyumu)
    claim: str = ""         # Alias: llm_claim
    fact: str = ""          # Alias: kb_fact
    distance: float = 0.0
    position: Optional[tuple] = None

    def __post_init__(self):
        """Eski/yeni attribute sync."""
        if self.llm_claim and not self.claim:
            self.claim = self.llm_claim
        if self.kb_fact and not self.fact:
            self.fact = self.kb_fact
        if self.claim and not self.llm_claim:
            self.llm_claim = self.claim
        if self.fact and not self.kb_fact:
            self.kb_fact = self.fact
        if self.patch_position and not self.position:
            self.position = (self.patch_position, self.patch_position + len(self.claim or self.llm_claim))
        elif self.position and not self.patch_position:
            self.patch_position = self.position[0] if self.position else 0


@dataclass
class Correction:
    """Uygulanmış düzeltme."""
    conflict: Conflict
    original_text: str
    corrected_text: str
    edit_distance: int = 0


@dataclass
class RectificationResult:
    """Pipeline çıktısı."""
    original: str
    corrected: str
    corrections: list[Correction] = field(default_factory=list)
    topics_found: list[Topic] = field(default_factory=list)
    rules_activated: list[str] = field(default_factory=list)
    latency_us: dict[str, float] = field(default_factory=dict)
    modified: bool = False

    @property
    def summary(self) -> str:
        if not self.modified:
            return "✅ Hiçbir düzeltme gerekmedi"
        
        total = len(self.corrections)
        by_severity = {}
        for c in self.corrections:
            s = c.conflict.severity.name
            by_severity[s] = by_severity.get(s, 0) + 1
        
        parts = [f"🔧 {total} düzeltme uygulandı"]
        for sev, count in by_severity.items():
            parts.append(f"  {sev}: {count}")
        
        return "\n".join(parts)
