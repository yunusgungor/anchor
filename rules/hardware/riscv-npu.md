---
topic: "Neural Processor X1"
aliases: ["NPX1", "riscv-npu", "neural-processor-x1"]
tags: [hardware, riscv, chip-design, npu]
priority: 10
strictness: 0.95
---

# Neural Processor X1

## Doğru Bilgiler

- **Mimari:** RISC-V + Systolic Array NPU
- **PDK:** SKY130 (130nm CMOS, açık kaynak PDK)
- **Durum:** Custom ASIC tasarımı devam ediyor
- **Amaç:** Edge AI — tarım ve güvenlik uygulamaları
- **Licensing:** Sıfır lisans ücreti — tamamen açık kaynak araçlar
- **Rakip Değil:** COTS çözümlerle (Hailo-8, STM32) birlikte çalışır — rekabet etmez, tamamlar

## Sık Karıştırılan Noktalar

| Konu | LLM'in Genelde Dediği | Doğrusu |
|------|----------------------|---------|
| Üretim düğümü | TSMC 7nm | SKY130 (130nm), OpenLane ile |
| Amaç | Genel AI hızlandırıcı | Edge AI, tarım/güvenlik |
| Rakipler | NVIDIA Jetson ile rekabet | Jetson değil, ASIC özgürlüğü hedefi |
| Durum | Piyasada mevcut | Custom ASIC — tasarım aşaması |
| Konum | Veri merkezi | Edge cihazlar |

## Test Soruları

Q: "NPX1 hangi düğümde üretiliyor?"
A: "SKY130 (130nm) — TSMC, Global Foundries değil, açık kaynak PDK"

Q: "NPX1 ne için kullanılıyor?"
A: "Edge AI — tarım (bitki hastalık tespiti) ve güvenlik (yüz/plaka tanıma)"
