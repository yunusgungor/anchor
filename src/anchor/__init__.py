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
        """Bir .md dosyasından Rule oluştur."""
        text = fpath.read_text(encoding="utf-8")
        rule_id = fpath.stem
        
        fm = {}
        content = text
        
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                content = parts[2]
                
                for line in fm_text.split("\n"):
                    if ":" in line:
                        key, _, val = line.partition(":")
                        key = key.strip()
                        val = val.strip()
                        
                        if val.startswith("[") and val.endswith("]"):
                            val = [v.strip().strip("'\"") for v in val[1:-1].split(",")]
                        elif val.isdigit():
                            val = int(val)
                        elif val.replace(".", "").isdigit():
                            val = float(val)
                        
                        fm[key] = val
        
        return cls(
            id=rule_id,
            topic=fm.get("topic", rule_id),
            content=content,
            file_path=str(fpath),
            aliases=fm.get("aliases", []),
            tags=fm.get("tags", []),
            priority=fm.get("priority", 5),
            strictness=fm.get("strictness", 0.8),
        )


@dataclass
class Conflict:
    """Tespit edilmiş çelişki."""
    rule_id: str
    topic: str
    severity: Severity
    llm_claim: str          # LLM'in söylediği
    kb_fact: str            # KB'deki doğru bilgi
    patch_position: int = 0  # Düzeltmenin yapılacağı pozisyon
    confidence: float = 0.5  # Çelişki tespit güven skoru (0-1)


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
