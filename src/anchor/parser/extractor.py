"""
Anchor Engine — Fact ve Confusion Extractor

Format-agnostik fact extraction motoru.
Rule içeriğinden (markdown, düz metin) yapısal bilgi çıkarır.

Desteklenen pattern'ler:
  1. Liste öğeleri: ``- fact``, ``* fact``
  2. Checklist öğeleri: ``- [ ] fact``, ``- [x] fact``
  3. Pipe table satırları: ``| Type | Description |``
  4. Blockquote: ``> fact``
  5. Kalın metin: ``**label:** value`` (inline veya ayrı satır)
  6. Alt başlıklar: ``### N. Title`` → label + takip eden içerik
  7. Kalın blok: ``**Bold Block**`` başlık + takip eden içerik
  8. Section bazlı: ``## Bölüm`` altındaki liste öğeleri
  9. Confusion table doğru bilgileri: son sütun değerleri
"""

import re
from difflib import SequenceMatcher
from typing import Optional

from anchor.config import FACT_MIN_LENGTH, FACT_NEAR_DUPE_THRESHOLD
from anchor.parser.diagram import extract_diagram_blocks, diagram_to_facts


def extract_facts(content: str) -> list[str]:
    """Rule içeriğinden fact'leri çıkar — format-agnostik.
    
    Parametre olarak content alır, ConflictDetector'a bağımlı DEĞİLDİR.
    Bu sayede hem detect.py, hem store, hem enricher kullanabilir.
    
    Returns:
        Benzersiz fact listesi (10+ karakter, near-duplicate filtrelenmiş)
    """
    facts = []
    lines = content.split('\n')
    in_code_block = False
    in_frontmatter = False
    current_section = ""
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Code block / diagram fence toggle
        if line.startswith('```'):
            # Mermaid code block → diagram fact'leri çıkar
            if line.strip().lower() == '```mermaid':
                # Mermaid block içeriğini topla
                j = i + 1
                mermaid_lines = []
                while j < len(lines) and not lines[j].strip().startswith('```'):
                    mermaid_lines.append(lines[j])
                    j += 1
                if mermaid_lines:
                    mermaid_code = '\n'.join(mermaid_lines)
                    diagrams = extract_diagram_blocks(f"```mermaid\n{mermaid_code}\n```")
                    for d in diagrams:
                        facts.extend(diagram_to_facts(d))
                i = j + 1  # Skip closing ```
                continue
            
            in_code_block = not in_code_block
            i += 1
            continue
        if in_code_block:
            i += 1
            continue
        
        # YAML frontmatter skip
        if line == '---' and i == 0:
            in_frontmatter = True
            i += 1
            continue
        if in_frontmatter:
            if line == '---':
                in_frontmatter = False
            i += 1
            continue
        
        # Track H2 section
        if line.startswith('## ') and not line.startswith('### '):
            current_section = line[3:].strip()
            i += 1
            continue
        
        # H3 heading: "### N. Title" → label + content
        if line.startswith('### '):
            heading_label = _extract_heading_label(line)
            j, content_lines = _collect_content(lines, i + 1)
            if heading_label and content_lines:
                combined = f"{heading_label}: {' '.join(content_lines)}"
                if len(combined) > FACT_MIN_LENGTH:
                    facts.append(combined)
                    i = j
                    continue
        
        # Bold block: "**Title**" at line start
        if line.startswith('**') and '**' in line[2:] and not line.startswith('***'):
            bold_match = re.match(r'\*\*(.+?)\*\*', line)
            if bold_match and not bold_match.group(1).endswith(':'):
                facts.extend(_extract_bold_block(lines, i, bold_match))
                i += 1
                continue
        
        # Pipe table row: "| Type | Description |"
        if line.startswith('|') and line.count('|') >= 2:
            facts.extend(_extract_pipe_table_row(line))
            i += 1
            continue
        
        # Blockquote: "> text"
        if line.startswith('> '):
            facts.extend(_extract_blockquote(lines, i, line))
            i += 1
            continue
        
        # Checklist item: "- [ ] fact"
        if line.startswith('- [') and '] ' in line[:6]:
            fact = line.split('] ', 1)[-1].strip()
            if fact and len(fact) > 5:
                facts.append(fact)
        
        # List item: "- " or "* "
        elif line.startswith('- ') or line.startswith('* '):
            fact = line[2:].strip()
            if fact and len(fact) > 5:
                facts.append(fact)
        
        # Bold label: "**Label:** value"
        elif ':**' in line[:40] and line.count('**') >= 2:
            fact = line.strip()
            if len(fact) > 5:
                facts.append(fact)
        
        # ASCII diagram pattern: "+--+" box border
        elif line.startswith('+-') or line.startswith('+='):
            # Collect ASCII diagram content
            j = i
            ascii_lines = []
            while j < len(lines):
                nl = lines[j]
                stripped_nl = nl.strip()
                if (stripped_nl.startswith('+-') or stripped_nl.startswith('+=') or
                    stripped_nl.startswith('|') or
                    '-->' in stripped_nl or '<--' in stripped_nl):
                    ascii_lines.append(nl)
                    j += 1
                elif len(ascii_lines) >= 3 and not stripped_nl:
                    # Empty line after diagram
                    break
                else:
                    break
            if len(ascii_lines) >= 3:
                ascii_code = '\n'.join(ascii_lines)
                diagrams = extract_diagram_blocks(ascii_code)
                for d in diagrams:
                    facts.extend(diagram_to_facts(d))
                i = j
                continue
        
        i += 1
    
    return _deduplicate_facts(facts)


def extract_known_wrong_claims(content: str) -> list[tuple[str, str]]:
    """Confusion table'dan (yanlış, doğru) çiftlerini çıkar.
    
    Pipe tablosu formatı:
    | Konu | LLM'in Genelde Dediği | Doğrusu |
    | Üretim düğümü | TSMC 7nm | SKY130 (130nm) |
    
    Returns:
        [(\"TSMC 7nm\", \"SKY130 (130nm), OpenLane ile\"), ...]
    """
    confusions = []
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('|') and line.count('|') >= 3:
            cols = [c.strip() for c in line.split('|') if c.strip()]
            if len(cols) >= 3:
                wrong = cols[-2]
                correct = cols[-1]
                is_separator = not any(c.isalpha() for c in wrong) and not any(c.isalpha() for c in correct)
                if (wrong and wrong not in ('LLM\'in Genelde Dediği', '---', '')
                    and correct and correct not in ('Doğrusu', '---', '')
                    and not is_separator):
                    confusions.append((wrong, correct))
    return confusions


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _extract_heading_label(line: str) -> str:
    """H3 başlıktan label çıkar: '### 1. Dependency Rule' → 'Dependency Rule'"""
    heading_text = line[4:].strip()
    label = re.sub(r'^\d+[\.\)]\s*', '', heading_text)
    return label.strip('*').strip()


def _collect_content(lines: list[str], start: int) -> tuple[int, list[str]]:
    """H3 heading'den sonraki içeriği topla."""
    content_lines = []
    j = start
    while j < len(lines):
        nl = lines[j].strip()
        if nl.startswith('###') or nl.startswith('## '):
            break
        if nl.startswith('---') or nl.startswith('```'):
            j += 1
            break
        if nl:
            content_lines.append(nl)
        else:
            if j + 1 < len(lines) and not lines[j + 1].strip():
                break
        j += 1
    return j, content_lines


def _extract_bold_block(lines: list[str], i: int, bold_match) -> list[str]:
    """**Title:** şeklindeki bold bloklardan fact çıkar."""
    result = []
    bold_text = bold_match.group(1).strip()
    content_lines = []
    after_bold = lines[i][bold_match.end():].strip()
    if after_bold:
        content_lines.append(after_bold)
    j = i + 1
    while j < len(lines):
        nl = lines[j].strip()
        if nl.startswith('###') or nl.startswith('## '):
            break
        if nl.startswith('---') or nl.startswith('```'):
            break
        if nl:
            content_lines.append(nl)
        else:
            break
        j += 1
    if bold_text and content_lines:
        combined = f"{bold_text}: {' '.join(content_lines)}"
        if len(combined) > FACT_MIN_LENGTH:
            result.append(combined)
    return result


def _extract_pipe_table_row(line: str) -> list[str]:
    """Pipe table satırından fact çıkar."""
    result = []
    cols = [c.strip().strip('*') for c in line.split('|') if c.strip()]
    if len(cols) >= 2 and any(c.isalpha() for c in line):
        if not any(c.isalpha() for c in cols[0]) and not any(c.isalpha() for c in cols[-1]):
            return result  # Separator
        
        if len(cols) >= 3:
            correct = cols[-1]
            header_keywords = {'konu', 'topic', 'type', 'description', 'when to use',
                              "llm'in genelde dediği", "doğrusu", 'common misconception',
                              'what llms usually say', 'correct'}
            is_header = any(k in cols[0].lower() for k in header_keywords)
            if not is_header and correct and len(correct) > 3:
                if correct not in result and len(correct) > 5:
                    result.append(correct)
                if cols[0] and len(cols[0]) > 2 and len(cols[0] + ': ' + correct) > 10:
                    labeled = f"{cols[0]}: {correct}"
                    if labeled not in result:
                        result.append(labeled)
        
        elif len(cols) == 2 and any(c.isalpha() for c in cols[1]) and len(cols[1]) > 5:
            if cols[1] not in result:
                result.append(cols[1])
    
    return result


def _extract_blockquote(lines: list[str], i: int, first_line: str) -> list[str]:
    """Blockquote satırından fact çıkar, multi-line destekler."""
    result = []
    fact = first_line.lstrip('> ').strip('* \t')
    if fact and len(fact) > FACT_MIN_LENGTH:
        result.append(fact)
    
    # Multi-line blockquote
    combined = fact
    j = i + 1
    while j < len(lines):
        nl = lines[j].strip()
        if nl.startswith('> '):
            combined += ' ' + nl.lstrip('> ').strip('* \t')
            j += 1
        elif nl == '>':
            j += 1
        else:
            break
    if combined != fact and len(combined) > 15:
        result.append(combined)
    return result


def _deduplicate_facts(facts: list[str]) -> list[str]:
    """Near-duplicate temizleme (varsayılan: 0.85 similarity threshold)."""
    seen = set()
    unique = []
    for f in facts:
        fl = f.lower().strip()
        if fl not in seen and len(f) > FACT_MIN_LENGTH:
            is_dup = False
            for existing in seen:
                sm = SequenceMatcher(None, fl, existing)
                if sm.ratio() > FACT_NEAR_DUPE_THRESHOLD:
                    is_dup = True
                    break
            if not is_dup:
                seen.add(fl)
                unique.append(f)
    return unique if unique else [facts[0].strip()] if facts else []
