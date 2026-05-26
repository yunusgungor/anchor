# Corrective Mode — Anchor v1.4.0 (IMPLEMENTED)

> **Session:** 2026-05-26 — Kullanıcının isteği üzerine uygulandı.
> **Durum:** ✅ Tamamlandı (hermes-agent plugin, `next` branch)

## Mimari

Corrective mode, `anchor_rectifier.py`'daki `apply_corrections()` fonksiyonu ile
LLM çıktısını **append değil, doğrudan metin içinde değiştirerek** düzeltir.

### Nasıl Çalışır?

```
LLM:  "git commit -m 'yaptıklarım' yeterlidir"
Anchor (corrective):
  ├── apply_corrections() çağrılır
  │   ├── "yaptıklarım" → "feat: yaptıklarım" (domain, conf=0.92)
  │   └── str.replace(..., 1) ile metin değiştirilir
  └── Log: "⚓ Corrective: 1 replacement(s) applied"
Kullanıcı:  "git commit -m 'feat: yaptıklarım' yeterlidir"  ✓
```

### Dosyalar

| Dosya | Değişiklik |
|-------|-----------|
| `hermes-agent/plugins/anchor/anchor_rectifier.py` | `apply_corrections()` eklendi |
| `hermes-agent/plugins/anchor/__init__.py` | Corrective mode handler eklendi |
| `hermes-agent/plugins/anchor/plugin.yaml` | v1.4.0 |

## Confidence Thresholds

| Rule Type | Threshold | Amaç |
|-----------|-----------|------|
| `domain` | >= 0.5 | Factual bilgi — düşük eşik |
| `hybrid` | >= 0.7 | Orta güven — eğitim içeriğinde FP önleme |
| `workflow` | >= 0.8 | En yüksek — sadece çok emin olunan düzeltmeler |

## Fallback

Tüm düzeltmeler eşiğin altındaysa → `annotated` mode'a fallback yapar
(annotation eklenir, metin değişmez).
