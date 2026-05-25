# Anchor → Hermes Agent Entegrasyonu

> **Deterministik ikinci aşama** — her LLM yanıtı otomatik Anchor'dan geçer.

---

## Nasıl Çalışır

```
User → Prompt → LLM → [Tool Calls] → LLM → Response
                                                │
                                          ⚓ ANCHOR
                                          (her zaman!)
                                                │
                                    ┌───────────┴──────────┐
                                    │                      │
                              Hata varsa            Temizse
                                    │                      │
                              Orijinal yanıt      Orijinal yanıt
                              + Anchor raporu     aynen geçer
                                    │                      │
                                    └──────────┬───────────┘
                                               │
                                          User
```

**Anahtar prensip:** Anchor, LLM'in cevabını ASLA değiştirmez. Düzeltmeleri tespit eder ve rapor olarak sunar. Kullanıcı, moda bağlı olarak düzeltmeleri görür veya görmez.

## Akış Testi Sonuçları (5/5 ✅)

| # | LLM Söyledi | Anchor Tespit | Severity |
|---|---|---|---|
| 1 | "Singletons use them everywhere" | Tasarım deseni ihlali | 🔴 CRITICAL |
| 2 | "Factory Method NOT suitable" | Negation detection (A1) | 🔴 CRITICAL |
| 3 | "Repository creates tight coupling" | Yanlış neden-sonuç (A3) | 🔴 CRITICAL |
| 4 | "Wrote code, refactored, then tests" | TDD sıra ihlali | ❌ ERROR |
| 5 | "Write production code first" | 7 hata (missing + order) | 🔴 CRITICAL |

**LLM yanıtı korundu:** 5/5 ✅

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `/opt/hermes/plugins/anchor/__init__.py` | Plugin giriş + `chat()` monkey-patch |
| `/opt/hermes/plugins/anchor/anchor_rectifier.py` | Anchor wrapper (init, rectify) |
| `/opt/hermes/plugins/anchor/plugin.yaml` | Manifest |
| `~/.hermes/config.yaml` → `anchor:` | Konfigürasyon |
| `~/.hermes/anchor-rules/` | 23 kural |

## Test

```bash
cd /opt/hermes && python3 -c "
from plugins.anchor.anchor_rectifier import init_engine, rectify
init_engine('/root/.hermes/anchor-rules')
corrected, report = rectify('test query', 'LLM output here')
if report: print(f'Anchor: {report[\"corrections\"]} corrections')
"
```
