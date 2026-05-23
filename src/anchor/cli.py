"""
Anchor CLI — Komut satırından kullanım için arayüz.
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="ANCHOR — LLM Çıktıları için Deterministik Rectification"
    )
    parser.add_argument(
        "action", 
        choices=["build", "process", "benchmark", "stats"],
        help="Yapılacak işlem"
    )
    parser.add_argument(
        "--rules", "-r",
        default="rules/",
        help="Rules dosyalarının bulunduğu klasör"
    )
    parser.add_argument(
        "--query", "-q",
        help="Kullanıcı sorusu"
    )
    parser.add_argument(
        "--llm-output", "-o",
        help="LLM çıktısı (veya dosya yolu)"
    )
    parser.add_argument(
        "--from-file", "-f",
        help="LLM çıktısını dosyadan oku"
    )
    
    args = parser.parse_args()
    
    if args.action == "build":
        from anchor.engine import AnchorEngine
        engine = AnchorEngine(args.rules)
        engine.build()
        print(f"✅  Index inşa edildi: {args.rules}")
        print(f"   {engine.stats}")
    
    elif args.action == "process":
        from anchor.engine import AnchorEngine
        
        if not args.query:
            print("❌  --query gerekli")
            sys.exit(1)
        
        if args.from_file:
            llm_output = Path(args.from_file).read_text(encoding='utf-8')
        elif args.llm_output:
            llm_output = args.llm_output
        else:
            print("❌  --llm-output veya --from-file gerekli")
            sys.exit(1)
        
        engine = AnchorEngine(args.rules)
        engine.build()
        
        result = engine.process(args.query, llm_output)
        
        print("\n" + "="*60)
        print("ANCHOR ÇIKTISI")
        print("="*60)
        
        if result.modified:
            print(result.corrected)
            print("\n---")
            print(result.summary)
        else:
            print("✅  Düzeltme gerekmedi")
            print(result.corrected)
        
        print(f"\n⏱️  Toplam latency: {result.latency_us.get('total', 0):.1f}μs")
    
    elif args.action == "benchmark":
        from anchor.engine import AnchorEngine
        
        engine = AnchorEngine(args.rules)
        engine.build()
        
        # Test senaryoları
        scenarios = [
            {
                "query": "Neural Processor X1 hakkında bilgi ver",
                "llm": "NPX1, TSMC'nin 7nm düğümünde üretilen genel amaçlı bir AI hızlandırıcısıdır.",
            },
            {
                "query": "StateGuard nedir?",
                "llm": "StateGuard bir güvenlik duvarı aracıdır.",
            },
            {
                "query": "SKY130 hakkında bilgi",
                "llm": "SKY130, Global Foundries'in 130nm düğümüdür.",
            },
            {
                "query": "RISC-V işlemci mimarisi",
                "llm": "RISC-V genel amaçlı bir işlemci mimarisidir.",
            },
        ]
        
        total_latency = 0
        modified_count = 0
        
        print(f"{'Test':<40} {'Durum':<15} {'Latency':<10}")
        print("-"*65)
        
        for i, scenario in enumerate(scenarios):
            result = engine.process(scenario["query"], scenario["llm"])
            latency = result.latency_us.get('total', 0)
            total_latency += latency
            
            status = "🔧 DÜZELTİLDİ" if result.modified else "✅ OLD" if i < 2 else "⚠️  "
            if result.modified:
                modified_count += 1
            
            print(f"{scenario['query'][:38]:<40} {status:<15} {latency:<8.1f}μs")
            
            if result.modified:
                for corr in result.corrections:
                    print(f"  → {corr.conflict.severity.name}: {corr.conflict.kb_fact[:60]}")
        
        print("-"*65)
        print(f"{'Toplam':<40} {'':<15} {total_latency:<8.1f}μs")
        print(f"Ortalama latency: {total_latency / len(scenarios):.1f}μs")
        print(f"Düzeltme oranı: {modified_count}/{len(scenarios)}")
    
    elif args.action == "stats":
        from anchor.engine import AnchorEngine
        
        engine = AnchorEngine(args.rules)
        engine.build()
        
        stats = engine.stats
        print("="*50)
        print("ANCHOR İSTATİSTİKLERİ")
        print("="*50)
        print(f"Yüklü rule sayısı:   {stats['store']['total_rules']}")
        print(f"Cache hit ratio:     {stats['store']['hit_ratio']:.1%}")
        print(f"İşlenen çağrı:       {stats['engine']['total_processed']}")
        print(f"Düzeltme oranı:      {stats['engine']['modification_rate']:.1%}")
        print(f"Topic extraction:    {stats['extractor']['avg_latency_us']:.1f}μs")
        print(f"Conflict detection:  {stats['detector']['avg_latency_us']:.1f}μs")
        print(f"Rectification:       {stats['rectifier']['avg_latency_us']:.1f}μs")


if __name__ == "__main__":
    main()
