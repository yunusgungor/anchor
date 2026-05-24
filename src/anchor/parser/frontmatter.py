"""
Frontmatter Utility — YAML frontmatter ayrıştırma için tek doğru nokta.

Tüm modüller BU utility'yi kullanır. Beş farklı yerde tekrarlanan
frontmatter parsing kodunu konsolide eder.

Desteklenen:
  - YAML frontmatter (--- ile çevrili) — dict olarak döndürür
  - Metadata çıkarma (topic, aliases, tags, priority, strictness)
  - İçerik extraction (frontmatter sonrası metin)
  - Topic extraction (sadece topic alanı, lazy parse)
"""

import re
from pathlib import Path
from typing import Any, Optional


def parse_frontmatter(text: str) -> dict[str, Any]:
    """
    YAML frontmatter'ı manuel olarak parse et (yaml modülü olmadan çalışır).
    
    ---
    topic: "Neural Processor X1"
    aliases: ["NPX1", "npx1"]
    tags: [hardware, chip]
    priority: 10
    strictness: 0.9
    ---
    
    Returns:
        Parsed alanların dict'i. Geçerli frontmatter yoksa boş dict.
    """
    if not text.startswith("---"):
        return {}
    
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    
    fm: dict[str, Any] = {}
    for line in parts[1].strip().split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        
        # List: [item1, item2]
        if val.startswith("[") and val.endswith("]"):
            val = [
                v.strip().strip("'\"").strip()
                for v in val[1:-1].split(",")
                if v.strip()
            ]
        # Quoted string
        elif val.startswith('"') and val.endswith('"'):
            val = val.strip('"')
        elif val.startswith("'") and val.endswith("'"):
            val = val.strip("'")
        # Boolean
        elif val.lower() in ("true", "yes", "on"):
            val = True
        elif val.lower() in ("false", "no", "off"):
            val = False
        # Integer
        elif val.isdigit() or (val.startswith("-") and val[1:].isdigit()):
            val = int(val)
        # Float
        elif val.replace(".", "").replace("-", "").isdigit():
            try:
                val = float(val)
            except ValueError:
                pass
        
        fm[key] = val
    
    return fm


def extract_content(text: str) -> str:
    """
    Frontmatter sonrası içerik kısmını döndürür.
    Frontmatter yoksa orijinal metni döndürür.
    """
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
    return text


def extract_topic(text: str, fallback: str = "") -> Optional[str]:
    """
    Sadece topic alanını çıkar — tam parse gerektirmez, hızlıdır.
    
    Returns:
        Topic değeri veya None
    """
    if not text.startswith("---"):
        return None
    
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    
    for line in parts[1].strip().split("\n"):
        line = line.strip()
        if line.startswith("topic:"):
            val = line.split(":", 1)[1].strip().strip("\"'")
            return val if val else None
    
    return None


def extract_metadata(text: str, rule_id: str = "") -> dict[str, Any]:
    """
    Frontmatter'dan topic, aliases, tags, priority, strictness çıkar.
    
    Returns:
        {
            "topic": str,
            "aliases": list[str],
            "tags": list[str],
            "priority": int,
            "strictness": float,
        }
        Eksik alanlar varsayılan değerlerle doldurulur.
    """
    fm = parse_frontmatter(text)
    
    return {
        "topic": fm.get("topic", rule_id or ""),
        "aliases": fm.get("aliases", []),
        "tags": fm.get("tags", []),
        "priority": fm.get("priority", 5),
        "strictness": fm.get("strictness", 0.8),
    }


def extract_aliases(text: str) -> list[str]:
    """Alias listesini çıkar (hızlı tarama)."""
    fm = parse_frontmatter(text)
    aliases = fm.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    return aliases


def extract_tags(text: str) -> list[str]:
    """Tag listesini çıkar (hızlı tarama)."""
    fm = parse_frontmatter(text)
    tags = fm.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    return tags


def extract_all_topics_and_aliases_from_dir(rules_path: str) -> set[str]:
    """
    Bir rules klasöründeki tüm .md dosyalarından topic, alias, tag ve 
    dosya adlarını topla. Bloom index ve shard router için kullanılır.
    
    Returns:
        Tüm topic/alias/tag'lerin lowercase set'i
    """
    from pathlib import Path
    
    items: set[str] = set()
    root = Path(rules_path)
    if not root.exists():
        return items
    
    for fpath in root.rglob("*.md"):
        try:
            text = fpath.read_text(encoding="utf-8")
            meta = extract_metadata(text, fpath.stem)
            
            items.add(meta["topic"].lower())
            items.add(fpath.stem.lower())
            
            for alias in meta["aliases"]:
                items.add(alias.lower())
            
            for tag in meta["tags"]:
                items.add(tag.lower())
            
            # Content'ten başlıkları da ekle
            content = extract_content(text)
            for match in re.findall(r'^#+\s+(.+)$', content, re.MULTILINE):
                items.add(match.strip().lower())
                
        except Exception:
            pass
    
    return items


def detect_content_type(text: str) -> str:
    """
    İçerik tipini tespit et (C5 ConstraintEngine için).
    """
    scores = {
        "edutainment": len(re.findall(r"\b(öğren|bilgi|ipucu|teknik|nasıl|neden|eğitim|ders)\b", text, re.I)),
        "promotional": len(re.findall(r"\b(indirim|fiyat|satın al|sipariş|kampanya|fırsat)\b", text, re.I)),
        "entertainment": len(re.findall(r"\b(eğlence|komik|gül|mizah|şaka|kahkaha)\b", text, re.I)),
        "news": len(re.findall(r"\b(haber|son dakika|gelişme|açıkladı|duyurdu|yayın)\b", text, re.I)),
    }
    return max(scores, key=scores.get) if scores else "unknown"
