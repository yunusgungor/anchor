"""
Anchor Demo — Shared report infrastructure.

Each scenario produces a DemoReport, and run_all.py collects them
into a single beautiful HTML report.
"""

import html
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────
#  Bilingual output helper
# ──────────────────────────────────────────────

def tr(text: str) -> str:
    """Mark text as Turkish (used for bilingual output)."""
    return f"🇹🇷 {text}"


def en(text: str) -> str:
    """Mark text as English (used for bilingual output)."""
    return f"🇬🇧 {text}"


def bil(en_text: str, tr_text: str) -> str:
    """Return both English and Turkish text."""
    return f"🇬🇧 {en_text}\n🇹🇷 {tr_text}"


def flag(lang: str) -> str:
    return "🇬🇧" if lang == "en" else "🇹🇷"


# ──────────────────────────────────────────────
#  Report data model
# ──────────────────────────────────────────────

@dataclass
class ReportSection:
    title: str
    body: str
    section_type: str = "info"  # info | success | warning | error | critical | code

    def color(self) -> str:
        return {
            "info": "#58a6ff",
            "success": "#3fb950",
            "warning": "#d29922",
            "error": "#f85149",
            "critical": "#da3633",
            "code": "#8b949e",
        }.get(self.section_type, "#58a6ff")

    def icon(self) -> str:
        return {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚫",
            "code": "📄",
        }.get(self.section_type, "ℹ️")


@dataclass
class Metric:
    key: str
    value: Any
    unit: str = ""
    icon: str = ""


@dataclass
class DemoReport:
    """Report produced by one scenario."""

    scenario_id: str
    title_en: str
    title_tr: str
    status: str = "running"  # running | passed | failed | skipped
    duration_ms: float = 0.0
    sections: list[ReportSection] = field(default_factory=list)
    metrics: list[Metric] = field(default_factory=list)
    raw_log: str = ""

    def add_section(self, title: str, body: str, section_type: str = "info"):
        self.sections.append(ReportSection(title, body, section_type))

    def add_code_section(self, title: str, code: str):
        self.sections.append(ReportSection(title, f"<pre><code>{html.escape(code)}</code></pre>", "code"))

    def add_metric(self, key: str, value: Any, unit: str = "", icon: str = ""):
        self.metrics.append(Metric(key, value, unit, icon))

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "title_en": self.title_en,
            "title_tr": self.title_tr,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "sections": [
                {"title": s.title, "body": s.body, "type": s.section_type}
                for s in self.sections
            ],
            "metrics": [
                {"key": m.key, "value": str(m.value), "unit": m.unit, "icon": m.icon}
                for m in self.metrics
            ],
        }


# ──────────────────────────────────────────────
#  Terminal output helpers (for live demo)
# ──────────────────────────────────────────────

def print_header(text: str, lang: str = "en"):
    """Print a section header with language-specific prefix."""
    prefix = flag(lang)
    width = 70
    print()
    print("=" * width)
    print(f"  {prefix}  {text}")
    print("=" * width)


def print_step(step: int, total: int, text: str, status: str = "..."):
    """Print a step indicator."""
    icons = {"...": "⏳", "OK": "✅", "FAIL": "❌", "SKIP": "⏭️", "INFO": "ℹ️"}
    icon = icons.get(status, "•")
    print(f"  {icon}  [{step}/{total}] {text}")


def print_metric(key: str, value: Any, unit: str = ""):
    """Print a key-value metric."""
    print(f"     📊 {key}: {value}{unit}")


def print_table(rows: list[list[str]], headers: list[str]):
    """Print a simple aligned table."""
    if not rows:
        return
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
    # Header
    header_line = "  " + " │ ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(header_line)
    print("  " + "─┼─".join("─" * w for w in col_widths))
    # Rows
    for row in rows:
        line = "  " + " │ ".join(str(c).ljust(w) for c, w in zip(row, col_widths))
        print(line)


# ──────────────────────────────────────────────
#  HTML Report Generator
# ──────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anchor Demo — Comprehensive Report</title>
<style>
  :root {{
    --bg: #0d1117;
    --surface: #161b22;
    --surface-2: #21262d;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --success: #3fb950;
    --warning: #d29922;
    --error: #f85149;
    --critical: #da3633;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 20px;
  }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  header {{
    text-align: center; padding: 40px 0 30px;
    border-bottom: 1px solid var(--border); margin-bottom: 30px;
  }}
  header h1 {{ font-size: 2.2em; background: linear-gradient(135deg, var(--accent), #bc8cff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  header p {{ color: var(--text-dim); margin-top: 8px; }}
  header .meta {{ font-size: 0.9em; color: var(--text-dim); margin-top: 12px; }}
  header .meta span {{ margin: 0 12px; }}
  .summary-bar {{
    display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
    margin: 24px 0 32px;
  }}
  .summary-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px 24px; text-align: center; min-width: 120px;
  }}
  .summary-card .value {{ font-size: 1.8em; font-weight: 700; }}
  .summary-card .label {{ font-size: 0.8em; color: var(--text-dim); margin-top: 4px; }}
  .scenario {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    margin-bottom: 20px; overflow: hidden;
  }}
  .scenario-header {{
    display: flex; align-items: center; padding: 16px 20px;
    cursor: pointer; border-bottom: 1px solid var(--border);
    transition: background 0.2s;
  }}
  .scenario-header:hover {{ background: var(--surface-2); }}
  .scenario-header .status-icon {{ font-size: 1.4em; margin-right: 14px; }}
  .scenario-header .title {{ flex: 1; font-size: 1.1em; font-weight: 600; }}
  .scenario-header .title small {{ font-size: 0.8em; color: var(--text-dim); font-weight: 400; }}
  .scenario-header .duration {{ color: var(--text-dim); font-size: 0.9em; margin-right: 16px; }}
  .scenario-header .toggle {{ color: var(--text-dim); font-size: 1.2em; }}
  .scenario-body {{ padding: 0 20px 20px; display: none; }}
  .scenario-body.open {{ display: block; }}
  .section {{ margin: 16px 0; }}
  .section-title {{ font-weight: 600; margin-bottom: 6px; font-size: 0.95em; }}
  .section-body {{ color: var(--text-dim); font-size: 0.95em; white-space: pre-wrap; }}
  .section-body pre {{ background: var(--surface-2); border-radius: 6px; padding: 12px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.88em;
    overflow-x: auto; }}
  .section-body code {{ background: var(--surface-2); padding: 2px 6px; border-radius: 4px;
    font-size: 0.88em; }}
  .section-success {{ border-left: 3px solid var(--success); padding-left: 12px; }}
  .section-warning {{ border-left: 3px solid var(--warning); padding-left: 12px; }}
  .section-error {{ border-left: 3px solid var(--error); padding-left: 12px; }}
  .section-critical {{ border-left: 3px solid var(--critical); padding-left: 12px; }}
  .metrics-row {{
    display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0;
  }}
  .metric-chip {{
    background: var(--surface-2); border-radius: 20px; padding: 4px 14px;
    font-size: 0.85em; display: inline-flex; align-items: center; gap: 6px;
  }}
  .badge {{
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    font-size: 0.78em; font-weight: 600;
  }}
  .badge-passed {{ background: #1b3826; color: var(--success); }}
  .badge-failed {{ background: #3d1416; color: var(--error); }}
  .badge-skipped {{ background: #1c1c1c; color: var(--text-dim); }}
  footer {{
    text-align: center; padding: 30px 0; color: var(--text-dim); font-size: 0.85em;
    border-top: 1px solid var(--border); margin-top: 40px;
  }}
  @media (max-width: 640px) {{
    .summary-bar {{ flex-direction: column; align-items: center; }}
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>⚓ Anchor Engine Demo</h1>
    <p>Comprehensive capability showcase — {total_scenarios} scenarios, all modules</p>
    <div class="meta">
      <span>📅 {timestamp}</span>
      <span>⚡ {total_duration}s total</span>
      <span>📂 {rules_count} rules loaded</span>
    </div>
    <div class="summary-bar">
      <div class="summary-card">
        <div class="value" style="color:var(--success)">{passed}</div>
        <div class="label">✅ Passed</div>
      </div>
      <div class="summary-card">
        <div class="value" style="color:var(--error)">{failed}</div>
        <div class="label">❌ Failed</div>
      </div>
      <div class="summary-card">
        <div class="value" style="color:var(--accent)">{total_scenarios}</div>
        <div class="label">📋 Total</div>
      </div>
    </div>
  </header>
  {scenarios_html}
  <footer>
    ⚓ Anchor Engine Demo — Built with ❤️ and deterministic rectification<br>
    <span style="font-size:0.85em">Zero hidden LLM calls — every result is reproducible</span>
  </footer>
</div>
<script>
document.querySelectorAll('.scenario-header').forEach(h => {{
  h.addEventListener('click', () => {{
    const body = h.nextElementSibling;
    body.classList.toggle('open');
    h.querySelector('.toggle').textContent = body.classList.contains('open') ? '▼' : '▶';
  }});
}});
// Open first scenario by default
const firstBody = document.querySelector('.scenario-body');
if (firstBody) {{ firstBody.classList.add('open'); }}
</script>
</body>
</html>"""


def generate_html_report(reports: list[DemoReport], rules_count: int = 0) -> str:
    """Generate the complete HTML report from a list of DemoReport objects."""
    passed = sum(1 for r in reports if r.status == "passed")
    failed = sum(1 for r in reports if r.status == "failed")
    total_duration = sum(r.duration_ms for r in reports) / 1000.0
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    scenarios_html = ""
    status_icons = {"passed": "✅", "failed": "❌", "skipped": "⏭️", "running": "⏳"}
    badge_classes = {"passed": "badge-passed", "failed": "badge-failed", "skipped": "badge-skipped"}

    for rep in reports:
        icon = status_icons.get(rep.status, "❓")
        badge_cls = badge_classes.get(rep.status, "badge-skipped")
        title_line = f"{rep.title_en}<br><small>{rep.title_tr}</small>"

        sections_html = ""
        for sec in rep.sections:
            type_class = {"success": "section-success", "warning": "section-warning",
                          "error": "section-error", "critical": "section-critical"}.get(sec.section_type, "")
            sections_html += f"""
            <div class="section {type_class}">
              <div class="section-title" style="color:{sec.color()}">{sec.icon()} {html.escape(sec.title)}</div>
              <div class="section-body">{sec.body}</div>
            </div>"""

        metrics_html = ""
        if rep.metrics:
            chips = "".join(
                f'<span class="metric-chip">{m.icon} {html.escape(m.key)}: <strong>{m.value}{m.unit}</strong></span>'
                for m in rep.metrics
            )
            metrics_html = f'<div class="metrics-row">{chips}</div>'

        scenarios_html += f"""
        <div class="scenario">
          <div class="scenario-header">
            <span class="status-icon">{icon}</span>
            <span class="title">{title_line}</span>
            <span class="duration">⚡ {rep.duration_ms:.1f}ms</span>
            <span class="badge {badge_cls}">{rep.status.upper()}</span>
            <span class="toggle">▶</span>
          </div>
          <div class="scenario-body">
            {metrics_html}
            {sections_html}
          </div>
        </div>"""

    return HTML_TEMPLATE.format(
        timestamp=timestamp,
        total_scenarios=len(reports),
        total_duration=f"{total_duration:.2f}",
        rules_count=rules_count,
        passed=passed,
        failed=failed,
        scenarios_html=scenarios_html,
    )


def save_report(reports: list[DemoReport], output_path: str = "report.html", rules_count: int = 0):
    """Generate and save the HTML report."""
    html_content = generate_html_report(reports, rules_count)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\n📊  HTML rapor kaydedildi: {output_path}")
    print(f"     Dosya boyutu: {os.path.getsize(output_path):,} bytes")
