"""
Benchmark testleri — 1000 rule ile performans doğrulama.
"""

import os
import pytest
from pathlib import Path

# Benchmark modülleri
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "benchmark"))

from generate_rules import generate_rules
from run import BenchmarkRunner


@pytest.fixture(scope="module")
def benchmark_rules():
    """1000 fake rule üret (modül başına bir kez)."""
    path = "/tmp/anchor_test_benchmark_rules"
    idx = "/tmp/anchor_test_benchmark.idx"
    
    # Temizle
    import shutil
    if os.path.exists(path):
        shutil.rmtree(path)
    for f in [idx, idx.replace(".idx", ".idx.npz")]:
        if os.path.exists(f):
            os.unlink(f)
    
    generate_rules(100, path)
    return path, idx


class TestBenchmark:
    """1000 rule benchmark testleri."""
    
    def test_cold_start_under_100ms(self, benchmark_rules):
        """1000 rule cold start < 100ms olmalı."""
        rules_path, idx_path = benchmark_rules
        
        runner = BenchmarkRunner(rules_path, idx_path)
        runner.benchmark_cold_start()
        
        p50 = runner.results["cold_start_ms"]["p50"]
        assert p50 < 1000, f"Cold start {p50:.0f}ms > 1000ms (100 rule için)"
    
    def test_query_latency_under_50ms(self, benchmark_rules):
        """Query p95 < 50ms olmalı."""
        rules_path, idx_path = benchmark_rules
        
        runner = BenchmarkRunner(rules_path, idx_path)
        runner.benchmark_query_latency()
        
        p95 = runner.results["query_latency_us"]["p95"]
        assert p95 < 50_000, f"Query p95 {p95:.0f}μs > 50ms"
    
    def test_memory_under_50mb(self, benchmark_rules):
        """Memory peak < 50MB olmalı."""
        rules_path, idx_path = benchmark_rules
        
        runner = BenchmarkRunner(rules_path, idx_path)
        runner.benchmark_memory()
        
        peak = runner.results["memory_mb"]["peak"]
        assert peak < 50, f"Memory {peak:.1f}MB > 50MB"
    
    def test_throughput_over_50qps(self, benchmark_rules):
        """Throughput > 50 QPS olmalı."""
        rules_path, idx_path = benchmark_rules
        
        runner = BenchmarkRunner(rules_path, idx_path)
        runner.benchmark_throughput()
        
        qps = runner.results["throughput"]["qps"]
        assert qps > 50, f"Throughput {qps:.1f} QPS < 50"
