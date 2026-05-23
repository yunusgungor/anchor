"""
Benchmark Rule Generator — Gerçekçi fake rule'lar üret.

Strateji:
  - 1000 rule, 10 domain shard
  - Her rule: topic, aliases, tags, facts, confusion table
  - Konular: teknik terimler, ürün isimleri, kavramlar
"""

import os
import random
import string
from pathlib import Path


# Domain'ler ve içindeki konular
DOMAINS = {
    "hardware": [
        ("processor", ["cpu", "chip", "işlemci"]),
        ("memory", ["ram", "dram", "ssd"]),
        ("sensor", ["imu", "gyro", "accelerometer"]),
        ("fpga", ["programmable", "logic"]),
        ("gpu", ["graphics", "accelerator"]),
    ],
    "software": [
        ("compiler", ["gcc", "clang", "build"]),
        ("database", ["sql", "nosql", "cache"]),
        ("framework", ["library", "sdk", "toolkit"]),
        ("os", ["kernel", "scheduler", "driver"]),
        ("protocol", ["tcp", "udp", "http"]),
    ],
    "ai_ml": [
        ("transformer", ["attention", "bert", "gpt"]),
        ("cnn", ["convolution", "filter", "layer"]),
        ("training", ["epoch", "batch", "gradient"]),
        ("inference", ["deployment", "serving", "optimization"]),
        ("dataset", ["corpus", "annotation", "label"]),
    ],
    "cloud": [
        ("container", ["docker", "pod", "image"]),
        ("orchestration", ["kubernetes", "scheduler", "service"]),
        ("serverless", ["lambda", "function", "trigger"]),
        ("storage", ["s3", "blob", "object"]),
        ("network", ["vpc", "subnet", "firewall"]),
    ],
    "security": [
        ("encryption", ["aes", "rsa", "cipher"]),
        ("authentication", ["oauth", "jwt", "token"]),
        ("firewall", ["ids", "ips", "rule"]),
        ("vulnerability", ["exploit", "cve", "patch"]),
        ("blockchain", ["ledger", "hash", "consensus"]),
    ],
    "bio": [
        ("sequencing", ["dna", "rna", "genome"]),
        ("protein", ["enzyme", "folding", "structure"]),
        ("cell", ["membrane", "organelle", "nucleus"]),
        ("drug", ["compound", "molecule", "target"]),
        ("pathway", ["metabolism", "signal", "cascade"]),
    ],
    "energy": [
        ("solar", ["photovoltaic", "panel", "cell"]),
        ("battery", ["lithium", "ion", "charge"]),
        ("grid", ["transmission", "distribution", "smart"]),
        ("nuclear", ["reactor", "fission", "fusion"]),
        ("wind", ["turbine", "blade", "generator"]),
    ],
    "finance": [
        ("trading", ["stock", "option", "future"]),
        ("risk", ["var", "exposure", "hedge"]),
        ("payment", ["transaction", "settlement", "clearing"]),
        ("regulation", ["compliance", "aml", "kyc"]),
        ("crypto", ["bitcoin", "ethereum", "defi"]),
    ],
    "robotics": [
        ("actuator", ["motor", "servo", "piston"]),
        ("sensor_fusion", ["lidar", "camera", "radar"]),
        ("planning", ["path", "trajectory", "obstacle"]),
        ("manipulation", ["gripper", "arm", "grasp"]),
        ("locomotion", ["leg", "wheel", "balance"]),
    ],
    "space": [
        ("propulsion", ["rocket", "engine", "thrust"]),
        ("orbit", ["trajectory", "apsis", "period"]),
        ("satellite", ["payload", "transponder", "bus"]),
        ("life_support", ["oxygen", "co2", "habitat"]),
        ("communication", ["antenna", "band", "relay"]),
    ],
}

# Fact template'leri
FACT_TEMPLATES = [
    ("Mimari", "{topic} mimarisi, {detail1} ve {detail2} birleşimidir"),
    ("Üretim", "{topic}, {detail1} süreciyle üretilmektedir"),
    ("Lisans", "{topic}, {detail1} lisans modeliyle dağıtılmaktadır"),
    ("Performans", "{topic}, {detail1} hıza ve {detail2} verimliliğe sahiptir"),
    ("Uyumluluk", "{topic}, {detail1} ile uyumludur"),
]

# Yanlış bilgi template'leri
MISTAKE_TEMPLATES = [
    "{topic}, {detail1} mimarili değildir",
    "{topic}, {detail1} süreciyle üretilir",
    "{topic}, {detail1} lisansı altındadır",
    "{topic}, {detail1} hızında çalışır",
    "{topic}, {detail1} ile uyumlu değildir",
]

# Detay kelimeleri
DETAILS = [
    "RISC-V", "ARM", "x86", "MIPS", "SPARC",
    "CMOS", "FinFET", "SOI", "GaN", "SiC",
    "açık kaynak", "tescilli", "hibrid", "özel",
    "5nm", "7nm", "14nm", "28nm", "130nm",
    "1GHz", "2GHz", "3GHz", "5GHz", "10GHz",
    "DDR4", "DDR5", "LPDDR", "HBM", "GDDR",
    "PCIe", "USB", "SATA", "NVMe", "Ethernet",
]


def random_id(topic: str, idx: int) -> str:
    """Rule ID oluştur."""
    return f"{topic}-{idx:04d}"


def generate_rule_content(topic: str, aliases: list[str], idx: int) -> str:
    """Gerçekçi rule içeriği üret."""
    details = random.sample(DETAILS, 4)
    
    # Doğru bilgiler
    facts = []
    for i, (label, template) in enumerate(random.sample(FACT_TEMPLATES, 3)):
        d1 = details[i]
        d2 = details[(i + 1) % len(details)]
        fact = template.format(
            topic=topic,
            detail1=d1,
            detail2=d2
        )
        facts.append((label, fact))
    
    # Yanlış bilgiler (confusion table)
    mistakes = []
    wrong_details = random.sample(DETAILS, 3)
    for i, template in enumerate(random.sample(MISTAKE_TEMPLATES, 3)):
        wrong = template.format(topic=topic, detail1=wrong_details[i])
        correct = facts[i][1] if i < len(facts) else f"{topic} doğru bilgi"
        mistakes.append((facts[i][0], wrong, correct))
    
    content = f"""# {topic.replace('_', ' ').title()}

## Doğru Bilgiler

"""
    for label, fact in facts:
        content += f"- **{label}:** {fact}\n"
    
    content += """
## Sık Karıştırılan Noktalar

| Konu | LLM'in Genelde Dediği | Doğrusu |
|------|----------------------|---------|
"""
    for label, wrong, correct in mistakes:
        content += f"| {label} | {wrong} | {correct} |\n"
    
    return content


def generate_rules(count: int = 1000, output_dir: str = "/tmp/anchor_benchmark_rules") -> str:
    """
    `count` adet fake rule üret.
    
    Returns:
        Oluşturulan rules dizini yolu
    """
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    
    # Her domain'e eşit dağıt
    domains = list(DOMAINS.keys())
    rules_per_domain = count // len(domains)
    
    total = 0
    for domain_idx, (domain, topics) in enumerate(DOMAINS.items()):
        domain_path = base / domain
        domain_path.mkdir(exist_ok=True)
        
        for topic_idx, (topic, aliases) in enumerate(topics):
            # Her topic için alt kategori
            topic_path = domain_path / topic
            topic_path.mkdir(exist_ok=True)
            
            for i in range(rules_per_domain // len(topics)):
                rule_id = random_id(topic, i)
                rule_topic = f"{topic.replace('_', ' ').title()} {string.ascii_uppercase[i % 26]}{i}"
                rule_aliases = aliases + [f"{a}{i}" for a in aliases[:2]]
                
                # Frontmatter
                fm = f"""---
topic: "{rule_topic}"
aliases: {rule_aliases}
tags: [{domain}, {topic}, benchmark]
priority: {random.randint(1, 10)}
strictness: {random.uniform(0.3, 1.0):.1f}
---

"""
                content = generate_rule_content(rule_topic, rule_aliases, i)
                
                fpath = topic_path / f"{rule_id}.md"
                fpath.write_text(fm + content, encoding="utf-8")
                total += 1
    
    print(f"✅ {total} fake rule üretildi: {output_dir}")
    return str(base)


if __name__ == "__main__":
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    generate_rules(count)
