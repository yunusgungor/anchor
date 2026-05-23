# Anchor: Deterministic Rectification of LLM Outputs

**Bağımsız Bilimsel Araştırma Projesi**

---

## Problem

LLM'ler olasılıksal sistemlerdir: aynı girdiyle her seferinde farklı çıktı üretebilirler.

$$y \sim p_\theta(y | x) \quad \text{— her adımda bir olasılık dağılımından örnekleme}$$

Kullanıcının bilgi tabanı (rules dosyaları) ise **deterministik ve kesin** bilgiler içerir. Aradaki ontolojik boşluğu kapatacak, LLM'den bağımsız bir matematiksel/fonksiyonel katman gereklidir.

Bu proje, herhangi bir LLM'in çıktısını, kullanıcının kendi bilgi tabanına göre **düzeltmek, doğrulamak ve tutarlı hale getirmek** için tasarlanmıştır.

## Araştırma Sorusu

Bir LLM'in olasılıksal çıktı uzayı $\mathcal{Y}_{LLM}$ ile kullanıcının deterministik bilgi uzayı $\mathcal{K}$ arasında, hiçbir LLM'e dokunmadan çalışan bir **Rectification Fonksiyonu** $\Phi: \mathcal{Y}_{LLM} \times \mathcal{K} \to \mathcal{Y}_{corrected}$ tasarlanabilir mi?

**Kısıt:** $\Phi$ asla ikinci bir LLM çağırmaz. Tüm işlemler string manipülasyonu, regex, hash/indeks ve embedding projeksiyonu ile yapılır.

## Temel Tanımlar

| Sembol | Anlam |
|---|---|
| $\mathcal{K} = \{k_1, ..., k_n\}$ | Kullanıcının rules dosyaları (her $k_i$ bir .md dosyası) |
| $\mathcal{T} = \{t_1, ..., t_m\}$ | Konu uzayı (topic space) |
| $f: \mathcal{K} \to \mathcal{T}$ | Her rule'un hangi konuda olduğunu belirten fonksiyon |
| $y_{raw} \in \Sigma^*$ | LLM'in ürettiği ham string |
| $\Phi(y_{raw}, \mathcal{K}) \to y'$ | Araştırmanın hedefi olan rectification fonksiyonu |
| $d: \Sigma^* \times \Sigma^* \to \mathbb{R}^+$ | İki string arasındaki fark metriği (edit distance) |
| $\delta: \Sigma^* \to \mathcal{P}(\mathcal{T})$ | LLM çıktısından konu çıkaran fonksiyon (topic extraction) |

## Araştırma Metrikleri

$$ \text{Accuracy} = \frac{\text{doğru düzeltme sayısı}}{\text{toplam düzeltme sayısı}} $$

$$ \text{Coverage} = \frac{\text{KB'de olup LLM'in doğru ürettiği konu}}{\text{toplam konu}} $$

$$ \text{False Positive Rate} = \frac{\text{yanlış alarm}}{\text{toplam düzeltme}} $$

$$ \text{Latency}_{p50}, \text{Latency}_{p99} $$

$$ \text{Edit Distance}_{avg} = \frac{1}{N} \sum_i \text{ED}(y_{raw}^{(i)}, y'^{(i)}) $$

## Metodoloji

### Faz I — Formal Model (✓)
Matematiksel tanımlar, performans hedefleri, başarı metrikleri.

### Faz II — Prototip (▶)
Python ile core engine: topic extraction, index yapısı, conflict detection, rectification.

### Faz III — Deneysel Değerlendirme
3 farklı LLM'de test (ChatGPT, Claude, Llama), 3 farklı domain'de test, metrik toplama.

### Faz IV — Yayın
Matematiksel ispatlar, performans grafikleri, white paper.

## Proje Yapısı

```
anchor/
├── README.md                 # Araştırma manifestosu
├── research/
│   ├── mathematical-framework.md
│   ├── experiments.md
│   └── results/
├── anchor/                   # Core engine (Python paketi)
│   ├── __init__.py
│   ├── models.py             # Veri modelleri
│   ├── index.py              # Rule index yapısı
│   ├── topic_extractor.py    # Topic extraction
│   ├── conflict_detector.py  # Conflict detection
│   └── rectifier.py          # Ana rectification pipeline
├── tests/
│   └── test_core.py
├── examples/
│   └── rules/                # Örnek rule dosyaları
└── requirements.txt
```

## Kullanım (Taslak)

```python
from anchor import KnowledgeEngine

# Rules dosyalarını yükle
engine = KnowledgeEngine("examples/rules")

# Herhangi bir LLM'den gelen çıktıyı düzelt
llm_output = "RISC-V NPU, genel amaçlı bir AI hızlandırıcıdır..."
corrected = engine.rectify(
    user_query="NPX1 nedir?",
    llm_output=llm_output
)
# → "RISC-V NPU (NPX1), edge AI için özel bir tasarımdır..."
```

## License

Bu bir araştırma projesidir. Tüm haklar saklıdır.
