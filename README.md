# ⚓ Anchor Engine v4.4.1

> **Deterministic LLM Output Rectification** — Halüsinasyonları gerçek zamanlı düzeltir.

LLM'lerin olasılıksal çıktılarını, kullanıcının kural dosyalarındaki **deterministik bilgiyle** senkronize eden **model-agnostik** rectification engine.

Tek bir LLM çağrısına ihtiyaç duymaz, embedding modeli sadece build-time'da çalışır, runtime **<1ms**'dir.

[![Tests](https://img.shields.io/badge/tests-96%2F96%20passing-brightgreen)]()
[![Latency](https://img.shields.io/badge/latency-%3C1ms-blue)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![PyPI](https://img.shields.io/badge/pypi-v4.4.1-orange)](https://pypi.org/project/anchor-engine/)

---

## 🎯 Ne Yapar?

```
Kullanıcı Sorusu → LLM → Ham Cevap → Anchor → Düzeltilmiş Cevap
                                              ↑
                                       Bilgi Tabanı (rules/)
```

| LLM Der ki | Anchor Düzeltir |
|---|---|
| "NPX1, TSMC 7nm'de üretilir" | "SKY130 (130nm), OpenLane ile" |
| "Singleton'lar her yerde kullanılabilir" | "Singleton'lar dikkatli kullanılmalıdır" |
| "Repository pattern tight coupling yaratır" | "Repository pattern temiz ayrıştırma sağlar" |

**Deterministik.** Aynı input → her zaman aynı output. **Sıfır runtime LLM maliyeti.**

---

## 🚀 Quick Start

### Installation

```bash
# Core engine (tüm özellikler, embedding olmadan)
pip install anchor-engine

# Tam kurulum (embedding + LLM + UI)
pip install "anchor-engine[all]"

# Sadece LLM desteği
pip install "anchor-engine[llm]"
```

### Usage

```python
from anchor.engine import AnchorEngine

# Rules dizinindeki kurallarla engine'i başlat
engine = AnchorEngine(rules_path="/path/to/my/rules")
engine.build()

# LLM çıktısını doğrula
result = engine.process(
    user_query="NPX1 specs?",
    llm_output="NPX1 uses TSMC 7nm process",
)

if result.modified:
    print(f"Düzeltildi! {len(result.corrections)} hata")
    print(f"✅ {result.corrected}")
else:
    print("✅ Hiçbir düzeltme gerekmedi")
```

### Test

```bash
pytest tests/ -q
```

### Demo Agent

```bash
cd demo-agent && python run_demo.py
```
engine = AnchorEngine("rules/", use_embedding=True)
engine.build()  # ~27s (ilk sefer, model indirme + pre-compute)

result = engine.process("NPX1 nedir?", llm_output)
# Runtime: ~10ms (pre-computed embeddings sayesinde)
```

---

## 📁 Proje Yapısı

```
anchor/
├── src/anchor/
│   ├── __init__.py              # Core: Rule, Conflict, Correction, Severity
│   ├── engine.py                # A1-A4 Pipeline orkestrasyonu
│   ├── detect.py                # ClaimExtractor + FactMatcher + ConflictDetector
│   ├── rectify.py               # PatchEngine (4 strateji)
│   ├── judge/                   # 3-Phase Judge Pipeline
│   │   ├── embedding.py         #   Phase 1: Sentence-transformer similarity
│   │   ├── llm_judge.py         #   Phase 2: LLM-as-Judge (opsiyonel)
│   │   ├── enricher.py          #   Phase 3: Build-time paraphrase generation
│   │   └── cache.py             #   Judge verdict cache (LRU, md5 key)
│   ├── compliance/              # C5: Constraint Engine
│   ├── parser/                  # Format-agnostik rule parser (.md, .txt)
│   ├── organize/                # ShardRouter, BloomFilter, SemanticIndex
│   ├── store/                   # ScalableRuleStore + BinaryIndex (JSON+NPZ)
│   ├── agent/                   # SafeLLMAgent + LLMClient + RuleManager
│   └── ui/                      # FastAPI + Chat UI
├── rules/                       # Bilgi tabanı (örnek, 4 rule)
│   ├── hardware/riscv-npu.md
│   ├── hardware/sky130-pdk.md
│   ├── projects/state-guard.md
│   └── concepts/architectural-sovereignty.md
├── tests/                       # 96 test
├── benchmark/                   # Performans benchmark
├── demo-agent/                  # 7 entegre senaryolu tanıtım paketi
├── docs/manifesto.md            # Matematiksel framework
├── Dockerfile + docker-compose.yml
└── pyproject.toml
```

---

## 🧠 Mimarisi

### Pipeline (A1-A4)

```
┌──────────────────────────────────────────────────────────────────┐
│  Anchor Engine v3.3                                                │
├──────────────────────────────────────────────────────────────────┤
│  A1: Topic Extraction      → Trie + Regex + Alias Match  < 1ms   │
│  A2: Knowledge Retrieval   → BloomFilter → Shard → Semantic Index │
│                              LazyLoad + LRU Cache (200 rule)      │
│  A3: Conflict Detection    → ClaimExtractor + FactMatcher         │
│                              α·d_edit + β·d_sem + γ·d_neg        │
│                              + d_emb (pre-computed batch cache)   │
│  A4: Rectification         → PatchEngine (4 strateji)            │
│                              CRITICAL/ERROR/WARNING/INFO          │
├──────────────────────────────────────────────────────────────────┤
│  C5: Constraint Engine     → Format/Style/Strategy/Tone checker   │
│      • Auto-fix: truncate, insert emoji, append CTA              │
│      • Flag: style violations (humor, tone)                      │
└──────────────────────────────────────────────────────────────────┘
```

### 3-Phase Judge Pipeline

```
┌─ Phase 1 (DEFAULT) ──────────────────────────────────────────┐
│  Embedding-based similarity                                   │
│  Model: paraphrase-multilingual-MiniLM-L12-v2 (384-dim)       │
│  Build-time:  encode_batch(facts) → float16 → NPZ            │
│  Runtime:      claim_emb (LRU cache) + np.dot(fact_emb)      │
│  Threshold:    d_emb<0.5→SIMILAR, >0.7→DIFFERENT, else→NEUTRAL│
│  Graceful:     LLM→Embedding→Jaccard→safe default            │
└──────────────────────────────────────────────────────────────┘
┌─ Phase 2 (OPSİYONEL) ────────────────────────────────────────┐
│  LLM-as-Judge for borderline (0.5 ≤ d_emb ≤ 0.7)            │
│  Provider: OpenAI / Ollama / Mock                            │
│  Cache: JudgeCache (LRU, md5 key, deterministik)             │
└──────────────────────────────────────────────────────────────┘
┌─ Phase 3 (BUILD-TIME) ───────────────────────────────────────┐
│  RuleEnricher → LLM paraphrase generation during build()     │
│  Sonuç: enriched_facts → binary index → runtime kullan      │
└──────────────────────────────────────────────────────────────┘
```

### Conflict Detection Detayı

```
Claim = α·d_edit + β·d_sem + γ·d_neg + (d_emb embedding-aware)

  d_edit  = SequenceMatcher (Levenshtein)        α=0.4
  d_sem   = Jaccard word overlap                 β=0.4
  d_neg   = Regex negation markers (değil/yok)   γ=0.2
  d_emb   = cosine similarity (pre-computed, ~3μs)

Severity Mapping:
  CRITICAL (4)  → OVERRIDE sentence
  ERROR (3)     → PATCH sentence + doğrusu
  WARNING (2)   → INSERT after sentence
  INFO (1)      → APPEND footnote
  NONE (0)      → no change
```

---

## 📊 Performans (v3.3.0 Benchmark)

| Sorgu | **ÖNCE (v3.2)** | **SONRA (v3.3)** | **Hızlanma** |
|-------|----------------|-----------------|-------------|
| NPX1 query | 2,609ms | **23ms** | **113×** 🚀 |
| StateGuard | 1,499ms | **3ms** | **500×** 🚀 |
| SKY130 | 1,537ms | **4ms** | **384×** 🚀 |
| **Ortalama** | 1,882ms | **10ms** | **188×** 🚀 |

| Metrik | Değer |
|--------|-------|
| Cold start (binary index) | ~10ms |
| Query latency (p50) | ~5ms |
| Embedding model boyutu | 458MB (sadece build) |
| Runtime bellek | ~0MB (pre-computed NPZ) |
| Binary index boyutu | ~12KB (JSON+NPZ) |
| Test coverage | **96/96** ✅ (3.27s) |
| Rule kapasitesi | 10K+ (Bloom + Shard + LazyLoad) |

### Root Causes Fixed (v3.3)

| # | Problem | Çözüm |
|---|---------|-------|
| 1 | YAML frontmatter "---" fact sanılıyor | Skip filter eklendi |
| 2 | Double embedding compute (d_sem + d_emb) | Deduplicate edildi |
| 3 | Claim encoding cache yok | LRU cache (max 10) |
| 4 | Build-time facts ≠ runtime facts | Pre-computed fact_texts kullan |
| 5 | JSONEncoder np.ndarray → list | NPZ storage |

---

## 🔗 RAG / Guardrails / Anchor Karşılaştırması

| | RAG | Guardrails | **Anchor** |
|---|---|---|---|
| **Halüsinasyon** | Devam eder 🚫 | Reddeder 🚫 | **Düzeltir** ✅ |
| **LLM Çağrısı** | 1 | 2+ | **0** (runtime) |
| **Latency** | ~1-3s | ~200-500ms | **<10ms** |
| **Maliyet** | Normal | 2x | **$0** |
| **Determinizm** | ❌ | ❌ | **✅** |
| **Model-agnostik** | ❌ | ❌ | **✅** |
| **Test edilebilir** | Zor | Zor | **✅ (pytest)** |
| **CI/CD entegrasyonu** | ❌ | ❌ | **✅** |

Anchor, LLM'in **önünde** değil, **sonunda** çalışır — RAG'ın aksine LLM'in prompt'u görmezden gelme riski yoktur.

---

## 🧪 Demo

```bash
cd demo-agent && python run_all.py
```

7 entegre senaryo, tüm Anchor kabiliyetlerini sergiler:
- **Fact Conflict Detection**: CRITICAL/WARNING/INFO conflict'ler
- **Confusion Table**: Bilinen yanlış claim'leri CRITICAL override
- **Workflow Governor**: Step order + completeness validation
- **FlowConflictMatcher**: Diagram akışına aykırı LLM output'ları
- **Negation-Aware**: "no X", "skip Y" detection
- **Constraint Engine**: C5 creative compliance layer
- **Judge Pipeline**: Embedding + LLM-as-Judge borderline arbitration
- **Diagram Extraction**: Mermaid/ASCII → flow facts
- **ScalableStore**: Bloom filter, LRU cache, domain sharding
- **CLI/UI**: anchor-cli aracı + FastAPI dashboard

---

## 📄 Lisans

MIT © Yunus Güngör
