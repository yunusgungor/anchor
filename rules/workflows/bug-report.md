---
topic: "Bug Report Workflow"
aliases: ["bug-report", "hata-raporu", "bug report", "hata raporu", "bug"]
tags: [workflow, process, quality]
priority: 10
strictness: 0.9
steps:
  - id: step-1
    title: "Ortamı belirle"
    mandatory: true
    checks: ["Windows", "Linux", "macOS", "Chrome", "Firefox", "tarayıcı"]
  - id: step-2
    title: "Hatayı tanımla"
    mandatory: true
    depends_on: [step-1]
    checks: ["hata", "reproduce", "adım", "aşama"]
  - id: step-3
    title: "Logları ekle"
    mandatory: true
    depends_on: [step-2]
    checks: ["log", "hata kodu", "kayıt"]
  - id: step-4
    title: "Beklenen davranışı açıkla"
    mandatory: true
    checks: ["beklenen", "olması gereken", "normalde"]
  - id: step-5
    title: "Öncelik belirle"
    mandatory: false
    options: ["P0", "P1", "P2"]
---

## Sık Karıştırılan Noktalar

| Konu | LLM'in Genelde Dediği | Doğrusu |
|------|-----------------------|---------|
| Sıralama | Önce çözüm öner, sonra log sor | Önce log, sonra çözüm |
| Atlama | Log eklemeden direkt çözüm | Log zorunlu adım |
