# Quick Start Guide

> Anchor Agent'i 5 dakikada çalıştırın.

---

## 📦 Prerequisites

- Python 3.10+
- pip

## 🚀 Installation

```bash
# 1. Clone
cd anchor/demo-agent

# 2. Install
pip install -e .

# 3. Doğrulama
python -c "from agent.core.classifier import TaskClassifier; print('✅ Anchor Agent ready!')"
```

## 🎮 Run Demo Scenarios

```bash
# Tüm 10 senaryoyu çalıştır
python run_demo.py

# Tek senaryo (örn: Negation Detection)
python run_demo.py --scenario 1

# JSON çıktı
python run_demo.py --scenario 4 --json

# Senaryoları listele
python run_demo.py --list
```

### Expected output:
```
🔧 Anchor Demo Engine başlatılıyor...
   ✅ Rules loaded: 23 rules (73ms)

══════════════════════════════════════════════════════════════════════
  [1/10] A1: Negation-Aware Regex Detection
══════════════════════════════════════════════════════════════════════
  Mode: FACTCHECK | Feature: Negation-Aware Detection (A1)
  ... (detaylar)

══════════════════════════════════════════════════════════════════════
  📊 DEMO SUMMARY: 10/10 PASSED
══════════════════════════════════════════════════════════════════════
```

## 🧪 Run Tests

```bash
# Tüm testler
python -m pytest tests/test_agent.py -v

# Tek bir test class'ı
python -m pytest tests/test_agent.py::TestFactCheckMode -v

# Tek bir test
python -m pytest tests/test_agent.py::TestFactCheckMode::test_01_init -v

# Doğrudan çalıştır (verbosity 2)
python tests/test_agent.py
```

### Expected: `55 passed`

## 🔧 Configuration

Anchor, `rules/` dizinindeki markdown dosyalarını otomatik okur:

```
rules/
├── architecture/
│   ├── design-patterns.md
│   └── solid-principles.md
├── tdd/
│   ├── red-green-refactor.md
│   └── test-pyramid.md
├── workflows/
│   ├── bug-fix.md
│   ├── code-review.md
│   └── release.md
└── ci-cd/
    ├── automated-testing.md
    └── deployment.md
```

Her kural dosyası belirli bir konuyu kapsar. Anchor, LLM çıktısını bu kurallarla karşılaştırır.

## 📝 Add Custom Rules

Yeni kural eklemek için `rules/<category>/<rule-name>.md` oluşturun:

```markdown
# My Rule

> Bu kural ne işe yarar?

- Kural 1: Açıklama
- Kural 2: Açıklama

## Workflow Steps

- [ ] Adım 1: Yapılacak iş
- [ ] Adım 2: Yapılacak iş
```

Anchor, yeni kuralı otomatik olarak algılar ve engine'de kullanır.

## 🎯 Example Usage

```python
from anchor import AnchorEngine
from agent.modes.factcheck import FactCheckMode

# Engine
engine = AnchorEngine(rules_path="/path/to/rules")
engine.build()

# Mode
mode = FactCheckMode()

# Process
query = "Are Singletons good for everything?"
output = "Yes, Singletons are the best pattern for shared state."

result = engine.process(query, output)
mode_result = mode.post_process(
    query=query,
    raw=output,
    corrected=result.corrected,
    anchor_result=result,
)

# Check result
if result.modified:
    print(f"Düzeltildi! {len(result.corrections)} correction")
else:
    print("Her şey doğru!")
```

## 🐛 Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'agent'` | Wrong working directory | `cd demo-agent` first |
| `0 rules loaded` | `rules/` dizini yok | `ln -s ../rules rules` |
| Demo slow | LLM fallback devrede | `use_llm=False` ile test |
| Test fails with `Severity` errors | API değişikliği | `pip install -e .` ile yeniden yükle |

## 📚 Documentation

| Document | Contents |
|---|---|
| [README.md](./README.md) | Project overview, features, roadmap |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design, components, data flow |
| [DEMO_GUIDE.md](./DEMO_GUIDE.md) | 10 demo scenario walkthrough |
| **This file** | Installation & quick start |
