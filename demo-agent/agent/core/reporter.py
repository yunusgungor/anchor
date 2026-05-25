"""
Reporter — Anchor Agent correction report formatter.

Formatlar:
  - Terminal: Renkli, emoji zengini, insan-okunabilir
  - JSON:     Makine-okunabilir, API dostu
  - HTML:     Web için rapor (opsiyonel)
  - Markdown: Dokümantasyon için
"""

import json
import time
from typing import Any

from anchor.agent.safe_llm import AgentResult


class Reporter:
    """
    Correction report formatter.
    
    Kullanım:
        reporter = Reporter()
        
        # Terminal çıktısı
        print(reporter.format_terminal(result))
        
        # JSON API çıktısı  
        data = reporter.format_json(result)
    """
    
    # -------- Terminal --------
    
    def format_terminal(self, result: "AgentResult", mode: str = "factcheck") -> str:
        """Terminal için renkli, emoji zengini rapor."""
        lines = []
        mode_info = self._get_mode_info(mode)
        
        # Header
        lines.append(f"\n{'='*60}")
        lines.append(f" {mode_info['emoji']}  Anchor Agent — {mode_info['name']} Mode")
        lines.append(f"   {mode_info['tagline']}")
        lines.append(f"{'='*60}")
        
        # Query
        lines.append(f"\n📝  Soru:")
        lines.append(f"   {result.query}")
        
        # Topics
        if result.topics:
            topics_str = ", ".join(t.upper() if isinstance(t, str) else str(t) for t in result.topics)
            lines.append(f"\n🏷️  Topic'ler: [{topics_str}]")
        
        # Response
        lines.append(f"\n💬  Cevap:")
        lines.append(f"   {result.corrected}")
        
        # Correction Summary
        lines.append(f"\n{'─'*60}")
        
        if result.modified:
            count = len(result.corrections)
            severity = max(
                (c.get("severity", "INFO") for c in result.corrections),
                key=lambda s: {"CRITICAL": 4, "ERROR": 3, "WARNING": 2, "INFO": 1}.get(s, 0),
            )
            severity_emoji = {
                "CRITICAL": "🔴",
                "ERROR": "❌",
                "WARNING": "⚠️",
                "INFO": "ℹ️",
            }.get(severity, "ℹ️")
            
            lines.append(f" {severity_emoji}  Düzeltme: {count} adet")
            
            for i, corr in enumerate(result.corrections, 1):
                sev = corr.get("severity", "INFO")
                sev_icon = {"CRITICAL": "🔴", "ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}.get(sev, "")
                lines.append(f"\n   {i}. {sev_icon}[{sev}]")
                lines.append(f"      ❌ Yanlış: {corr.get('original', '')[:100]}")
                lines.append(f"      ✅ Doğru:  {corr.get('corrected', '')[:100]}")
        else:
            lines.append(f" ✅  Düzeltme: Gerekmedi — cevap zaten kurallara uygun")
        
        # Rules activated
        rules = result.rules_activated or []
        if rules:
            lines.append(f"\n📋  Aktif Rule'lar ({len(rules)}):")
            for r in rules[:5]:
                r_name = r if isinstance(r, str) else getattr(r, "name", str(r))
                lines.append(f"   • {r_name}")
            if len(rules) > 5:
                lines.append(f"   ... ve {len(rules)-5} daha")
        
        # Confidence
        conf = result.confidence if hasattr(result, 'confidence') else None
        if conf is not None:
            conf_bar = self._confidence_bar(conf)
            lines.append(f"\n🎯  Güven: {conf:.0%} {conf_bar}")
        
        # Latency
        lat = result.latency_ms if hasattr(result, 'latency_ms') else None
        if lat:
            lines.append(f"⚡  Süre: {lat:.0f}ms")
        
        # Footer
        lines.append(f"\n{'='*60}")
        
        return "\n".join(lines)
    
    def format_terminal_compact(self, result: "AgentResult") -> str:
        """Kompakt terminal raporu (hızlı bakış için)."""
        parts = []
        
        if result.modified:
            count = len(result.corrections)
            severity = max(
                (c.get("severity", "INFO") for c in result.corrections),
                key=lambda s: {"CRITICAL": 4, "ERROR": 3, "WARNING": 2, "INFO": 1}.get(s, 0),
            )
            emoji = {"CRITICAL": "🔴", "ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}.get(severity, "⚠️")
            parts.append(f"{emoji} {count} düzeltme")
        else:
            parts.append("✅ Anchor-onaylı")
        
        if result.topics:
            topics_str = ", ".join(
                t.upper() if isinstance(t, str) else str(t)
                for t in result.topics
            )
            parts.append(f"🏷️ {topics_str}")
        
        return " | ".join(parts)
    
    # -------- JSON --------
    
    def format_json(self, result: "AgentResult", mode: str = "factcheck") -> dict:
        """JSON formatında rapor (API dostu)."""
        return {
            "mode": mode,
            "query": result.query,
            "corrected": result.corrected,
            "raw": result.raw,
            "modified": result.modified,
            "corrections": result.corrections if hasattr(result, 'corrections') else [],
            "topics": result.topics if hasattr(result, 'topics') else [],
            "rules_activated": result.rules_activated if hasattr(result, 'rules_activated') else [],
            "confidence": result.confidence if hasattr(result, 'confidence') else None,
            "latency_ms": result.latency_ms if hasattr(result, 'latency_ms') else None,
            "timestamp": time.time(),
        }
    
    # -------- HTML (Lightweight) --------
    
    def format_html(self, result: "AgentResult", mode: str = "factcheck") -> str:
        """Minimal HTML rapor."""
        mode_info = self._get_mode_info(mode)
        corrections_html = ""
        
        if result.modified:
            for i, corr in enumerate(result.corrections, 1):
                sev = corr.get("severity", "INFO")
                corrections_html += f"""
                <div class="correction severity-{sev.lower()}">
                    <span class="badge">{sev}</span>
                    <div class="diff">
                        <div class="original"><del>{corr.get('original', '')}</del></div>
                        <div class="fixed"><ins>{corr.get('corrected', '')}</ins></div>
                    </div>
                </div>"""
        else:
            corrections_html = "<p class='ok'>✅ No corrections needed</p>"
        
        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Anchor Agent — {mode_info['name']} Report</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 720px; margin: 2em auto; padding: 0 1em; }}
        .header {{ background: #1a1a2e; color: #fff; padding: 1.5em; border-radius: 12px; }}
        .header h1 {{ margin: 0; font-size: 1.4em; }}
        .header .tagline {{ opacity: 0.7; font-size: 0.9em; }}
        .query {{ background: #f5f5f5; padding: 1em; border-radius: 8px; margin: 1em 0; }}
        .response {{ line-height: 1.6; }}
        .correction {{ border: 1px solid #ddd; border-radius: 8px; padding: 0.8em; margin: 0.5em 0; }}
        .severity-CRITICAL {{ border-color: #e74c3c; }}
        .severity-ERROR {{ border-color: #e67e22; }}
        .severity-WARNING {{ border-color: #f1c40f; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }}
        .severity-CRITICAL .badge {{ background: #e74c3c; color: white; }}
        .severity-ERROR .badge {{ background: #e67e22; color: white; }}
        .severity-WARNING .badge {{ background: #f1c40f; }}
        del {{ background: #ffe0e0; color: #c00; }}
        ins {{ background: #e0ffe0; color: #0a0; }}
        .ok {{ color: #27ae60; font-weight: bold; }}
        .footer {{ margin-top: 2em; font-size: 0.85em; color: #888; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{mode_info['emoji']} Anchor Agent — {mode_info['name']}</h1>
        <div class="tagline">{mode_info['tagline']}</div>
    </div>
    <div class="query"><strong>Query:</strong> {result.query}</div>
    <div class="response">{result.corrected}</div>
    <h3>Corrections</h3>
    {corrections_html}
    {f"<p><strong>Confidence:</strong> {result.confidence:.0%}</p>" if hasattr(result, 'confidence') and result.confidence else ""}
    {f"<p><strong>Latency:</strong> {result.latency_ms:.0f}ms</p>" if hasattr(result, 'latency_ms') and result.latency_ms else ""}
    <div class="footer">Generated by Anchor Agent • anchor.nousresearch.com</div>
</body>
</html>"""
    
    # -------- Markdown --------
    
    def format_markdown(self, result: "AgentResult", mode: str = "factcheck") -> str:
        """Markdown rapor."""
        mode_info = self._get_mode_info(mode)
        lines = [
            f"# {mode_info['emoji']} Anchor Agent — {mode_info['name']}",
            "",
            f"**Query:** {result.query}",
            "",
            f"## Response",
            result.corrected,
            "",
        ]
        
        if result.modified:
            lines.append(f"## Corrections ({len(result.corrections)})")
            for corr in result.corrections:
                sev = corr.get("severity", "INFO")
                lines.append(f"- **[{sev}]** ❌ ~~{corr.get('original', '')}~~ → ✅ {corr.get('corrected', '')}")
        else:
            lines.append("✅ No corrections needed.")
        
        return "\n".join(lines)
    
    # -------- Helpers --------
    
    @staticmethod
    def _get_mode_info(mode: str) -> dict:
        """Mode metadata."""
        from .classifier import MODE_REGISTRY
        info = MODE_REGISTRY.get(mode, MODE_REGISTRY["factcheck"])
        return info
    
    @staticmethod
    def _confidence_bar(confidence: float, width: int = 12) -> str:
        """Güven skoru için bar görselleştirmesi."""
        filled = int(confidence * width)
        bar = "█" * filled + "░" * (width - filled)
        return bar
    
    @staticmethod
    def json_to_terminal(json_data: dict) -> str:
        """JSON raporu terminal formatına çevir (API'den dönen data için)."""
        mode = json_data.get("mode", "factcheck")
        query = json_data.get("query", "")
        corrected = json_data.get("corrected", "")
        modified = json_data.get("modified", False)
        corrections = json_data.get("corrections", [])
        topics = json_data.get("topics", [])
        confidence = json_data.get("confidence")
        latency = json_data.get("latency_ms")
        
        # Create AgentResult-like object
        class _Result:
            pass
        
        result = _Result()
        result.query = query
        result.corrected = corrected
        result.raw = json_data.get("raw", "")
        result.modified = modified
        result.corrections = corrections
        result.topics = topics
        result.confidence = confidence
        result.latency_ms = latency
        result.rules_activated = json_data.get("rules_activated", [])
        
        r = Reporter()
        return r.format_terminal(result, mode)
