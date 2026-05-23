"""
Anchor: Deterministic Rectification of LLM Outputs

Bağımsız bilimsel araştırma projesi.
Hiçbir LLM çağırmadan, LLM çıktılarını kullanıcının bilgi tabanına göre düzeltir.
"""

from .models import Rule, Conflict, ProcessedOutput, Topic
from .index import RuleIndex
from .topic_extractor import TopicExtractor
from .conflict_detector import ConflictDetector
from .rectifier import KnowledgeEngine, RectificationResult

__version__ = "0.1.0"
__all__ = [
    "Rule", "Conflict", "ProcessedOutput", "Topic",
    "RuleIndex", "TopicExtractor", "ConflictDetector",
    "KnowledgeEngine", "RectificationResult",
]
