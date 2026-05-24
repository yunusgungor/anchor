---
topic: "Bug Report Workflow"
aliases: ["bug-report", "hata-raporu"]
tags: [workflow, process, quality]
priority: 10
strictness: 0.9
steps:
  - id: step-1
    title: "Ortamı belirle"
    mandatory: true
    checks: ["OS", "browser"]
  - id: step-2
    title: "Hatayı tanımla"
    mandatory: true
    depends_on: [step-1]
    checks: ["adım", "reproduce"]
  - id: step-3
    title: "Logları ekle"
    mandatory: true
    depends_on: [step-2]
  - id: step-4
    title: "Beklenen davranışı açıkla"
    mandatory: true
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
