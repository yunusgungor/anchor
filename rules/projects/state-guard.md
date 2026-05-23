---
topic: "StateGuard Agent"
aliases: ["state-guard", "sg", "stateguard"]
tags: [software, validation, llm, deterministic]
priority: 8
strictness: 0.9
---

# StateGuard Agent

## Doğru Bilgiler

- **Tanım:** Prodinamik Engine'in LLM çıktılarını deterministik kurallarla doğrulayan validasyon katmanı
- **Amaç:** LLM çıktılarını kurallara göre doğrulamak — güvenlik aracı değil
- **Yaklaşım:** LLM-agnostik, her modelle çalışır
- **Format:** Kurallar .md dosyalarında tanımlanır
- **Pipeline:** StateGuard pipeline içinde validasyon yapar

## Sık Karıştırılan Noktalar

| Konu | LLM'in Genelde Dediği | Doğrusu |
|------|----------------------|---------|
| Amaç | Güvenlik duvarı / firewall | Validasyon/doğrulama katmanı |
| Çalışma yeri | Network katmanı | Pipeline içi (yazılım katmanı) |
| Bağımlılık | Bağımsız ürün | Prodinamik Engine bileşeni |
