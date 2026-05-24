"""
Anchor Engine — Deterministic Diagram Parser

Mermaid ve ASCII diyagramlarından yapısal bilgi çıkarır.
Sıfır LLM, tamamen regex+state-machine tabanlı.
"""

import re
from typing import Any

# ──────────────────────────────────────────
# Mermaid Pattern Constants
# ──────────────────────────────────────────

# Node definitions
RE_NODE_SQUARE = re.compile(r'([A-Za-z0-9_çğıöşüüĞİÖŞÜ]+)\[([^\]]+)\]')
RE_NODE_ROUND  = re.compile(r'([A-Za-z0-9_çğıöşüüĞİÖŞÜ]+)\(([^\)]+)\)')
RE_NODE_DIAMOND = re.compile(r'([A-Za-z0-9_çğıöşüüĞİÖŞÜ]+)\{([^\}]+)\}')

# Edge patterns — arrow-only (node definitions handled separately)
# Simple arrow: -->, ==>
RE_SIMPLE_ARROW = re.compile(r'(-{2,3}|={2,3})[>]')

# Subgraph
RE_SUBGRAPH = re.compile(r'subgraph\s+([\w\sçğıöşüüĞİÖŞÜ\-]+)')
RE_END = re.compile(r'^end\s*$')

# Headers
RE_GRAPH_HEADER = re.compile(r'(graph|flowchart)\s+(TD|LR|BT|RL)')
RE_SEQUENCE_HEADER = re.compile(r'sequenceDiagram')
RE_CLASS_HEADER = re.compile(r'classDiagram')
RE_STATE_HEADER = re.compile(r'stateDiagram(?:-v2)?')

# Sequence participants
RE_PARTICIPANT = re.compile(r'participant\s+([\w\sçğıöşüüĞİÖŞÜ\-]+)')
RE_SEQUENCE_MSG = re.compile(
    r'([A-Za-z0-9_çğıöşüüĞİÖŞÜ]+)'  # from
    r'\s*(->>|-->>|->|-x|--x|-)\s*'  # arrow
    r'([A-Za-z0-9_çğıöşüüĞİÖŞÜ]+)'  # to
    r':\s*(.*)'  # message
)

# State diagram
RE_STATE = re.compile(r'state\s+"([^"]+)"\s+as\s+([A-Za-z0-9_]+)')
RE_STATE_TRANSITION = re.compile(
    r'([A-Za-z0-9_]+)\s*-->'
    r'\s*([A-Za-z0-9_]+)'
    r'(?:\s*:\s*(.*))?'
)

# ──────────────────────────────────────────
# ASCII Pattern Constants
# ──────────────────────────────────────────

# Box detection: top/bottom border
RE_ASCII_BOX_TOP = re.compile(r'[\+\#][\-\=\*]{2,}[\+\#]')
RE_ASCII_BOX_SIDE = re.compile(r'\|([^|]{1,40})\|')
RE_ASCII_BOX_BORDER = re.compile(r'[\+\#][\-\=\*\.]{2,}[\+\#]')

# Arrow detection
RE_ASCII_HORIZ_ARROW = re.compile(r'\-{2,}\>|={2,}\>|\<\-\-{2,}|\<={2,}')
RE_ASCII_VERT_ARROW = re.compile(r'\|(?:\s*\|)?\s*v\s*\|?', re.IGNORECASE)

# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _normalize_label(label: str) -> str:
    """Node label'ini normalize et: köşeli parantezleri kaldır, trim yap."""
    return label.strip().strip('[](){}"\"\'')


def _clean_id(node_id: str) -> str:
    """Node ID'sini temizle."""
    return node_id.strip()


def _extract_node_id(text: str) -> str | None:
    """
    Prefix/suffix'ten son node ID'sini çıkar.
    
    Örnekler:
      "A[Input]" → "A"
      "A" → "A"
      "B[Process]" → "B"
      "B" → "B"
      "" → None
    """
    text = text.strip()
    if not text:
        return None
    # Remove trailing node definition blocks: [label], (label), {label}
    text = re.sub(r'\[[^\]]*\]$', '', text)
    text = re.sub(r'\([^\)]*\)$', '', text)
    text = re.sub(r'\{[^\}]*\}$', '', text)
    text = text.strip()
    if not text:
        return None
    # Take the last word (alphanumeric with underscores)
    words = re.findall(r'[A-Za-z0-9_çğıöşüüĞİÖŞÜ]+', text)
    return words[-1] if words else None


def _register_bare_node(result: dict, node_id: str, source_text: str) -> None:
    """
    Edge'den referans alınan ama label syntax'ı olmayan node'ları kaydeder.
    Örn: 'Start' (no brackets) → node registered with label='Start'
    """
    if not node_id:
        return
    # Check if already registered
    if any(n["id"] == node_id for n in result["nodes"]):
        return
    # Check if this node had label syntax in the source text
    # (meaning _extract_node_id stripped it)
    has_label_syntax = bool(re.search(
        r'\[[^\]]*\]$|\([^\)]*\)$|\{[^\}]*\}$',
        source_text.strip()
    ))
    if not has_label_syntax:
        # Bare ID — use the ID itself as the label
        result["nodes"].append({
            "id": node_id,
            "label": node_id,  # Bare ID → label = ID
            "type": "bare",
        })


# ──────────────────────────────────────────
# Mermaid Parser
# ──────────────────────────────────────────

def parse_mermaid(code: str) -> dict[str, Any]:
    """
    Mermaid diagram kodunu parse eder.
    
    Desteklenen: graph, flowchart, sequenceDiagram, classDiagram, stateDiagram
    
    Returns:
        dict: parsed diagram yapısı
    """
    result: dict[str, Any] = {
        "type": "mermaid",
        "subtype": "unknown",
        "direction": "",
        "nodes": [],
        "edges": [],
        "sequences": [],
        "states": [],
        "transitions": [],
        "participants": [],
        "subgraphs": [],
        "flows": [],
    }
    
    lines = code.strip().split('\n')
    if not lines:
        return result
    
    first_line = lines[0].strip()
    
    # Tip tespiti
    m = RE_GRAPH_HEADER.match(first_line)
    if m:
        result["subtype"] = m.group(1)
        result["direction"] = m.group(2)
    elif RE_SEQUENCE_HEADER.match(first_line):
        result["subtype"] = "sequenceDiagram"
    elif RE_CLASS_HEADER.match(first_line):
        result["subtype"] = "classDiagram"
    elif RE_STATE_HEADER.match(first_line):
        result["subtype"] = "stateDiagram-v2"
    else:
        # Fallback: graph varsay
        result["subtype"] = "graph"
    
    # Node ID → Label mapping (parsing sırasında doldurulur)
    node_labels: dict[str, str] = {}
    node_types: dict[str, str] = {}
    
    current_subgraph = ""
    
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith('%') or line.startswith('%%'):
            continue
        
        # Subgraph
        sg = RE_SUBGRAPH.match(line)
        if sg:
            current_subgraph = sg.group(1).strip()
            result["subgraphs"].append({"name": current_subgraph, "nodes": []})
            continue
        if RE_END.match(line):
            current_subgraph = ""
            continue
        
        if result["subtype"] == "sequenceDiagram":
            # Participant
            p = RE_PARTICIPANT.match(line)
            if p:
                result["participants"].append(p.group(1).strip())
                continue
            
            # Message
            msg = RE_SEQUENCE_MSG.match(line)
            if msg:
                result["sequences"].append({
                    "from": msg.group(1).strip(),
                    "to": msg.group(3).strip(),
                    "arrow": msg.group(2).strip(),
                    "message": msg.group(4).strip(),
                })
                continue
        
        if result["subtype"] in ("stateDiagram-v2", "stateDiagram"):
            st = RE_STATE.match(line)
            if st:
                result["states"].append({
                    "id": st.group(2).strip(),
                    "label": st.group(1).strip(),
                })
                node_labels[st.group(2).strip()] = st.group(1).strip()
                continue
            
            tr = RE_STATE_TRANSITION.match(line)
            if tr:
                result["transitions"].append({
                    "from": tr.group(1).strip(),
                    "to": tr.group(2).strip(),
                    "label": tr.group(3).strip() if tr.group(3) else "",
                })
                continue
        
        # Node definitions — find ALL nodes on this line (search not match)
        # e.g. "A[Input] --> B[Process]" has 2 nodes
        for regex, ntype in [
            (RE_NODE_SQUARE, "rect"),
            (RE_NODE_ROUND, "round"),
            (RE_NODE_DIAMOND, "diamond"),
        ]:
            for m in regex.finditer(line):
                nid = _clean_id(m.group(1))
                label = _normalize_label(m.group(2))
                node_labels[nid] = label
                node_types[nid] = ntype
                if current_subgraph and result["subgraphs"]:
                    result["subgraphs"][-1]["nodes"].append(nid)
                # Check if this node ID is already registered
                if not any(n["id"] == nid for n in result["nodes"]):
                    result["nodes"].append({
                        "id": nid,
                        "label": label,
                        "type": ntype,
                    })
        
        # Edge definitions — find ALL edges on this line (search not match)
        # Simple approach: find arrows, extract IDs to left/right
        # Handle inline labels: -->|label|-->
        for m in re.finditer(r'-->\|([^|]+)\|-->', line):
            # Find source (ID before this arrow)
            prefix = line[:m.start()].strip()
            source = _extract_node_id(prefix)
            # Find target (ID after this arrow)
            suffix = line[m.end():].strip()
            target = _extract_node_id(suffix)
            label = m.group(1).strip()
            if source and target:
                result["edges"].append({
                    "from": source, "to": target, "label": label,
                })
                # Register bare nodes
                _register_bare_node(result, source, prefix)
                _register_bare_node(result, target, suffix)
        
        # Simple arrows: -->, ==>
        for m in RE_SIMPLE_ARROW.finditer(line):
            arrow_start = m.start()
            arrow_end = m.end()
            prefix = line[:arrow_start].strip()
            suffix = line[arrow_end:].strip()
            source = _extract_node_id(prefix)
            target = _extract_node_id(suffix)
            if source and target:
                # Register bare nodes (IDs without label syntax)
                _register_bare_node(result, source, prefix)
                _register_bare_node(result, target, suffix)
                # Check for pipe label in suffix
                label = ""
                label_m = re.match(r'\|([^|]+)\|', suffix)
                if label_m:
                    label = label_m.group(1).strip()
                result["edges"].append({
                    "from": source, "to": target, "label": label,
                })
    
    # Post-processing: Node label'larını edge'lerine ekle
    for edge in result["edges"]:
        edge["from_label"] = node_labels.get(edge["from"], edge["from"])
        edge["to_label"] = node_labels.get(edge["to"], edge["to"])
    
    # Post-processing: Flows çıkar (topolojik sıralama değil, sadece edge bazlı)
    node_set = set()
    for n in result["nodes"]:
        node_set.add(n["id"])
    
    # İzin verilen akışları çıkar (node'lar arası edge'leri takip ederek)
    visited = set()
    
    def find_flows(start, path, depth=0):
        if depth > 10:  # Döngü koruması
            return
        current = node_labels.get(start, start)  # son node'un label'ı
        if current not in visited:
            visited.add(current)
        outgoing = [e for e in result["edges"] if e["from"] == start]
        if not outgoing:
            if len(path) >= 2:
                result["flows"].append(list(path))
            return
        for e in outgoing:
            new_path = list(path)
            to_label = node_labels.get(e["to"], e["to"])
            new_path.append(to_label)
            find_flows(e["to"], new_path, depth + 1)
    
    # Her root node'dan (kendine gelen edge olmayan) başla
    all_targets = {e["to"] for e in result["edges"]}
    roots = [e["from"] for e in result["edges"] if e["from"] not in all_targets]
    roots = list(set(roots))
    
    if not roots:
        # Döngü varsa veya edge yoksa, tüm node'lardan dene
        roots = list(set(e["from"] for e in result["edges"]))
    
    for root in roots:
        root_label = node_labels.get(root, root)
        find_flows(root, [root_label])
    
    return result


# ──────────────────────────────────────────
# ASCII Diagram Parser
# ──────────────────────────────────────────

def parse_ascii_diagram(code: str) -> dict[str, Any]:
    """
    Basit ASCII diyagramlarını parse eder.
    
    Desteklenen:
    - Kutu+ok diyagramları (+---+ ---> +---+)
    - Dikey oklar
    - Basit ağaç yapıları
    
    Returns:
        dict: parsed diagram yapısı
    """
    result: dict[str, Any] = {
        "type": "ascii",
        "subtype": "architecture",
        "nodes": [],
        "edges": [],
        "flows": [],
    }
    
    lines = code.strip().split('\n')
    if not lines:
        return result
    
    # ASCII diagram parsing:
    # 1. Kutuları bul (+--+ pattern)
    # 2. Okları bul (--> pattern)
    # 3. Etiketleri çıkar
    
    boxes = []  # [(row, col_start, col_end, label)]
    arrows = []  # [(from_row, from_col, to_row, to_col, label)]
    
    for i, line in enumerate(lines):
        # Kutu üst/alt kenarı
        # Find all box borders on this line
        col = 0
        while col < len(line):
            m = RE_ASCII_BOX_BORDER.search(line, col)
            if not m:
                break
            start = m.start()
            end = m.end()
            
            # Kutu içeriğini bul (bir sonraki satırda | label |)
            label = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # next_line[start:end] içinde | label | pattern'ini ara
                label_m = re.search(r'\|([^|]{1,40})\|', next_line[start:end+1] if end+1 <= len(next_line) else next_line[start:])
                if label_m:
                    label = label_m.group(1).strip()
                    # Clear leading pipe area
                    pipe_idx = next_line.find(label_m.group(0))
                    while pipe_idx < start:
                        pipe_idx = next_line.find(label_m.group(0), pipe_idx + 1)
                        
            # Dublicate kontrolü: aynı col_start pozisyonunda box zaten var mı?
            # (üst ve alt border aynı kutuyu temsil eder)
            is_duplicate = any(
                b["col_start"] == start
                for b in boxes
            )
            if is_duplicate:
                col = end + 1
                continue
            
            boxes.append({
                "row": i,
                "col_start": start,
                "col_end": end,
                "label": label,
            })
            
            col = end + 1  # Move past this box
        
        # Yatay ok
        arrow_matches = list(RE_ASCII_HORIZ_ARROW.finditer(line))
        for m in arrow_matches:
            # Oku çevreleyen kutuları bul
            arrow_start = m.start()
            arrow_end = m.end()
            arrows.append({
                "from_row": i,
                "to_row": i,
                "from_col": arrow_start,
                "to_col": arrow_end,
                "label": "",
                "direction": "right" if ">" in m.group() else "left",
            })
    
    # Post-processing: Kutuları node'lara çevir
    node_counter = 0
    for box in boxes:
        node_id = f"box_{node_counter}"
        node_counter += 1
        result["nodes"].append({
            "id": node_id,
            "label": box["label"] if box["label"] else f"box_{node_counter}",
            "type": "box",
            "position": {"row": box["row"], "col": box["col_start"]},
        })
    
    # Okları edge'lere çevir — kolon bazlı eşleştirme
    for arrow in arrows:
        # Okun solundaki (en yakın) kutuyu bul
        # row filter yok — sadece kolon pozisyonuna bak
        from_box = None
        to_box = None
        arrow_mid = (arrow["from_col"] + arrow["to_col"]) // 2
        
        for b in boxes:
            # Arrow'ın solunda: box'ın sağ kenarı arrow'ın solunda
            if b["col_end"] <= arrow["from_col"]:
                if from_box is None or b["col_end"] > from_box["col_end"]:
                    from_box = b
            # Arrow'ın sağında: box'ın sol kenarı arrow'ın sağında
            if b["col_start"] >= arrow["to_col"]:
                if to_box is None or b["col_start"] < to_box["col_start"]:
                    to_box = b
        
        if from_box and to_box:
            from_idx = boxes.index(from_box)
            to_idx = boxes.index(to_box)
            result["edges"].append({
                "from": f"box_{from_idx}",
                "to": f"box_{to_idx}",
                "from_label": from_box["label"] if from_box["label"] else f"box_{from_idx}",
                "to_label": to_box["label"] if to_box["label"] else f"box_{to_idx}",
                "label": "",
            })
    
    # Basit fallback: Lines-based parsing
    # Eğer hiç node bulunamadıysa, metin bazlı yaklaşım
    if not result["nodes"]:
        _ascii_fallback_parse(lines, result)
    
    # Flows çıkar
    _build_ascii_flows(result)
    
    return result


def _ascii_fallback_parse(lines: list[str], result: dict[str, Any]) -> None:
    """
    Fallback: Satır bazlı ASCII parsing.
    Pattern'leri doğrudan metin üzerinde arar.
    """
    node_counter = len(result["nodes"])
    
    for i, line in enumerate(lines):
        # | label | pattern
        label_matches = list(RE_ASCII_BOX_SIDE.finditer(line))
        for m in label_matches:
            label = m.group(1).strip()
            if label and len(label) <= 40:  # Muhtemel kutu etiketi
                node_id = f"box_{node_counter}"
                node_counter += 1
                result["nodes"].append({
                    "id": node_id,
                    "label": label,
                    "type": "box",
                    "position": {"row": i, "col": m.start()},
                })
    
    # Ok pattern'leri
    for i, line in enumerate(lines):
        for m in RE_ASCII_HORIZ_ARROW.finditer(line):
            # Okun solundaki ve sağındaki node'ları bul
            before = line[:m.start()].strip()
            after = line[m.end():].strip()
            
            # Node'lar arasında en yakın olanı bul
            from_node = None
            to_node = None
            
            for n in result["nodes"]:
                if n["position"]["row"] == i:
                    if n["position"]["col"] < m.start():
                        # Sol taraftaki en yakın node
                        if from_node is None or n["position"]["col"] > from_node["position"]["col"]:
                            from_node = n
                    elif n["position"]["col"] > m.end():
                        # Sağ taraftaki en yakın node
                        if to_node is None or n["position"]["col"] < to_node["position"]["col"]:
                            to_node = n
            
            if from_node and to_node:
                # Edge'i daha önce eklemediysek ekle
                edge_exists = any(
                    e["from"] == from_node["id"] and e["to"] == to_node["id"]
                    for e in result["edges"]
                )
                if not edge_exists:
                    result["edges"].append({
                        "from": from_node["id"],
                        "to": to_node["id"],
                        "from_label": from_node["label"],
                        "to_label": to_node["label"],
                        "label": "",
                    })


def _build_ascii_flows(result: dict[str, Any]) -> None:
    """ASCII diyagramından izin verilen akışları çıkar."""
    if not result["edges"]:
        return
    
    # Her node'dan başlayarak akışları bul
    visited_flows = set()
    
    def find_flows_ascii(start_id, path, depth=0):
        if depth > 10:
            return
        path_key = " → ".join(str(p) for p in path)
        if path_key in visited_flows:
            return
        visited_flows.add(path_key)
        
        outgoing = [e for e in result["edges"] if e["from"] == start_id]
        if not outgoing:
            if len(path) >= 2:
                result["flows"].append(list(path))
            return
        for e in outgoing:
            new_path = list(path) + [e["to_label"]]
            find_flows_ascii(e["to"], new_path, depth + 1)
    
    all_targets = {e["to"] for e in result["edges"]}
    roots = list(set(e["from"] for e in result["edges"] if e["from"] not in all_targets))
    roots = roots or list(set(e["from"] for e in result["edges"]))
    
    for root in roots:
        root_node = next((n for n in result["nodes"] if n["id"] == root), None)
        root_label = root_node["label"] if root_node else root
        find_flows_ascii(root, [root_label])


# ──────────────────────────────────────────
# Public API
# ──────────────────────────────────────────


def extract_diagram_blocks(text: str) -> list[dict[str, Any]]:
    """
    Metin içindeki tüm diagram bloklarını bulur ve parse eder.
    
    Returns:
        list[dict]: Her diagram için parsed yapı
    """
    results = []
    
    # 1. Mermaid blokları
    mermaid_blocks = _extract_fenced_blocks(text, "mermaid")
    for block in mermaid_blocks:
        parsed = parse_mermaid(block)
        if parsed["nodes"] or parsed["edges"] or parsed["sequences"]:
            results.append(parsed)
    
    # 2. ASCII diyagram blokları
    ascii_blocks = _extract_ascii_diagrams(text)
    for block in ascii_blocks:
        parsed = parse_ascii_diagram(block)
        if parsed["nodes"] or parsed["edges"]:
            results.append(parsed)
    
    return results


def _extract_fenced_blocks(text: str, language: str) -> list[str]:
    """Fenced code block'ları çıkarır (```language ... ```)."""
    blocks = []
    pattern = re.compile(
        r'```' + re.escape(language) + r'\s*\n(.*?)```',
        re.DOTALL
    )
    for m in pattern.finditer(text):
        blocks.append(m.group(1).strip())
    return blocks


def _extract_ascii_diagrams(text: str) -> list[str]:
    """
    ASCII diyagram bloklarını metin içinde algılar.
    
    Strateji: Fenced değilse bile +--+, | |
    pattern'lerini ara ve çevresini blok olarak al.
    """
    blocks = []
    lines = text.split('\n')
    
    # Fenced ASCII blokları (````)
    in_fence = False
    current_block = []
    for line in lines:
        if line.strip().startswith('```'):
            if in_fence:
                blocks.append('\n'.join(current_block))
                current_block = []
                in_fence = False
            else:
                in_fence = True
            continue
        if in_fence:
            current_block.append(line)
    
    # Ayrıca fenced olmayan ASCII diyagramları da tespit et
    # (arka arkaya gelen + border satırları)
    in_ascii = False
    current_ascii = []
    for line in lines:
        stripped = line.strip()
        is_border = bool(RE_ASCII_BOX_BORDER.match(stripped))
        is_side = bool(RE_ASCII_BOX_SIDE.match(stripped))
        has_arrow = bool(RE_ASCII_HORIZ_ARROW.search(stripped))
        is_vert = stripped in ('|', 'v', '^') or stripped.startswith('|') and stripped.endswith('|')
        is_connector = stripped in ('|', 'v', '^') or stripped.startswith('| ') or stripped.startswith('  |')
        
        if is_border or is_side or has_arrow or is_connector:
            in_ascii = True
            current_ascii.append(line)
        else:
            if in_ascii and len(current_ascii) >= 3:  # En az 3 satır
                blocks.append('\n'.join(current_ascii))
            in_ascii = False
            current_ascii = []
    
    # Dosya sonu
    if in_ascii and len(current_ascii) >= 3:
        blocks.append('\n'.join(current_ascii))
    
    return blocks


def diagram_to_facts(diagram: dict[str, Any]) -> list[str]:
    """
    Parse edilmiş diagram'dan metinsel fact'ler çıkarır.
    
    ClaimExtractor ve ConflictMatcher için kullanılır.
    """
    facts = []
    
    if diagram["type"] == "mermaid" and diagram["subtype"] == "sequenceDiagram":
        # Sequence diagram
        for seq in diagram["sequences"]:
            facts.append(f"Message flow: {seq['from']} → {seq['to']}: {seq['message']}")
            facts.append(f"{seq['from']} sends message to {seq['to']}")
        for p in diagram["participants"]:
            facts.append(f"Participant: {p}")
    
    elif diagram["type"] == "mermaid" and diagram["subtype"] in ("stateDiagram-v2", "stateDiagram"):
        for t in diagram["transitions"]:
            facts.append(f"State transition: {t['from']} → {t['to']}")
        for s in diagram["states"]:
            facts.append(f"State: {s['label']}")
    
    else:
        # Graph/flowchart/classDiagram
        for edge in diagram["edges"]:
            from_lbl = edge.get("from_label", edge["from"])
            to_lbl = edge.get("to_label", edge["to"])
            if edge["label"]:
                facts.append(f"Dependency: {from_lbl} → {to_lbl} ({edge['label']})")
                facts.append(f"{from_lbl} {edge['label']} {to_lbl}")
            else:
                facts.append(f"Dependency: {from_lbl} → {to_lbl}")
                facts.append(f"{from_lbl} depends on {to_lbl}")
        
        # Flows
        for flow in diagram["flows"]:
            facts.append(f"Flow: {' → '.join(flow)}")
    
    return facts


def diagram_to_terms(diagram: dict[str, Any]) -> list[str]:
    """
    Diagram'dan ClaimExtractor için term'ler çıkarır.
    Node label'ları, participant isimleri, state isimleri.
    """
    terms = []
    seen = set()
    
    for node in diagram.get("nodes", []):
        label = node.get("label", "").lower()
        if label and label not in seen and len(label) >= 3:
            terms.append(label)
            seen.add(label)
    
    for seq in diagram.get("sequences", []):
        for field in ("from", "to", "message"):
            val = seq.get(field, "").lower()
            if val and val not in seen and len(val) >= 3:
                terms.append(val)
                seen.add(val)
    
    for p in diagram.get("participants", []):
        p_lower = p.lower()
        if p_lower and p_lower not in seen and len(p_lower) >= 3:
            terms.append(p_lower)
            seen.add(p_lower)
    
    for s in diagram.get("states", []):
        label = s.get("label", "").lower()
        if label and label not in seen and len(label) >= 3:
            terms.append(label)
            seen.add(label)
    
    for t in diagram.get("transitions", []):
        for field in ("from", "to"):
            val = t.get(field, "").lower()
            if val and val not in seen and len(val) >= 3:
                terms.append(val)
                seen.add(val)
    
    return terms


def diagram_to_flows(diagram: dict[str, Any]) -> list[list[str]]:
    """Diagram'daki tüm flow'ları döndürür."""
    flows = []
    
    # Named flows (parsed)
    for flow in diagram.get("flows", []):
        flows.append(flow)
    
    # Edge-based flows (fallback)
    if not flows and diagram.get("edges"):
        # Simple: her edge'i ayrı flow olarak
        for edge in diagram["edges"]:
            from_lbl = edge.get("from_label", edge["from"])
            to_lbl = edge.get("to_label", edge["to"])
            flows.append([from_lbl, to_lbl])
    
    return flows
