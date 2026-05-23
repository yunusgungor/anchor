"""
Rule Manager — Rules CRUD + öneri sistemi.

Kullanım:
    from anchor.agent.rule_manager import RuleManager
    
    rm = RuleManager("rules/")
    
    # Listele
    rm.list_rules()
    
    # Yeni rule ekle
    rm.create_rule(
        topic="Yeni Konu",
        aliases=["yk"],
        facts={"Özellik": "Değer"},
        confusions={"Yanlış": "Doğrusu"},
        domain="hardware"
    )
    
    # Otomatik rule önerisi
    suggestions = rm.suggest_rules("LLM'in söylediği yanlış bilgi...")
"""

import os
import re
from pathlib import Path
from typing import Optional

from anchor import Rule


class RuleManager:
    """Rules klasörünü yönet."""
    
    def __init__(self, rules_path: str):
        self.path = Path(rules_path)
        self.path.mkdir(parents=True, exist_ok=True)
    
    def list_rules(self, domain: Optional[str] = None) -> list[dict]:
        """Tüm rule'ları listele."""
        rules = []
        search_path = self.path / domain if domain else self.path
        
        for fpath in search_path.rglob("*.md"):
            try:
                rule = Rule.from_file(fpath)  # Path objesi ver
                rules.append({
                    "id": rule.id,
                    "topic": rule.topic,
                    "aliases": rule.aliases,
                    "tags": rule.tags,
                    "path": str(fpath.relative_to(self.path)),
                    "strictness": rule.strictness,
                })
            except Exception:
                continue
        
        return sorted(rules, key=lambda x: x["topic"])
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """ID'ye göre rule bul."""
        for fpath in self.path.rglob("*.md"):
            if fpath.stem == rule_id:
                try:
                    return Rule.from_file(str(fpath))
                except Exception:
                    continue
        return None
    
    def create_rule(
        self,
        topic: str,
        aliases: list[str],
        facts: dict[str, str],
        confusions: dict[str, tuple[str, str]],
        domain: str = "general",
        priority: int = 5,
        strictness: float = 0.8,
    ) -> str:
        """
        Yeni rule oluştur.
        
        Args:
            topic: Konu başlığı
            aliases: Kısa isimler
            facts: {"label": "doğru bilgi"}
            confusions: {"yanlış": ("llm_genelde", "doğrusu")}
            domain: Kategori klasörü
            priority: Öncelik (1-10)
            strictness: Katılık (0.0-1.0)
            
        Returns:
            Oluşturulan dosya yolu
        """
        # Domain dizini
        domain_path = self.path / domain
        domain_path.mkdir(parents=True, exist_ok=True)
        
        # ID oluştur
        safe_id = re.sub(r'[^\w-]', '-', topic.lower())
        fpath = domain_path / f"{safe_id}.md"
        
        # İçerik oluştur
        aliases_str = ", ".join(f'"{a}"' for a in aliases)
        tags = [domain]
        
        facts_md = "\n".join(f"- **{k}:** {v}" for k, v in facts.items())
        
        confusions_md = "| Konu | LLM'in Genelde Dediği | Doğrusu |\n|------|----------------------|---------|\n"
        for k, (wrong, correct) in confusions.items():
            confusions_md += f"| {k} | {wrong} | {correct} |\n"
        
        content = f"""---
topic: "{topic}"
aliases: [{aliases_str}]
tags: [{', '.join(tags)}]
priority: {priority}
strictness: {strictness:.1f}
---

# {topic}

## Doğru Bilgiler

{facts_md}

## Sık Karıştırılan Noktalar

{confusions_md}
"""
        
        fpath.write_text(content, encoding="utf-8")
        return str(fpath)
    
    def delete_rule(self, rule_id: str) -> bool:
        """Rule sil."""
        for fpath in self.path.rglob("*.md"):
            if fpath.stem == rule_id:
                fpath.unlink()
                return True
        return False
    
    def suggest_rules(self, llm_output: str) -> list[dict]:
        """
        LLM output'una bakarak eksik rule öner.
        
        Basit yaklaşım: Bilinen pattern'lerle eşleştir.
        """
        suggestions = []
        
        # Teknik terim pattern'leri
        patterns = [
            (r"\b(TSMC|Samsung|Intel)\s+\d+nm\b", "hardware", "Üretim düğümü bilgisi"),
            (r"\b(NVIDIA|AMD|Qualcomm)\b", "hardware", "Rakip/Rakip değil bilgisi"),
            (r"\b(genel amaçlı|özel amaçlı)\b", "general", "Amaç/Use-case bilgisi"),
        ]
        
        for pattern, domain, reason in patterns:
            if re.search(pattern, llm_output, re.IGNORECASE):
                suggestions.append({
                    "trigger": pattern,
                    "domain": domain,
                    "reason": reason,
                    "suggested_action": f"'{domain}' altında yeni rule oluştur",
                })
        
        return suggestions
    
    def domain_stats(self) -> dict:
        """Domain başına istatistik."""
        stats = {}
        for subdir in self.path.iterdir():
            if subdir.is_dir():
                md_count = len(list(subdir.rglob("*.md")))
                stats[subdir.name] = md_count
        return stats
