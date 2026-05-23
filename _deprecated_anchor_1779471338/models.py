"""
Anchor: Veri Modelleri

LLM'den bağımsız, tüm pipeline'da kullanılan veri yapıları.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Severity(Enum):
    """Çelişkinin ciddiyet seviyesi."""
    INFO = "info"          # Ek bilgi var, çelişki yok
    WARNING = "warning"    # LLM eksik söylemiş
    ERROR = "error"        # LLM yanlış söylemiş
    CRITICAL = "critical"  # KB net, LLM tam tersini söylüyor


@dataclass
class Topic:
    """Bir konuyu temsil eder."""
    name: str
    aliases: list[str] = field(default_factory=list)
    confidence: float = 1.0  # 0.0 - 1.0 arası


@dataclass
class Rule:
    """
    Bir rules dosyasını (.md) temsil eder.
    
    Attributes:
        id: Benzersiz rule tanımlayıcısı (dosya adı)
        topic: Ana konu
        content: Full .md içeriği
        aliases: Alternatif isimler
        tags: Etiketler
        priority: Öncelik (yüksek = daha baskın)
        strictness: Ne kadar zorla düzeltileceği (0.0 - 1.0)
        version: Rule versiyonu
        path: Kaynak dosya yolu
    """
    id: str
    topic: str
    content: str
    path: Path
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    priority: int = 5
    strictness: float = 0.8
    version: str = "1.0"
    embedding: Optional[list[float]] = None  # Opsiyonel semantic embedding
    
    @classmethod
    def from_file(cls, path: Path) -> "Rule":
        """Bir .md dosyasından Rule nesnesi oluşturur."""
        text = path.read_text(encoding="utf-8")
        
        # YAML frontmatter parse
        frontmatter, content = cls._parse_frontmatter(text)
        
        return cls(
            id=path.stem,
            topic=frontmatter.get("topic", path.stem),
            content=content,
            path=path,
            aliases=frontmatter.get("aliases", []),
            tags=frontmatter.get("tags", []),
            priority=int(frontmatter.get("priority", 5)),
            strictness=float(frontmatter.get("strictness", 0.8)),
            version=frontmatter.get("version", "1.0"),
        )
    
    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict, str]:
        """YAML frontmatter'ı ayıklar."""
        fm = {}
        content = text
        
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                content = parts[2].strip()
                
                for line in fm_text.split("\n"):
                    if ":" in line:
                        key, _, val = line.partition(":")
                        key = key.strip()
                        val = val.strip()
                        
                        # List parsing
                        if val.startswith("[") and val.endswith("]"):
                            val = [v.strip().strip("'\"") for v in val[1:-1].split(",")]
                        # Integer parsing
                        elif val.isdigit():
                            val = int(val)
                        # Float parsing
                        elif val.replace(".", "").isdigit():
                            val = float(val)
                        
                        fm[key] = val
        
        return fm, content


@dataclass
class Conflict:
    """
    LLM çıktısı ile rule arasındaki çelişki.
    
    Attributes:
        rule_id: Hangi rule ile çelişki?
        topic: Hangi konuda?
        llm_claim: LLM'in söylediği
        correct_fact: Rule'daki doğru bilgi
        severity: Çelişki ciddiyeti
        confidence: Tespit güveni
        context: Bağlam (opsiyonel)
    """
    rule_id: str
    topic: str
    llm_claim: str
    correct_fact: str
    severity: Severity
    confidence: float
    context: Optional[str] = None
    
    def summary(self) -> str:
        """İnsan okunabilir özet."""
        icon = {
            Severity.INFO: "ℹ️",
            Severity.WARNING: "⚠️",
            Severity.ERROR: "❌",
            Severity.CRITICAL: "🚫",
        }[self.severity]
        
        return f"{icon} [{self.topic}] {self.llm_claim[:60]}... → {self.correct_fact[:60]}..."


@dataclass
class RectificationResult:
    """Rectification işleminin sonucu."""
    original_text: str
    corrected_text: str
    conflicts: list[Conflict]
    modified: bool
    latency_ms: float
    rules_consulted: list[str]
    confidence: float  # 0.0 - 1.0, düzeltmenin ne kadar güvenilir olduğu
