# Anchor Engine 🔗

> **Deterministic Reliability for AI Outputs**  
> *Gerçeklerle çelişmeyen, kurallara uyan, formatı bozmayan AI çıktıları.*

---

## 🚀 Overview

**Anchor** is a lightweight, deterministic correction engine that sits *between* your LLM and your user. It validates AI outputs against a knowledge base of rules — detecting factual errors, workflow violations, and format deviations — then rectifies them automatically.

```
User Query → LLM → Raw Output → ⚓ ANCHOR → Corrected Output → User
                                    │
                             Rules & Facts
```

### Key Capabilities

| Capability | What It Does | Anchor Feature |
|---|---|---|
| 🔍 **FactCheck** | Gerçek doğrulama — LLM'in yanlış bilgi üretmesini engeller | A1–A4 Pipeline |
| ⚙️ **Workflow** | Adım-atlama tespiti — süreçlerin eksiksiz takibini sağlar | Governor |
| 🎨 **Creative** | Format/stil denetimi — tweet/post/makale kurallarını uygular | C5 Engine |
| 🔄 **Dedup** | Tekrar eden düzeltmeleri önler — seen_claims mekanizması | Memory Tracker |
| 🛡️ **Cross-Rule** | Çakışan kurallar arasında en uygun düzeltmeyi seçer | Conflict Resolution |

---

## 🏗️ Architecture

```
anchor-demo-agent/
├── agent/
│   ├── core/
│   │   ├── agent.py        # SafeLLMAgent — Anchor'ı saran ana sınıf
│   │   ├── classifier.py   # TaskClassifier — Query'yi doğru mode'a yönlendirir
│   │   ├── context.py      # ContextManager — Multi-turn session yönetimi
│   │   └── reporter.py     # Reporter — 4 formatta çıktı (terminal/JSON/HTML/Markdown)
│   ├── modes/
│   │   ├── factcheck.py    # 🔍 FactCheckMode — A1-A4 pipeline + highlight
│   │   ├── workflow.py     # ⚙️ WorkflowMode — Governor integration
│   │   └── creative.py     # 🎨 CreativeMode — C5 Constraint Engine
│   ├── templates/
│   │   └── system_prompts.py  # LLM prompt şablonları
│   └── cli.py             # CLI entry point
├── tests/
│   └── test_agent.py      # 55 unit test
├── run_demo.py            # 10-scenario demo runner
├── run.py                 # Main runner
└── setup.py              # Package setup
```

---

## ⚡ Quick Start

```bash
# Install
cd demo-agent && pip install -e .

# Run all demos
python run_demo.py

# Run single scenario
python run_demo.py --scenario 1

# Run tests
python -m pytest tests/test_agent.py -v
```

📖 Detaylı: [QUICKSTART.md](./QUICKSTART.md)

---

## 🎯 Demo Scenarios

| # | Scenario | Feature | Status |
|---|---|---|---|
| 01 | 🔍 A1: Negation Detection | `NOT`, `never`, `avoid` tespiti | ✅ |
| 02 | 🔍 A2: Semantic Similarity | TF-IDF + embedding matching | ✅ |
| 03 | 🔍 A3: Causal Conflict | CCI heuristic ile neden-sonuç analizi | ✅ |
| 04 | 🔍 A4: Multi-Vector | Aynı metinde çoklu düzeltme | ✅ |
| 05 | ⚙️ Workflow: Missing Steps | Eksik adım tespiti | ✅ |
| 06 | ⚙️ Workflow: Order Violation | Sıra ihlali | ✅ |
| 07 | 🎨 C5: Character Limit | Smart auto-truncation | ✅ |
| 08 | 🎨 C5: Emoji + Sections | Emoji temizleme + bölüm ekleme | ✅ |
| 09 | 🔄 Dedup + Cross-Rule | Tekrar engelleme + çakışma çözümü | ✅ |
| 10 | 🚀 Full Pipeline | Tüm Anchor kabiliyetleri tek seferde | ✅ |

📖 Detaylı: [DEMO_GUIDE.md](./DEMO_GUIDE.md)

---

## 🔬 Core Features

### A1: Negation-Aware Detection
Anchor, olumlu/olumsuz ifadeleri ayırt eder:
- `"Singleton is NOT appropriate"` → olumsuz tespit edilir
- `"Singleton should be used"` → olumlu, düzeltme gerekmez
- 3-strat regex motoru: `\b(not|never|without|avoid|...)\b`

### A2: Multi-Strategy Similarity
Üç katmanlı benzerlik:
1. **TF-IDF** — Kosinüs benzerliği
2. **Edit Distance** — Levenshtein fuzzy matching
3. **Keyword Overlap** — Token bazlı eşleşme

### A3: Causal Conflict Intelligence
CCI heuristic ile neden-sonuç hatalarını tespit eder:
- `"Since X is wrong, we should Y"` — X doğruysa yanlış nedensellik
- Loopback limiti: maksimum 5, sonsuz döngü koruması

### A4: Strategic Rectification
Her düzeltme için en uygun strateji:
- **Override** — Tamamen değiştir
- **Prepend/Append** — Başına/sonuna ekle
- **Merge** — Birleştir

### Governor (Workflow)
Adım-adım süreçleri doğrular:
- **Missing Step**: Eksik adım tespiti
- **Order Violation**: Sıra ihlali
- **Incomplete Step**: Eksik detay
- **Duplicate Step**: Tekrar eden adım

### C5 (Creative)
Format kısıtlamalarını denetler:
- **Character Limit**: Smart truncation (cümle bilinciyle)
- **Emoji Control**: Yasaklama / limit / serbest
- **Section Check**: Zorunlu bölümler (başlık, giriş, sonuç, çağrı)
- **Style Enforcement**: Tone, voice, dil seviyesi

---

## 📊 Test Coverage

**55 tests** — tümü geçiyor:

```
✅ FactCheckMode — 9 test (init, severity, highlights, dedup, post-process)
✅ WorkflowMode — 7 test (parsing, breakdown, progress, report, fixes)
✅ CreativeMode — 17 test (char limit, emoji, sections, format detection, auto-fix)
✅ Classifier — 8 test (routing, confidence, ambiguity, test suite)
✅ Reporter — 4 test (terminal, json, markdown, all modes)
✅ ContextManager — 7 test (messages, reset, format, metadata)
✅ Integration — 3 test (routing, severity, result objects)
```

---

## 🧠 How It Works

### Without Anchor
```
LLM: "Singletons are great! Use them everywhere." → ❌ User sees incorrect advice
```

### With Anchor
```
LLM: "Singletons are great! Use them everywhere."
           ↓
Anchor: Detects claim ≠ "Singleton should be used sparingly"
           ↓
Anchor: Rectifies → "Be cautious with Singletons. Use them sparingly."
           ↓
User: ✅ Gets correct information
```

### Flow
1. **Classify** — Query analiz edilir: factcheck / workflow / creative
2. **Generate** — LLM çıktı üretir (bilingli şekilde, Anchor koruyacak)
3. **Detect** — Anchor, çıktıyı kurallarla karşılaştırır
4. **Rectify** — Hatalı kısımlar otomatik düzeltilir
5. **Report** — Her düzeltme belgelenir (severity, strateji, konum)

---

## 🏆 Why Anchor?

| Özellik | Anchor | Diğer Çözümler |
|---|---|---|
| **Deterministic** | ✅ Her çalıştırmada aynı sonuç | ❌ LLM çağrısına bağlı |
| **Sub-ms latency** | ✅ Kural bazlı, GPU gerekmez | ❌ API call = saniyeler |
| **No API key** | ✅ Tamamen local çalışır | ❌ OpenAI/Anthropic bağımlısı |
| **Explainable** | ✅ Her düzeltme kaynaklı | ❌ Black box |
| **Multi-mode** | ✅ FactCheck + Workflow + Creative | ❌ Tek amaçlı |
| **Custom rules** | ✅ Markdown, istediğin kadar | ❌ Sabit kurallar |

---

## 📦 Project Structure

```
anchor/
├── src/anchor/        # Core engine (A1-A4, Governor, C5)
├── rules/             # 23+ kural dosyası (markdown)
├── demo-agent/        # Agent layer (modes, classifier, reporter)
│   ├── agent/         # Agent classes
│   ├── tests/         # 55 test
│   ├── docs/          # Documentation
│   ├── run_demo.py    # Demo runner
│   └── setup.py       # Package
└── README.md          # Bu dosya
```

---

## 🛣️ Roadmap

- [x] **Phase 1** Core Modes — FactCheck, Workflow, Creative
- [x] **Phase 2** Demo Runner — 10 demo senaryosu
- [x] **Phase 3** Test Suite — 55 unit test
- [x] **Phase 4** Documentation — README, ARCHITECTURE, QUICKSTART, DEMO_GUIDE
- [ ] **Phase 5** Deployment — Dockerfile, Makefile, CI

---

## 📄 License

MIT — Use freely, contribute happily.

---

## 👤 Author

**Yunus Güngör**  
🔗 [github.com/yunusgungor](https://github.com/yunusgungor)
