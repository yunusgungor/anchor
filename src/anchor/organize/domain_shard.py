"""
Domain Sharding — Rule'ları domain'lere bölerek O(1) shard routing.

Mimari:
  rules/
    ├── _index.yaml          → Shard manifest (hangi topic hangi shard'ta)
    ├── hardware/
    │   ├── chip/
    │   │   └── riscv-npu.md
    │   └── sky130-pdk.md
    ├── software/
    │   └── state-guard.md
    └── concepts/
        └── architectural-sovereignty.md

Router, topic → shard_path eşlemesini O(1) hash lookup ile yapar.
"""

import fnmatch
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DomainShard:
    """Bir domain klasörünü temsil eder."""
    name: str
    path: Path
    patterns: list[str] = field(default_factory=list)
    # Ön yüklü metadata (diskten tekrar parse etmemek için)
    topic_count: int = 0
    file_count: int = 0


class ShardRouter:
    """
    Topic → DomainShard eşlemesi.
    
    Strateji:
      1. Önce exact topic → shard mapping (hash)
      2. Yoksa pattern matching (glob)
      3. Hâlâ yoksa → default shard (veya None)
    """
    
    def __init__(self, rules_root: str):
        self.root = Path(rules_root)
        self._topic_map: dict[str, str] = {}      # topic → shard_name
        self._pattern_map: list[tuple[str, str]] = []  # (glob, shard_name)
        self._shards: dict[str, DomainShard] = {}
        
        self._discover_shards()
    
    def _discover_shards(self):
        """Rules root altındaki tüm klasörleri shard olarak tanı."""
        if not self.root.exists():
            return
        
        for subdir in self.root.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("_") and not subdir.name.startswith("."):
                shard = DomainShard(
                    name=subdir.name,
                    path=subdir,
                )
                self._shards[shard.name] = shard
                
                # Her shard altındaki .md dosyalarını tara → topic mapping
                for md_file in subdir.rglob("*.md"):
                    topic = self._extract_topic(md_file)
                    aliases = self._extract_aliases(md_file)
                    if topic:
                        self._topic_map[topic.lower()] = shard.name
                        # Ayrıca dosya adı da bir topic olabilir
                        self._topic_map[md_file.stem.lower()] = shard.name
                        for alias in aliases:
                            self._topic_map[alias.lower()] = shard.name
    
    def _extract_aliases(self, md_file: Path) -> list[str]:
        """Bir .md dosyasının frontmatter'ından alias'ları çıkar."""
        try:
            text = md_file.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1].strip()
                    for line in fm_text.split("\n"):
                        line = line.strip()
                        if line.startswith("aliases:"):
                            val = line.split(":", 1)[1].strip()
                            if val.startswith("[") and val.endswith("]"):
                                return [a.strip().strip('"').strip("'") for a in val[1:-1].split(",")]
                            else:
                                return [val.strip('"').strip("'")]
        except Exception:
            pass
        return []
    
    def _extract_topic(self, md_file: Path) -> Optional[str]:
        """Bir .md dosyasının frontmatter'ından topic çıkar."""
        try:
            text = md_file.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1].strip()
                    for line in fm_text.split("\n"):
                        if line.strip().startswith("topic:"):
                            return line.split(":", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
        return None
    
    def route(self, topics: list[str]) -> set[str]:
        """
        Topic listesinden ilgili shard adlarını bul.
        
        Returns:
            Etkinleştirilecek shard isimleri.
        """
        shards_needed = set()
        
        for topic in topics:
            topic_lower = topic.lower()
            
            # 1. Exact match
            if topic_lower in self._topic_map:
                shards_needed.add(self._topic_map[topic_lower])
                continue
            
            # 2. Stem match (topic içinde boşluk varsa son kelime)
            parts = topic_lower.split()
            for i in range(len(parts)):
                partial = " ".join(parts[i:])
                if partial in self._topic_map:
                    shards_needed.add(self._topic_map[partial])
                    break
        
        return shards_needed
    
    def get_shard_path(self, shard_name: str) -> Optional[Path]:
        """Bir shard'ın disk yolunu döndür."""
        shard = self._shards.get(shard_name)
        return shard.path if shard else None
    
    def list_shards(self) -> list[str]:
        """Tüm shard isimlerini listele."""
        return list(self._shards.keys())
    
    @property
    def stats(self) -> dict:
        return {
            "shard_count": len(self._shards),
            "topic_mappings": len(self._topic_map),
            "shards": {name: {"path": str(s.path)} for name, s in self._shards.items()},
        }
