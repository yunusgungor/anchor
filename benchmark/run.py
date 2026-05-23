"""
Anchor Benchmark Suite — Performans ve doğruluk ölçümü.

Metrikler:
  - Cold start latency
  - Query latency (p50, p95, p99)
  - Memory usage
  - Conflict detection accuracy (precision/recall)
  - Patch latency
  - Throughput (queries/second)
"""

import gc
import os
import random
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

# Anchor'ı ekle
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from anchor.engine import AnchorEngine


class BenchmarkRunner:
    """Anchor engine benchmark'ları çalıştırır."""
    
    def __init__(self, rules_path: str, index_path: str):
        self.rules_path = rules_path
        self.index_path = index_path
        self.results: dict[str, Any] = {}
    
    def run_all(self) -> dict:
        """Tüm benchmark'ları çalıştır ve rapor üret."""
        print("=" * 60)
        print("ANCHOR BENCHMARK SUITE")
        print("=" * 60)
        
        self.benchmark_cold_start()
        self.benchmark_query_latency()
        self.benchmark_conflict_accuracy()
        self.benchmark_patch_latency()
        self.benchmark_memory()
        self.benchmark_throughput()
        
        return self.results
    
    def benchmark_cold_start(self):
        """Cold start latency ölç."""
        print("\n🚀 Cold Start Benchmark...")
        
        times = []
        for _ in range(5):
            gc.collect()
            t0 = time.perf_counter()
            engine = AnchorEngine(self.rules_path, self.index_path)
            engine.build()
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000)
            del engine
        
        self.results["cold_start_ms"] = {
            "p50": sorted(times)[len(times) // 2],
            "min": min(times),
            "max": max(times),
        }
        print(f"  Cold start: {self.results['cold_start_ms']['p50']:.1f}ms (min: {min(times):.1f}, max: {max(times):.1f})")
    
    def benchmark_query_latency(self):
        """Query latency ölç (p50, p95, p99)."""
        print("\n🔍 Query Latency Benchmark...")
        
        engine = AnchorEngine(self.rules_path, self.index_path)
        engine.build()
        
        # Test sorguları
        queries = [
            ("X1 processor hakkında bilgi", "X1, ARM mimarili bir işlemcidir."),
            ("Y2 sensor nedir", "Y2, optik sensördür."),
            ("Z3 database hakkında", "Z3, SQL tabanlı bir veritabanıdır."),
            ("A4 encryption ne işe yarar", "A4, AES ile şifreleme yapar."),
            ("B5 solar panel verimliliği", "B5, %20 verimlilikle çalışır."),
        ] * 20  # 100 query
        
        latencies = []
        for q, output in queries:
            t0 = time.perf_counter()
            result = engine.process(q, output)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1_000_000)  # μs
        
        latencies.sort()
        n = len(latencies)
        
        self.results["query_latency_us"] = {
            "p50": latencies[n // 2],
            "p95": latencies[int(n * 0.95)],
            "p99": latencies[int(n * 0.99)],
            "min": latencies[0],
            "max": latencies[-1],
        }
        
        print(f"  p50: {self.results['query_latency_us']['p50']:.0f}μs")
        print(f"  p95: {self.results['query_latency_us']['p95']:.0f}μs")
        print(f"  p99: {self.results['query_latency_us']['p99']:.0f}μs")
    
    def benchmark_conflict_accuracy(self):
        """Conflict detection doğruluğunu ölç."""
        print("\n🎯 Conflict Detection Accuracy...")
        
        engine = AnchorEngine(self.rules_path, self.index_path)
        engine.build()
        
        # Bilinen çelişkiler (ground truth)
        test_cases = [
            # (query, llm_output, expected_modified)
            (
                "X1 processor hakkında bilgi",
                "X1, ARM mimarili bir işlemcidir.",
                True,  # ARM → farklı mimari (confusion table'da olabilir)
            ),
            (
                "Y2 sensor nedir",
                "Y2, optik sensördür.",
                True,  # optik → farklı sensör tipi
            ),
            (
                "RISC-V NPU nedir",
                "RISC-V NPU, edge AI işlemcisidir.",
                False,  # Doğru bilgi
            ),
            (
                "Z3 database hakkında",
                "Z3, NoSQL tabanlı bir veritabanıdır.",
                True,  # SQL ↔ NoSQL çelişkisi
            ),
            (
                "A4 encryption",
                "A4, RSA ile şifreleme yapar.",
                True,  # AES ↔ RSA çelişkisi
            ),
        ]
        
        correct = 0
        total = len(test_cases)
        
        for query, output, expected_modified in test_cases:
            result = engine.process(query, output)
            if result.modified == expected_modified:
                correct += 1
        
        accuracy = correct / total
        self.results["conflict_accuracy"] = {
            "accuracy": accuracy,
            "correct": correct,
            "total": total,
        }
        
        print(f"  Accuracy: {accuracy:.1%} ({correct}/{total})")
    
    def benchmark_patch_latency(self):
        """Patch latency ölç."""
        print("\n🩹 Patch Latency Benchmark...")
        
        engine = AnchorEngine(self.rules_path, self.index_path)
        engine.build()
        
        # CRITICAL conflict üreten query
        latencies = []
        for _ in range(100):
            t0 = time.perf_counter()
            result = engine.process(
                "X1 processor hakkında",
                "X1, yanlış mimarili bir işlemcidir."
            )
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1_000_000)
        
        avg = sum(latencies) / len(latencies)
        self.results["patch_latency_us"] = {
            "avg": avg,
            "min": min(latencies),
            "max": max(latencies),
        }
        
        print(f"  Avg: {avg:.0f}μs")
    
    def benchmark_memory(self):
        """Memory kullanımını ölç."""
        print("\n🧠 Memory Benchmark...")
        
        tracemalloc.start()
        
        engine = AnchorEngine(self.rules_path, self.index_path)
        engine.build()
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        self.results["memory_mb"] = {
            "current": current / (1024 * 1024),
            "peak": peak / (1024 * 1024),
        }
        
        print(f"  Current: {current / (1024*1024):.1f}MB")
        print(f"  Peak: {peak / (1024*1024):.1f}MB")
    
    def benchmark_throughput(self):
        """Throughput ölç (queries/second)."""
        print("\n⚡ Throughput Benchmark...")
        
        engine = AnchorEngine(self.rules_path, self.index_path)
        engine.build()
        
        queries = [
            ("X1 hakkında", "X1, bir işlemcidir."),
            ("Y2 nedir", "Y2, bir sensördür."),
        ] * 50  # 100 queries
        
        t0 = time.perf_counter()
        for q, output in queries:
            engine.process(q, output)
        t1 = time.perf_counter()
        
        elapsed = t1 - t0
        qps = len(queries) / elapsed
        
        self.results["throughput"] = {
            "qps": qps,
            "total_queries": len(queries),
            "elapsed_ms": elapsed * 1000,
        }
        
        print(f"  {qps:.1f} queries/second ({len(queries)} queries in {elapsed*1000:.0f}ms)")


def print_report(results: dict):
    """Konsol raporu yazdır."""
    print("\n" + "=" * 60)
    print("BENCHMARK REPORT")
    print("=" * 60)
    
    print("\n📊 Cold Start:")
    cs = results["cold_start_ms"]
    print(f"  p50: {cs['p50']:.1f}ms | min: {cs['min']:.1f}ms | max: {cs['max']:.1f}ms")
    
    print("\n📊 Query Latency:")
    ql = results["query_latency_us"]
    print(f"  p50: {ql['p50']:.0f}μs | p95: {ql['p95']:.0f}μs | p99: {ql['p99']:.0f}μs")
    
    print("\n📊 Conflict Detection Accuracy:")
    acc = results["conflict_accuracy"]
    print(f"  {acc['accuracy']:.1%} ({acc['correct']}/{acc['total']})")
    
    print("\n📊 Patch Latency:")
    pl = results["patch_latency_us"]
    print(f"  Avg: {pl['avg']:.0f}μs")
    
    print("\n📊 Memory:")
    mem = results["memory_mb"]
    print(f"  Current: {mem['current']:.1f}MB | Peak: {mem['peak']:.1f}MB")
    
    print("\n📊 Throughput:")
    thr = results["throughput"]
    print(f"  {thr['qps']:.1f} queries/second")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Anchor Benchmark Suite")
    parser.add_argument("--rules", default="/tmp/anchor_benchmark_rules", help="Rules dizini")
    parser.add_argument("--index", default="/tmp/anchor_benchmark.idx", help="Index dosyası")
    parser.add_argument("--generate", action="store_true", help="Rule üret ve çalıştır")
    parser.add_argument("--count", type=int, default=1000, help="Rule sayısı")
    
    args = parser.parse_args()
    
    if args.generate:
        from generate_rules import generate_rules
        rules_path = generate_rules(args.count, args.rules)
    else:
        rules_path = args.rules
    
    runner = BenchmarkRunner(rules_path, args.index)
    results = runner.run_all()
    print_report(results)
