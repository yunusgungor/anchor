# Anchor → Hermes Agent Entegrasyonu

> **Deterministik ikinci aşama** — her LLM yanıtı otomatik olarak Anchor'dan geçer.

---

## Nasıl Çalışır

```
User → LLM → Tool Calls → LLM → Response → ⚓ ANCHOR → Corrected → User
                                            (her zaman!)
```

Anchor, Hermes Agent'in `AIAgent.chat()` metoduna **monkey-patch** uygular.  
Her LLM yanıtı, kullanıcıya gitmeden önce Anchor Engine'den geçer.

**LLM'in Anchor'ı atlama şansı YOKTUR** — çünkü Anchor, LLM döngüsünün DIŞINDA, cevap kullanıcıya iletilmeden HEMEN ÖNCE çalışır.

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `/opt/hermes/plugins/anchor/__init__.py` | Plugin giriş noktası — `on_session_start` hook + `chat()` patch |
| `/opt/hermes/plugins/anchor/anchor_rectifier.py` | AnchorEngine wrapper — init, rectify, rules path |
| `/opt/hermes/plugins/anchor/plugin.yaml` | Plugin manifest |
| `~/.hermes/config.yaml` → `anchor:` | Konfigürasyon |
| `~/.hermes/anchor-rules/` | 23 built-in kural |

## Konfigürasyon

```yaml
# ~/.hermes/config.yaml
anchor:
  enabled: true                      # Aktif/pasif
  rules_path: "~/.hermes/anchor-rules/"  # Rules dizini
  mode: "silent"                     # silent | annotated | report
  use_embedding: false               # Embedding (opsiyonel)

# toolsets ve plugins'e anchor eklenmeli:
toolsets:
- hermes-cli
- content
- anchor

plugins:
  enabled:
  - anchor
```

## Modlar

| Mod | Davranış |
|---|---|
| **silent** (default) | Düzeltilmiş metni göster, kullanıcı fark etmez |
| **annotated** | Düzeltilmiş metin + "N düzeltme uygulandı" notu |
| **report** | Düzeltilmiş metin + altında detaylı rapor (kurallar, konular) |

## Güvenceler

| Durum | Davranış |
|---|---|
| **Anchor aktif, düzeltme var** | Düzeltilmiş metin döner |
| **Anchor aktif, düzeltme yok** | Orijinal metin döner (düzeltme raporu yok) |
| **Anchor hata verdi** | Orijinal metin döner (non-fatal) |
| **anchor-engine pip paketi yok** | Anchor pasif, her yanıt aynen geçer |
| **Rules dizini boş/yok** | Anchor pasif, log uyarısı |

## Test

```bash
# Plugin yüklemesi
cd /opt/hermes && python3 -c "
from plugins.anchor.anchor_rectifier import init_engine, rectify
init_engine('/root/.hermes/anchor-rules')
corrected, report = rectify('test', 'LLM output here')
print(f'Corrected: {corrected[:60]}...' if len(corrected) > 60 else f'Corrected: {corrected}')
"

# Anchor rules'ların varlığı
ls ~/.hermes/anchor-rules/
```
