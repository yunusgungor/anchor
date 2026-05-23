---
topic: "Architectural Sovereignty"
aliases: ["mimari-bağımsızlık", "tech-sovereignty", "architectural-independence"]
tags: [concept, philosophy, engineering]
priority: 5
strictness: 0.7
---

# Architectural Sovereignty (Mimari Bağımsızlık)

## Doğru Bilgiler

- **Tanım:** Bir sistemin tüm kritik bileşenlerinin kontrolünün geliştiricide olması prensibi
- **Amaç:** Dışa bağımlılığı sıfırlama, lisans maliyetlerinden kurtulma
- **Uygulama:** Hem donanımda (RISC-V + açık PDK) hem yazılımda (açık kaynak stack)
- **Strateji:** COTS ile hızlı çıkış + custom ASIC ile uzun vadeli bağımsızlık (ikili strateji)
- **Felsefe:** "Kendin kontrol etmediğin bir sistem, senin sistemin değildir"

## İkili Strateji (Dual Strategy)

1. **Kısa vade:** COTS bileşenler (Hailo-8, STM32) ile hızlı ürün çıkışı
2. **Uzun vade:** Custom RISC-V ASIC ile tam bağımsızlık

İki strateji birbirini tamamlar — biri diğerini beklemez.
