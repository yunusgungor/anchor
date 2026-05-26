# ⚓ Anchor Engine — Features

> **Deterministik LLM Rectification Engine**
> LLM'lerin olasılıksal çıktılarını, kullanıcının deterministik bilgi tabanıyla senkronize eden model-agnostik doğrulama ve düzeltme motoru.
> Anchor v4.4.3 | Plugin: anchor-rectifier v1.5.0 | 23 kural

---

## İçindekiler

- [1. Deterministik Çıktı Güvencesi](#1-deterministik-çıktı-güvencesi)
- [2. Çok Katmanlı Tespit Stratejileri](#2-çok-katmanlı-tespit-stratejileri)
- [3. Format-Agnostik Kural Motoru](#3-format-agnostik-kural-motoru)
- [4. Type-Aware Rule Filtering](#4-type-aware-rule-filtering)
- [5. Corrective Mode](#5-corrective-mode)
- [6. Çok Dilli ve Türkçe Desteği](#6-çok-dilli-ve-türkçe-desteği)
- [7. Binary Index ile Hızlı Başlangıç](#7-binary-index-ile-hızlı-başlangıç)
- [8. Diagram-Aware Validasyon](#8-diagram-aware-validasyon)
- [9. Hermes Plugin Entegrasyonu](#9-hermes-plugin-entegrasyonu)
- [10. False Positive Önleme](#10-false-positive-önleme)
- [11. Metrikler ve Gözlemlenebilirlik](#11-metrikler-ve-gözlemlenebilirlik)
- [12. Negation-Aware Tespit](#12-negation-aware-tespit)
- [13. Cross-Rule FP Filtresi](#13-cross-rule-fp-filtresi)
- [14. Loopback Limiti ve Guards](#14-loopback-limiti-ve-guards)
- [15. Correct-Statement Detection](#15-correct-statement-detection)
- [16. Geliştirici Araçları](#16-geliştirici-araçları)

---

## 1. Deterministik Çıktı Güvencesi

LLM'lerin doğası gereği **her seferinde farklı** çıktı üretme riskine karşı, Anchor `.md` dosyalarına yazdığın kuralları **birebir** uygular.

| Özellik | Açıklama |
|---------|----------|
| **Kural bazlı** | LLM-on-LLM validation'ın aksine, kurallar değişmedikçe sonuç değişmez |
| **Model-agnostik** | Hangi LLM kullanılırsa kullanılsın aynı kurallar işler |
| **Deterministik** | Aynı girdi → aynı çıktı, olasılıksal sapma yok |

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   LLM Çıktısı    │────▶│   Anchor        │────▶│  Düzeltilmiş      │
│  (probabilistic) │     │   23 Kural      │     │  Çıktı            │
│                  │     │   ile Denetle   │     │  (deterministik)  │
└─────────────────┘     └─────────────────┘     └──────────────────┘
                                 │
                                 ▼
                         ┌─────────────────┐
                         │  Detaylı Rapor  │
                         │  (kaç ihlal,    │
                         │   hangi kural)  │
                         └─────────────────┘
```

---

## 2. Çok Katmanlı Tespit Stratejileri

Anchor, aynı ihlali farklı açılardan yakalamak için **6 farklı tespit katmanı** kullanır:

| Katman | Mekanizma | Ne Zaman Çalışır |
|--------|-----------|------------------|
| **Phase 0** | Direct known-wrong scan | Yanlış ifadeyi birebir eşleştirir, çok hızlı |
| **NLP-based** | Claim extraction | LLM çıktısından iddiaları çıkarır ve kurallarla karşılaştırır |
| **Token overlap** | Token düzeyinde eşleşme | Doğru ifadeyi token düzeyinde tanır |
| **Negation-aware** | 3 strateji | "X yapma" gibi olumsuzlamaları doğru işler |
| **Fuzzy matching** | 9 strateji (≥3 chars) | Minor varyasyonları tolere eder (typo, ek, küçük/büyük harf) |
| **Cross-rule FP filter** | TF-IDF distinctive keywords | Aynı anda birden fazla kural tetiklenince FP önler |

### Tespit Akışı

```
LLM Çıktısı
    │
    ├─▶ Phase 0: Known-Wrong Scan ──▶ Anında ihlal tespiti
    │
    ├─▶ NLP Claim Extraction ──────▶ İddiaları çıkar, kurallarla eşleştir
    │
    ├─▶ Fuzzy Matching (9 strateji) ──▶ Varyasyonları tolere et
    │
    ├─▶ Negation Check ─────────────▶ Olumsuzlama varsa ters mantık uygula
    │
    ├─▶ Cross-Rule FP Filter ──────▶ Aynı anda tetiklenen kuralları analiz et
    │
    └─▶ Token Overlap Check ───────▶ Doğru ifade tespiti
```

---

## 3. Format-Agnostik Kural Motoru

Kurallar **düz markdown** dosyalarıdır — özel bir dil, derleme aşaması, JSON şeması gerekmez.

```
~/.hermes/anchor-rules/
├── architecture/
│   ├── clean-architecture.md
│   └── solid-principles.md
├── workflows/
│   ├── tdd-cycle.md
│   ├── code-review.md
│   ├── bug-fix.md
│   └── release-process.md
├── tdd/
│   └── red-green-refactor.md
├── git-practices.md
├── clean-code.md
├── security.md
└── ...
```

### Kural Dosyası Yapısı

```yaml
---
topic: "TDD Red-Green-Refactor Cycle"
aliases: ["tdd-cycle", "red-green-refactor", "test-first"]
tags: [workflow, tdd, testing]
type: hybrid
steps:
  - id: write-failing-test
    title: "Red: Başarısız Test Yaz"
    mandatory: true
---
# Kural içeriği (markdown)
## The Three Laws of TDD
1. You must not write production code until...
2. You must not write more of a unit test...
3. You must not write more production code...
```

### Frontmatter Alanları

| Alan | Zorunlu | Açıklama |
|------|---------|----------|
| `topic` | ✅ | Kuralın ana konusu |
| `aliases` | ❌ | Alternatif eşleşme anahtarları |
| `tags` | ❌ | Etiketler |
| `type` | ❌ | `domain`, `workflow`, `hybrid` (default: `domain`) |
| `priority` | ❌ | Kural önceliği (1-10, default: 5) |
| `steps` | ❌ | Workflow adımları (workflow/hybrid tipleri için) |
| `strictness` | ❌ | Sıkılık derecesi (0.0 - 1.0) |

---

## 4. Type-Aware Rule Filtering

Anchor, içerik türüne göre hangi kuralların uygulanacağını akıllıca seçer. **Özellikle eğitim/açıklama içeriğinde false positive'leri önler.**

### Kural Tipleri

| Tip | `type:` frontmatter | Normal Mod | Eğitim İçeriği |
|-----|---------------------|------------|----------------|
| **Domain** | `type: domain` *(default)* | ✅ Tüm çakışmalar kontrol edilir | ✅ Tüm çakışmalar (threshold 0.5) |
| **Hybrid** | `type: hybrid` | ✅ Tüm çakışmalar | ✅ Sadece factual çakışmalar (threshold 0.7), ❌ Step ihlalleri atlanır |
| **Workflow** | `type: workflow` | ✅ Tüm çakışmalar | ❌ **Tamamen atlanır** |

### Ne Zaman Hangi Tip Kullanılır

| Kural İçeriği | Önerilen Tip |
|---------------|-------------|
| Saf teknik bilgi (SOLID prensipleri, mimari kararlar, kod standartları) | `domain` |
| Saf süreç adımları (commit akışı, release prosedürü) | `workflow` |
| Hem bilgi hem süreç içeren (severity tablosu + bug fix adımları) | `hybrid` |

### Akış Diyagramı

```
LLM Çıktısı geldi
    │
    ├─▶ Eğitim içeriği mi?
    │       │
    │       ├─▶ EVET → workflow kurallarını atla, domain %100 çalışır
    │       │         hybrid: sadece factual çakışmalar
    │       │
    │       └─▶ HAYIR → tüm kurallar tam yetkili
    │
    ▼
Her kural için confidence threshold kontrolü
    │
    ├─▶ domain:  conf >= 0.5
    ├─▶ hybrid:  conf >= 0.7
    └─▶ workflow: conf >= 0.7
```

---

## 5. Corrective Mode

Anchor sadece **uyarmakla kalmaz**, çıktıyı **otomatik düzeltir**.

### İki Mod

| Mod | Açıklama | Kullanım |
|-----|----------|----------|
| **Annotated** | İhlalleri tespit eder, raporlar, orijinal metni korur | Geliştirme/debug |
| **Corrective** | İhlalleri tespit eder, **doğrudan düzeltilmiş metni** kullanıcıya iletir | Üretim |

### apply_corrections() Pipeline

```python
# 1. İhlalleri tespit et
corrections = detect(output, rules)

# 2. Confidence threshold kontrolü
valid = [c for c in corrections if c.confidence >= threshold]

# 3. Düzeltmeleri uygula
corrected_output = apply_corrections(output, valid)

# 4. Detaylı rapor üret
report = {
    "total": len(valid),
    "by_rule": {"tdd-cycle": 3, "solid": 1},
    "details": [
        {"rule": "tdd-cycle", "original": "...", "corrected": "..."},
        ...
    ]
}
```

---

## 6. Çok Dilli ve Türkçe Desteği

Anchor, **Türkçe ve İngilizce karışık** ortamlarda doğru çalışacak şekilde tasarlanmıştır.

### Özellikler

| Özellik | Versiyon | Açıklama |
|---------|----------|----------|
| **Türkçe Karakter Normalizasyonu** | v4.4.3 | `çikolata` ≠ `cikolata` gibi yanlış eşleşmeleri önler |
| **Bilingual Confusion Table** | v4.4.2 | İngilizce/Türkçe karışık kullanımda alias genişletme (LSP/SRP/OCP) |
| **Türkçe Negation-Aware** | v4.4.1 | Türkçe olumsuz yapıları doğru işler |
| **Per-rule seen_claims** | v4.4.1 | Her kural için daha önce görülen iddiaları takip eder |

### Normalizasyon Örnekleri

| Girdi | Normalize | Eşleşme |
|-------|-----------|---------|
| `çikolata` | `cikolata` | ✅ |
| `şirket` | `sirket` | ✅ |
| `örnek kod` | `ornek kod` | ✅ |
| `İstanbul` | `istanbul` | ✅ |

---

## 7. Binary Index ile Hızlı Başlangıç

Anchor, **BinaryIndexManager** ile kural indeksini serileştirerek soğuk başlangıç süresini **5 saniyeden 123ms'ye** düşürür.

```
Başlangıç
    │
    ├─▶ Binary index var mı?
    │       │
    │       ├─▶ EVET → ~123ms: index'i yükle, hazır
    │       │
    │       └─▶ HAYIR → ~5sn: tüm kuralları parse et, index'i oluştur, serialize et
    │
    ▼
Hazır
```

### İndex Bileşenleri

| Bileşen | Açıklama |
|---------|----------|
| Bloom filter | Hızlı varlık/yokluk kontrolü |
| Semantic index | Anlamsal benzerlik için embedding indeksi |
| Shard topic map | Topic'lere göre parçalanmış kural haritası |
| Distinctive keyword index | TF-IDF tabanlı ayırt edici kelime indeksi |

---

## 8. Diagram-Aware Validasyon

Anchor, Mermaid ve ASCII diyagramlarını **parse eder** ve sentetik validasyon yapabilir.

### Desteklenen Validasyonlar

| Validasyon Türü | Açıklama |
|-----------------|----------|
| **FlowConflictMatcher** | Flowchart içinde adım sırası ihlali tespiti |
| **Synthetic step validation** | Geçersiz geçişler, kopuk akışlar |
| **Mermaid diyagram parse** | `graph TD`, `sequenceDiagram`, `flowchart LR` |
| **ASCII diagram parse** | Basit metin tabanlı akış şemaları |

```
┌──────────┐     ┌──────────┐
│  Step 1  │────▶│  Step 2  │
└──────────┘     └──────────┘
                      │
                      ▼
                 ┌──────────┐
                 │  Step 3  │
                 └──────────┘
                      │
               ✗ Geçersiz geçiş
                      ▼
                 ┌──────────┐
                 │  Step 5  │  ← Step 4 atlandı!
                 └──────────┘
```

---

## 9. Hermes Plugin Entegrasyonu

Anchor, Hermes Agent'in **her LLM yanıtını otomatik denetler** — kullanıcıya ekstra aksiyon gerekmez.

### Entegrasyon Mimarisi

```
Hermes Agent
    │
    ├─▶ on_session_start kancası
    │       │
    │       ├─▶ Anchor Engine init (23 kural yüklenir)
    │       │
    │       └─▶ run_conversation() hook
    │               │
    │               ├─▶ LLM yanıt üretir
    │               ├─▶ rectifiy() çağrılır
    │               │       ├─▶ Kural denetimi
    │               │       ├─▶ İhlal tespiti
    │               │       └─▶ Düzeltme/rapor
    │               │
    │               └─▶ Yanıt kullanıcıya iletilir
    │
    ▼
Log: ⚓ Detected: N corrections (rules=[...])
```

### Plugin Özellikleri

| Özellik | Açıklama |
|---------|----------|
| Otomatik aktivasyon | `on_session_start` ile her oturumda başlar |
| Log entegrasyonu | `agent.log`'a detaylı rapor yazar |
| Diagnostic araçları | Çalışıyor mu kontrolü, kural listeleme |
| Aktif/pasif kontrol | Gerektiğinde devre dışı bırakılabilir |

---

## 10. False Positive Önleme

Anchor, **yanlış pozitif** tespitlerini minimize etmek için çok katmanlı bir strateji kullanır.

### Stratejiler

| Strateji | Açıklama |
|----------|----------|
| **Type-Aware Filtering** | Eğitim içeriğinde workflow kurallarını atla |
| **Fuzzy Matching Guard** | Kısa kelimelerde (≤2 chars) fuzzy eşleşmeyi engelle |
| **Educational Content Detection** | İçerik sınıflandırması (educational=True/False) |
| **Cross-Rule FP Filter** | Aynı anda birden fazla kural tetiklenince TF-IDF analizi |
| **Negative Check** | Olumsuz ifadeleri doğru yorumla |
| **Token Overlap Check** | Doğru ifade tespiti ile yanlış alarmı önle |

### Performans Verileri

| Metrik | Değer |
|--------|-------|
| Toplam kural | 23 |
| Doğru tespit | 82+ (son 2 saatte) |
| Yanlış pozitif | ~0 (type-aware filtering ile) |

---

## 11. Metrikler ve Gözlemlenebilirlik

Anchor, her çalıştırmada detaylı metrikler üretir.

### engine.stats

```python
{
    "engine": {
        "total_processed": 1423,      # Toplam işlenmiş LLM çıktısı
        "total_modified": 247,         # Düzeltilen çıktı sayısı
        "modification_rate": 0.174     # Düzeltme oranı
    },
    "store": {
        "rules_count": 23,
        "build_time_ms": 123,
        "cache_hit_rate": 0.89
    },
    "detector_avg_latency_us": 450,
    "patcher_avg_latency_us": 120
}
```

### Log Çıktıları

```
# Anchor başladı
⚓ Anchor Engine initialized: rules=~/.hermes/anchor-rules, rules_count=23

# İhlal tespiti
⚓ Detected: 17 corrections in LLM output
  (rules=['tdd-cycle', 'red-green-refactor'], educational=False)

# İhlal yok
(Sessiz — "Anchor active" mesajı dışında log yok)
```

---

## 12. Negation-Aware Tespit

Anchor, olumsuz ifadeleri (`"X yapma"`, `"Y kullanma"`) doğru yorumlamak için **3 farklı strateji** kullanır.

### Stratejiler

| Strateji | Açıklama |
|----------|----------|
| **Direct negation** | `"yapma"`, `"kullanma"`, `"etme"` gibi direkt olumsuzluklar |
| **Negative prefix** | `"de-"`, `"un-"`, `"-sız"`, `"-mez"` gibi eklerle olumsuzluk |
| **Contextual negation** | Bağlamsal olumsuzluk analizi |

### Örnek

```python
# Kural: "TDD'de önce test yazılır"
# LLM çıktısı: "Önce kodu yaz, sonra test et"

# Negation-Aware olmadan:
#   → "yaz" ve "test" eşleşir, ihlal tespit edilmez

# Negation-Aware ile:
#   → "önce kodu yaz" ≠ "önce test yaz"
#   → İhlal tespit edilir ✅
```

---

## 13. Cross-Rule FP Filtresi

Birden fazla kural aynı anda tetiklendiğinde, Anchor **TF-IDF tabanlı distinctive keyword analizi** ile hangi kuralın gerçekten ihlal edildiğini belirler.

```
3 kural aynı anda tetiklendi
    │
    ├─▶ kural-A: "test yaz" (distinctive: "pytest", "unittest")
    ├─▶ kural-B: "commit mesajı" (distinctive: "git", "commit")
    └─▶ kural-C: "dökümantasyon" (distinctive: "docstring", "README")
    │
    ▼
Çıktıda "pytest" ve "unittest" geçiyor → kural-A doğru
"git" ve "commit" geçmiyor → kural-B FP
"README" geçmiyor → kural-C FP
```

---

## 14. Loopback Limiti ve Guards

Anchor'ın sonsuz döngüye girmesini önlemek için **loopback limiti** ve **guard mekanizmaları** vardır.

| Guard | Limit | Açıklama |
|-------|-------|----------|
| Loopback limit | 5 | Aynı çıktı üzerinde maksimum düzeltme döngüsü |
| Cross-rule guard | 3 | Aynı kuralın tekrar tekrar tetiklenmesini engeller |
| Per-rule dedup | auto | Daha önce görülen claim'leri tekrar işleme |

---

## 15. Correct-Statement Detection

Anchor, LLM'in **doğru ifadelerini** de yanlışlıkla ihlal olarak işaretlemesini önlemek için token overlap analizi yapar.

```python
# Kural: "SOLID prensipleri: Single Responsibility"
# LLM çıktısı: "Single Responsibility Principle'a göre her sınıfın tek bir sorumluluğu olmalıdır"

# Token overlap: "Single", "Responsibility" → yüksek overlap
# → Bu doğru bir ifade, ihlal DEĞİL
```

---

## 16. Geliştirici Araçları

Anchor ile birlikte gelen yardımcı araçlar.

### Script'ler

| Script | Açıklama |
|--------|----------|
| `verify-frontmatter-parser.py` | Tüm kural dosyalarının frontmatter metadata'sını doğrular |

### Diagnostic Komutları

```bash
# Anchor çalışıyor mu kontrol et
grep "Anchor active" ~/.hermes/logs/agent.log | tail -1

# Son ihlalleri gör
grep "Detected:" ~/.hermes/logs/agent.log | tail -10

# Kural tiplerini listele
grep -r "^type:" ~/.hermes/anchor-rules/ --include="*.md"

# Hangi kurallar hangi tip?
grep -r "^topic:" ~/.hermes/anchor-rules/ --include="*.md"

# Type-aware filtering log'u
grep "educational=" ~/.hermes/logs/agent.log | tail -5
```

### Debug API

```python
from plugins.anchor.anchor_rectifier import rectify, init_engine, get_rules_path

# Engine'i başlat
init_engine(rules_path=get_rules_path())

# Çıktıyı dene
corrected, report = rectify(user_query=query, llm_output=response)

if report:
    from collections import Counter
    rule_counts = Counter(d['rule'] for d in report['details'])
    print("Kural bazında ihlal sayısı:", rule_counts.most_common())
    for d in report['details']:
        print(f"[{d['rule']}] {d['severity']}: "
              f"{d['original'][:60]} → {d['corrected'][:60]}")
```

---

## Özet: Ne Zaman Ne İşe Yarar?

| Senaryo | Anchor'un Katkısı |
|---------|-------------------|
| **TDD/Red-Green-Refactor** uygulamak | ✅ TDD döngüsünü denetler, her adımı doğrular |
| **Clean Architecture/SOLID** korumak | ✅ Domain rules her zaman aktif |
| **Git branching/commit** standartları | ✅ İhlal durumunda uyarır |
| **Eğitim içeriği** üretirken FP önlemek | ✅ Type-aware filtering ile workflow kuralları atlanır |
| **Türkçe/İngilizce** karışık ortam | ✅ Normalizasyon + confusion table |
| **Code review** süreci | ✅ Review adımlarını ve standartları denetler |
| **Dökümantasyon/ADR** yazarken | ✅ ADR formatını ve içerik kurallarını doğrular |
| **Mevcut sisteme entegre** etmek | ✅ Hermes plugin + standalone engine |

---

*Son güncelleme: 26 Mayıs 2026*
*Anchor v4.4.3 | Plugin v1.5.0 | 23 kural*
