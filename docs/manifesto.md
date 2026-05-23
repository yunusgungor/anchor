# ANCHOR: LLM Çıktıları için Deterministik Rectification Çerçevesi

## Bilimsel Araştırma Manifestosu

### 1. Araştırma Problemi

Large Language Modeller (LLM'ler) olasılıksal sistemlerdir:

$$y \sim p_\theta(y | x)$$

Aynı $x$ girdisiyle her çağrıda farklı $y$ üretebilirler. Bu, aşağıdaki ontolojik boşluğu yaratır:

| Alan | Doğa | Deterministik mi? |
|---|---|---|
| LLM $p_\theta$ | Olasılıksal | ❌ |
| Kullanıcının bilgi tabanı $\mathcal{K}$ | Kesin | ✅ |
| **Aradaki boşluk** | **?** | **?** |

**Araştırma Sorusu:** Bir LLM'in olasılıksal çıktı uzayı $\mathcal{Y}_{LLM}$ ile kullanıcının deterministik bilgi uzayı $\mathcal{K}$ arasında, her iki tarafa da dokunmadan çalışan bir **Rectification Fonksiyonu** $\Phi$ tasarlanabilir mi?

$$\Phi: \mathcal{Y}_{LLM} \times \mathcal{K} \to \mathcal{Y}'$$

Bu fonksiyon:
- **Deterministik** olmalı ($\forall i,j: \Phi(y_i, \mathcal{K}) = \Phi(y_j, \mathcal{K})$ eğer $y_i \equiv y_j$)
- **LLM-agnostik** olmalı (ChatGPT, Claude, Llama, her modelle çalışmalı)
- **Gerçek zamanlı** çalışmalı ($< 10ms$ latency hedefi)

### 2. Matematiksel Çerçeve

#### 2.1 Temel Tanımlar

| Sembol | Tanım | Açıklama |
|---|---|---|
| $\mathcal{K} = \{k_1, ..., k_n\}$ | Knowledge Base | Kullanıcının rules dosyaları |
| $\mathcal{T}$ | Topic Space | Konu uzayı |
| $\tau: \Sigma^* \to \mathcal{P}(\mathcal{T})$ | Topic Extraction | LLM çıktısından konu çıkarma |
| $\kappa: \mathcal{T} \to \mathcal{P}(\mathcal{K})$ | Knowledge Retrieval | Konuyla ilgili rule'ları bulma |
| $\delta: \Sigma^* \times \mathcal{K} \to [0,1]$ | Conflict Detection | Çelişki skoru |
| $\rho: \Sigma^* \times \mathcal{K} \to \Sigma^*$ | Rectification | Düzeltme fonksiyonu |

#### 2.2 Rectification Pipeline

$$\Phi(y_{raw}, \mathcal{K}) = \rho \circ \delta \circ \kappa \circ \tau \quad (y_{raw}, \mathcal{K})$$

Adım adım:

1. **Topic Extraction:** $\hat{\mathcal{T}} = \tau(y_{raw})$
2. **Knowledge Retrieval:** $\hat{\mathcal{K}} = \kappa(\hat{\mathcal{T}})$
3. **Conflict Detection:** $c_i = \delta(y_{raw}, k_i) \quad \forall k_i \in \hat{\mathcal{K}}$
4. **Rectification:** $y' = \rho(y_{raw}, \{k_i : c_i > \theta\})$

#### 2.3 Performans Hedefleri

| Adım | İşlem | Hedef Latency | Yöntem |
|---|---|---|---|
| Topic Extraction | $y_{raw} \to \mathcal{T}$ | $< 250\mu s$ | Regex + Trie + Hash |
| Knowledge Retrieval | $\mathcal{T} \to \mathcal{K}$ | $< 200\mu s$ | Hash Lookup (O(1)) |
| Conflict Detection | $\mathcal{K} \to [0,1]^m$ | $< 1ms$ | String + Embedding |
| Rectification | $\to y'$ | $< 300\mu s$ | String Manipulation |
| **Total** | | **$< 2ms$** | |

### 3. Araştırma Hipotezleri

**H1:** LLM çıktılarındaki hataların $\geq 80\%$'i ikinci bir LLM çağırmadan, tamamen deterministik yöntemlerle (regex + string edit + hash lookup) düzeltilebilir.

**H2:** Topic extraction için küçük bir embedding modeli ($< 100MB$) kullanıldığında, coverage $\geq 95\%$'e çıkar.

**H3:** Ölçeklenebilirlik: $n$ rules dosyası için lookup latency, $O(1)$'e yakınsar (hash tabanlı index sayesinde).

### 4. Değerlendirme Metrikleri

**Doğruluk:**
$$\text{Accuracy} = \frac{\text{doğru düzeltme sayısı}}{\text{toplam düzeltme sayısı}}$$

**Kapsama:**
$$\text{Coverage} = \frac{|\{t \in \mathcal{T} : \tau(y_{raw}) \ni t\}|}{|\mathcal{T}|}$$

**Gecikme:**
$$\text{Latency}_{p50}, \text{Latency}_{p99}, \text{Latency}_{max}$$

**Minimal Müdahale:**
$$\text{Edit Distance} = \frac{1}{N}\sum_{i=1}^N \text{ED}(y_{raw}^{(i)}, y'^{(i)})$$

### 5. Araştırma Kapsamı

| Dahil | Hariç |
|---|---|
| Deterministic output rectification | Model fine-tuning |
| Rule-based conflict detection | RAG (Retrieval Augmented Generation) |
| LLM-agnostik yaklaşım | Model-specific optimization |
| Topic extraction (deterministic) | LLM-as-judge |
| Knowledge indexing | Knowledge graph construction |
| Conflict severity scoring | Full NLP pipeline |

### 6. Deneysel Tasarım

#### 6.1 LLM'ler
- ChatGPT (GPT-4o)
- Claude 4 Sonnet
- Llama 3 (70B/405B)
- DeepSeek-V3

#### 6.2 Domain'ler
- Teknik yazı (RISC-V, chip design)
- Yazılım dokümantasyonu
- Haber/medya

#### 6.3 Test Seti
- Her domain'den 100+ test senaryosu
- 50:50 oranında "LLM doğru söylüyor" / "LLM hatalı"
- Kör test (araştırmacı hangisi olduğunu bilmiyor)

### 7. Araştırma Takvimi

| Faz | Süre | Çıktı |
|---|---|---|
| Faz I: Formal Model | Hafta 1-2 | Matematiksel çerçeve + mimari |
| Faz II: Prototip | Hafta 3-6 | Core engine implementasyonu |
| Faz III: Deneysel | Hafta 7-12 | 3 LLM × 3 domain testleri |
| Faz IV: Yayın | Hafta 13-16 | White paper + analiz |

### 8. Etik Not

Bu araştırma, LLM çıktılarının güvenilirliğini artırmayı hedefler. Hiçbir LLM'in çıktısını sansürlemez veya değiştirmez — sadece kullanıcının kendi bilgi tabanıyla çelişen noktaları işaretler/düzeltir. Kullanıcı her zaman hangi düzeltmenin yapıldığını görür.
