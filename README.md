# ⚓ Anchor Engine v3

> **Deterministic LLM Output Rectification**

LLM'lerin olasılıksal çıktılarını, kullanıcının kural dosyalarındaki deterministik bilgiyle senkronize eden **model-agnostik** rectification engine.

[![Tests](https://img.shields.io/badge/tests-75%2F75%20passing-brightgreen)]()
[![Latency](https://img.shields.io/badge/latency-<30ms-blue)]()
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
| "StateGuard, AI framework" | "LLM Output Rectification Framework" |

**Deterministik.** Aynı input → her zaman aynı output.

---

## 🚀 Quick Start

```bash
# Kurulum
git clone https://github.com/yunusgungor/anchor.git
cd anchor
pip install -e ".[all]"

# Test
pytest tests/ -q

# Chat UI başlat
PYTHONPATH=src python -m uvicorn anchor.ui.app:app --host 0.0.0.0 --port 8080
```

---

## 📁 Proje Yapısı

```
anchor/
├── src/anchor/
│   ├── __init__.py          # Core: Rule, Fact, Conflict, Correction
│   ├── engine.py            # Ana orkestrasyon motoru
│   ├── detect.py            # Claim extraction + fact matching
│   ├── rectify.py           # Patch engine (4 strateji)
│   ├── compliance/            # C5: Constraint Engine (format/style/strategy)
│   ├── parser/               # Format-agnostik rule parser (.md, .txt, .json, .csv)
│   ├── organize/             # Shard, Bloom filter, semantic index
│   ├── store/                # Binary index, lazy loading
│   ├── agent/                # SafeLLMAgent + LLMClient + RuleManager
│   └── ui/                   # FastAPI + Chat UI
├── rules/                    # Bilgi tabanı (örnek)
├── tests/                    # 75 test
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## 🧠 Mimarisi

```
┌─────────────────────────────────────────────────────────────┐
│  Anchor Engine v3                                             │
├─────────────────────────────────────────────────────────────┤
│  A1: Topic Extraction      → Trie + Regex                   │
│  A2: Knowledge Retrieval   → Bloom + Semantic + Binary Index │
│  A3: Conflict Detection    → Claim Extractor + Fact Matcher   │
│  A4: Rectification         → Patch Engine (override/patch)   │
├─────────────────────────────────────────────────────────────┤
│  C5: Constraint Engine     → Format/Style/Strategy checker    │
│      • Auto-fix: truncate, insert emoji, append CTA          │
│      • Flag: style violations (humor, tone)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Performans

| Metrik | Değer |
|---|---|
| Cold start | ~55ms |
| Query latency (p50) | ~9ms |
| Throughput | 234 QPS |
| Memory (1000 rule) | 3.6MB |
| Test coverage | 75/75 ✅ |

---

## 🔗 Karşılaştırma

| | RAG | Guardrails | Anchor |
|---|---|---|---|
| Halüsinasyon | Devam eder | Reddeder | **Düzeltir** |
| LLM Çağrısı | 1 | 2 | **1** |
| Maliyet | Normal | 2x | **0** |
| Determinizm | ❌ | ❌ | **✅** |

---

## 📄 Lisans

MIT © Yunus Güngör
