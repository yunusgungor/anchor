"""
Format-Agnostic Rule Parser — Her türlü kural dosyasını parse et.

Desteklenen formatlar:
  - .md (YAML frontmatter'lı veya düz markdown)
  - .txt (düz metin)
  - .json (yapılandırılmış JSON)
  - .yaml / .yml (yapılandırılmış YAML)
  - .csv (tablo formatı)

Auto-detect: Dosya uzantısına ve içeriğine göre format tespit.
"""

from .rule_parser import RuleParser, ParsedRule

__all__ = ["RuleParser", "ParsedRule"]
