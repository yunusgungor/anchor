# Architecture Guide

> Anchor Agent — System Architecture & Component Design

---

## 📐 System Overview

```
                        ┌─────────────┐
                        │   User CLI  │
                        │  (CLI/API)  │
                        └──────┬──────┘
                               │ query
                               ▼
┌──────────────────────────────────────────────────────┐
│                   TaskClassifier                      │
│                                                       │
│   ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│   │ FactCheck│  │ Workflow │  │    Creative       │   │
│   │  Mode    │  │   Mode   │  │     Mode          │   │
│   └────┬─────┘  └────┬─────┘  └───────┬──────────┘   │
│        │              │                │              │
│        ▼              ▼                ▼              │
│   ┌────────────────────────────────────────────┐      │
│   │              Anchor Engine                  │      │
│   │  (Detect → Rectify → Report)               │      │
│   └────────────────────────────────────────────┘      │
│                                                       │
│   ┌────────────────────────────────────────────┐      │
│   │               Reporter                      │      │
│   │  Terminal · JSON · HTML · Markdown          │      │
│   └────────────────────────────────────────────┘      │
│                                                       │
│   ┌────────────────────────────────────────────┐      │
│   │           ContextManager                    │      │
│   │  Multi-turn · Dedup · Session tracking      │      │
│   └────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────┘
```

---

## 🧩 Component Architecture

### 1. TaskClassifier (`agent/core/classifier.py`)

Query routing engine — gelen sorguyu analiz edip doğru mode'a yönlendirir.

**Pattern-matching pipeline:**

```
Query
  │
  ├─ Mode hint provided? → Use hinted mode (confidence: 1.0)
  │
  └─ Deterministic scan:
      ├─ Workflow patterns?  → "how to", "steps", "adım"  → workflow
      ├─ Creative patterns?  → "write", "tweet", "yaz"    → creative
      └─ Default             → factcheck (confidence: 0.5)
```

**Threshold:** Confidence < 0.6 → ambiguous. LLM fallback (devre dışı bırakılabilir).

### 2. FactCheckMode (`agent/modes/factcheck.py`)

A1-A4 pipeline'ı saran mode katmanı.

**Features:**
- `post_process()` — Anchor result + claim highlighting + severity breakdown
- `_build_highlights()` — Her correction için original→corrected mapping
- `_apply_highlights()` — Görsel vurgu formatı (🔴 ❌ ⚠️ ℹ️)
- `_severity_breakdown()` — CRITICAL/ERROR/WARNING/INFO dağılımı

**Data flow:**
```
RectificationResult
  ├─ Original / Corrected text
  ├─ Corrections list
  │    ├─ Conflict (severity, topic, confidence)
  │    ├─ original_text
  │    └─ corrected_text
  └─ Dedup stats (_dedup_skipped)
```

### 3. WorkflowMode (`agent/modes/workflow.py`)

Workflow Governor'ı saran mode katmanı.

**Violation types:**
| Type | Detects | Fix |
|---|---|---|
| `MISSING_STEP` | Adım tamamen atlanmış | "ekleyin" |
| `ORDER_VIOLATION` | Adımlar yanlış sırada | "taşıyın" |
| `INCOMPLETE_STEP` | Adım detaylandırılmamış | "detaylandırın" |
| `DUPLICATE_STEP` | Aynı adım tekrar edilmiş | "birleştirin" |
| `DEADLINE_VIOLATION` | Süre aşımı | "zamanlayın" |
| `RESOURCE_VIOLATION` | Kaynak eksik | "tahsis edin" |
| `QUALITY_VIOLATION` | Kalite standardı düşük | "iyileştirin" |

**Report:**
- Progress bar (█░) with percentage
- Violation list with display icons
- Fix suggestions

### 4. CreativeMode (`agent/modes/creative.py`)

C5 Constraint Engine — format ve stil denetimi.

**Format constraints:**
| Format | Char Limit | Max Emoji | Required Sections | Emoji Policy |
|---|---|---|---|---|
| tweet | 280 | 2 | — | serbest |
| post | 1000 | 3 | — | serbest |
| thread | 3000 | 5 | başlık | serbest |
| article | 5000 | 0 | başlık, giriş, sonuç, çağrı | yasak |
| newsletter | 10000 | 3 | başlık, giriş, sonuç | serbest |

**Auto-fix strategies:**
- **Char limit exceeded:** Smart truncation — cümle sonundan keser, ... ekler
- **Emoji over limit:** Fazla olanları kaldırır (article'da tümünü)
- **Missing sections:** Otomatik ekler (İçerik buraya... formatında)
- **Style violation:** Uyarır (otomatik düzeltme opsiyonel)

### 5. Reporter (`agent/core/reporter.py`)

Dört formatta çıktı üretir:

| Format | Method | Use Case |
|---|---|---|
| Terminal | `format_terminal()` | CLI output (emoji + colors) |
| JSON | `format_json()` | API response |
| HTML | `format_html()` | Dashboard / web |
| Markdown | `format_markdown()` | Documentation / issues |

### 6. ContextManager (`agent/core/context.py`)

Multi-turn session yönetimi.

**Features:**
- Message history tracking
- Seen claims dedup (session bazında)
- Mode tracking
- Metadata storage
- LLM format output

---

## 🔄 Data Flow: Full Pipeline

```
Step 1: Classify
───────────────
    User: "Verify: Singletons are great for everything"
    Classifier → factcheck (confidence: 0.85)
    
Step 2: Generate (Optional — LLM)
──────────────────────────
    LLM generates response
    
Step 3: Process (Anchor Engine)
──────────────────────────
    engine.process(query, llm_output)
    ├─ Topic extraction
    ├─ Knowledge retrieval (rules)
    ├─ Rule matching (A1-A4 / Governor / C5)
    ├─ Conflict detection
    ├─ Rectification
    └─ Report generation
    
Step 4: Post-Process (Mode)
──────────────────────────
    mode.post_process(query, raw, corrected, anchor_result)
    ├─ Claim highlighting
    ├─ Severity breakdown
    └─ Dedup tracking
    
Step 5: Report
──────────────
    reporter.format_*(result)
    └─ Terminal / JSON / HTML / Markdown
```

---

## 🎯 Design Decisions

| Decision | Rationale |
|---|---|
| **Deterministic first, LLM fallback** | Sub-ms latency for common cases |
| **Rule-based > Vector-based** | No GPU, no API, always same result |
| **Separate Mode classes** | Clean separation of concerns |
| **Reporter as separate module** | Any format, any time |
| **Seen claims per session** | Avoid duplicate corrections naturally |
| **Turkish + English classifier** | Bilingual support out of the box |

---

## 📁 File Map

```
agent/
├── core/
│   ├── agent.py          # 500+ lines — Main SafeLLMAgent
│   ├── classifier.py     # 250+ lines — Task routing
│   ├── context.py        # 200+ lines — Session context
│   └── reporter.py       # 280+ lines — Output formatting
├── modes/
│   ├── factcheck.py      # 200+ lines — A1-A4 post-process
│   ├── workflow.py       # 220+ lines — Governor integration
│   └── creative.py       # 350+ lines — C5 constraint engine
├── templates/
│   └── system_prompts.py # 100+ lines — LLM prompt templates
└── cli.py                # 300+ lines — CLI + REPL
```

---

## 🔒 Constraints

- **No background threads:** All synchronous
- **No external API calls in core path:** (LLM fallback is optional)
- **No GPU requirement:** Pure CPU, sub-ms latency
- **Max loopback:** 5 iterations (safety guard)
- **Max dedup per session:** Unlimited (never repeat same correction)
