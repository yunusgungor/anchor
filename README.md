# ⚓ Anchor Engine v3.3

> **Deterministic LLM Output Rectification** — Halüsinasyonları gerçek zamanlı düzeltir.

LLM'lerin olasılıksal çıktılarını, kullanıcının kural dosyalarındaki **deterministik bilgiyle** senkronize eden **model-agnostik** rectification engine.

Tek bir LLM çağrısına ihtiyaç duymaz, embedding modeli sadece build-time'da çalışır, runtime <10ms'dir.

[![Tests](https://img.shields.io/badge/tests-96%2F96%20passing-brightgreen)]()
[![Latency](https://img.shields.io/badge/latency-<10ms-blue)]()
[![Speedup](https://img.shields.io/badge/v3.3-188x%20faster-orange)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()

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
| "StateGuard bir güvenlik duvarıdır" | "StateGuard bir LLM validasyon katmanıdır" |
| "NPX1, NVIDIA Jetson ile rekabet eder" | "Edge AI, tarım/güvenlik — COTS ile birlikte çalışır" |

**Deterministik.** Aynı input → her zaman aynı output. **Sıfır runtime LLM maliyeti.**

---

## 🚀 Quick Start

```bash
# Kurulum
git clone https://github.com/yunusgungor/anchor.git
cd anchor
pip install -e ".[all]"

# Test (96/96)
pytest tests/ -q

# Demo Agent (6 senaryo)
PYTHONPATH=src python demo_agent.py

# Chat UI
PYTHONPATH=src python -m uvicorn anchor.ui.app:app --host 0.0.0.0 --port 8080
```

### Embedding (Opsiyonel, Build-time)

```python
from anchor.engine import AnchorEngine

# Embedding modeli build'te yüklenir, runtime'da sıfır ek yük
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
├── demo_agent.py                # 6 senaryolu demo
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
PYTHONPATH=src python demo_agent.py
```

6 senaryo içerir:
- **A**: Yanlış bilgi → CRITICAL override (NPX1/TSMC → SKY130)
- **B**: Eksik bilgi → WARNING ekleme
- **C**: Doğru bilgi → Değişiklik yok
- **D**: Cross-domain (StateGuard)
- **E**: Batch işleme (3 sorgu)
- **F**: Streaming simülasyonu

---

## 📄 Lisans

MIT © Yunus Güngör
