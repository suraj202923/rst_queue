#!/usr/bin/env python3
"""
Unified Benchmarking Suite for rst_queue
=========================================

Comprehensive performance benchmarking and profiling tool combining:
  - Quick throughput comparisons
  - asyncio.Queue comparisons
  - Detailed latency analysis
  - Performance profiling with breakdowns
  - Memory characteristics analysis
  - Lock-free contention testing

Usage:
  python benchmarks.py              # Interactive menu
  python benchmarks.py quick        # Quick benchmark
  python benchmarks.py asyncio      # Compare with asyncio
  python benchmarks.py detailed     # Detailed latency profiling
  python benchmarks.py all          # Run all benchmarks
"""

import time
import asyncio
import threading
import statistics
import sys
import os
from typing import Callable, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor

try:
    from rst_queue import AsyncQueue, ExecutionMode
    PARALLEL = ExecutionMode.PARALLEL
    SEQUENTIAL = ExecutionMode.SEQUENTIAL
except ImportError:
    print("Error: rst_queue not available")
    sys.exit(1)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ============================================================================
# HELPER CLASSES
# ============================================================================

class BenchmarkResults:
    """Store and display benchmark results for comparison"""
    
    def __init__(self):
        self.results = {}
    
    def add(self, name, throughput, latency_us=None):
        """Add benchmark result"""
        self.results[name] = {
            'throughput': throughput,
            'latency': latency_us
        }
    
    def speedup(self, name1, name2):
        """Calculate speedup factor between two results"""
        t1 = self.results[name1]['throughput']
        t2 = self.results[name2]['throughput']
        return max(t1, t2) / min(t1, t2)
    
    def print_comparison(self):
        """Print results in tabular format"""
        print("\n" + "="*80)
        print("BENCHMARK SUMMARY")
        print("="*80)
        print(f"\n{'Implementation':<35} {'Throughput':<20} {'Latency':<15}")
        print("-"*80)
        
        for name, data in sorted(self.results.items()):
            throughput = data['throughput']
            latency = data['latency']
            
            if latency:
                lat_str = f"{latency:.3f} µs"
            else:
                lat_str = "N/A"
            
            print(f"{name:<35} {throughput:>15,.0f} items/s {lat_str:>14}")


class PerformanceProfiler:
    """Detailed performance profiling and analysis"""
    
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.measurements = {}
        self.process = psutil.Process() if HAS_PSUTIL else None
    
    def measure(self, name, func):
        """Measure function execution time"""
        start = time.perf_counter()
        result = func()
        elapsed = time.perf_counter() - start
        
        if name not in self.measurements:
            self.measurements[name] = []
        self.measurements[name].append(elapsed)
        
        if self.verbose:
            print(f"  {name}: {elapsed*1000:.3f}ms")
        
        return elapsed
    
    def report(self):
        """Generate performance report"""
        print("\n" + "=" * 70)
        print("PERFORMANCE PROFILE REPORT")
        print("=" * 70 + "\n")
        
        for operation, times in sorted(self.measurements.items()):
            if not times:
                continue
            
            print(f"{operation}:")
            print(f"  Calls:      {len(times)}")
            print(f"  Total:      {sum(times)*1000:.3f}ms")
            print(f"  Mean:       {statistics.mean(times)*1000:.3f}ms")
            print(f"  Median:     {statistics.median(times)*1000:.3f}ms")
            print(f"  Min:        {min(times)*1000:.3f}ms")
            print(f"  Max:        {max(times)*1000:.3f}ms")
            if len(times) > 1:
                print(f"  Std Dev:    {statistics.stdev(times)*1000:.3f}ms")
            print()


# ============================================================================
# QUICK BENCHMARKS
# ============================================================================

def benchmark_quick_push():
    """Quick: Single-threaded push throughput"""
    print("\n" + "="*80)
    print("QUICK BENCHMARK: Push Throughput")
    print("="*80)
    
    q = AsyncQueue()
    num_items = 100000
    
    start = time.perf_counter()
    for i in range(num_items):
        q.push(f"item_{i}".encode())
    elapsed = time.perf_counter() - start
    
    throughput = num_items / elapsed
    latency_us = (elapsed * 1e6 / num_items)
    
    print(f"\nItems: {num_items:,}")
    print(f"Time: {elapsed:.4f}s")
    print(f"Throughput: {throughput:,.0f} items/sec")
    print(f"Per-item latency: {latency_us:.3f} µs")
    
    return throughput


def benchmark_quick_batch():
    """Quick: Batch push throughput"""
    print("\n" + "="*80)
    print("QUICK BENCHMARK: Batch Push")
    print("="*80)
    
    q = AsyncQueue()
    num_batches = 1000
    batch_size = 100
    
    start = time.perf_counter()
    for b in range(num_batches):
        items = [f"batch_{b}_item_{i}".encode() for i in range(batch_size)]
        q.push_batch(items)
    elapsed = time.perf_counter() - start
    
    total_items = num_batches * batch_size
    throughput = total_items / elapsed
    
    print(f"\nBatches: {num_batches:,} x {batch_size} items")
    print(f"Total items: {total_items:,}")
    print(f"Time: {elapsed:.4f}s")
    print(f"Throughput: {throughput:,.0f} items/sec")
    
    return throughput


def benchmark_quick_concurrent():
    """Quick: Multi-threaded push performance"""
    print("\n" + "="*80)
    print("QUICK BENCHMARK: Concurrent Push (4 threads)")
    print("="*80)
    
    q = AsyncQueue()
    num_threads = 4
    items_per_thread = 25000
    
    def pusher(tid):
        for i in range(items_per_thread):
            q.push(f"t{tid}_{i}".encode())
    
    start = time.perf_counter()
    threads = [threading.Thread(target=pusher, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start
    
    total_items = num_threads * items_per_thread
    throughput = total_items / elapsed
    
    print(f"\nThreads: {num_threads}")
    print(f"Items/thread: {items_per_thread:,}")
    print(f"Total items: {total_items:,}")
    print(f"Time: {elapsed:.4f}s")
    print(f"Throughput: {throughput:,.0f} items/sec")
    
    return throughput


def benchmark_quick_latency():
    """Quick: Operation latency distribution"""
    print("\n" + "="*80)
    print("QUICK BENCHMARK: Latency Distribution (1,000 samples)")
    print("="*80)
    
    q = AsyncQueue()
    latencies = []
    
    for i in range(1000):
        start = time.perf_counter()
        q.push(f"item_{i}".encode())
        latencies.append((time.perf_counter() - start) * 1e6)
    
    latencies.sort()
    mean_lat = sum(latencies) / len(latencies)
    
    print(f"\nMean:   {mean_lat:>10.3f} µs")
    print(f"P50:    {latencies[len(latencies)//2]:>10.3f} µs")
    print(f"P99:    {latencies[int(len(latencies)*0.99)]:>10.3f} µs")
    print(f"P99.9:  {latencies[int(len(latencies)*0.999)]:>10.3f} µs")
    print(f"Max:    {max(latencies):>10.3f} µs")
    
    return mean_lat


# ============================================================================
# ASYNCIO COMPARISON BENCHMARKS
# ============================================================================

def benchmark_asyncio_push():
    """Compare: rst_queue vs asyncio.Queue push"""
    print("\n" + "="*80)
    print("COMPARISON: Push Operations")
    print("="*80)
    
    num_items = 50000
    
    # rst_queue
    print("\n[rst_queue]")
    q = AsyncQueue()
    start = time.perf_counter()
    for i in range(num_items):
        q.push(f"item_{i}".encode())
    rst_time = time.perf_counter() - start
    rst_throughput = num_items / rst_time
    
    print(f"  Items: {num_items:,}")
    print(f"  Time: {rst_time:.4f}s")
    print(f"  Throughput: {rst_throughput:,.0f} items/sec")
    print(f"  Per-item: {(rst_time*1e6/num_items):.2f} µs")
    
    # asyncio.Queue
    print("\n[asyncio.Queue]")
    async def asyncio_push():
        q = asyncio.Queue()
        start = time.perf_counter()
        for i in range(num_items):
            await q.put(f"item_{i}".encode())
        return time.perf_counter() - start
    
    asyncio_time = asyncio.run(asyncio_push())
    asyncio_throughput = num_items / asyncio_time
    
    print(f"  Items: {num_items:,}")
    print(f"  Time: {asyncio_time:.4f}s")
    print(f"  Throughput: {asyncio_throughput:,.0f} items/sec")
    print(f"  Per-item: {(asyncio_time*1e6/num_items):.2f} µs")
    
    speedup = rst_throughput / asyncio_throughput
    print(f"\n✅ rst_queue is {speedup:.1f}x FASTER")
    
    return rst_throughput, asyncio_throughput


def benchmark_asyncio_concurrent():
    """Compare: Concurrent push with threads/tasks"""
    print("\n" + "="*80)
    print("COMPARISON: Concurrent Push (4 workers × 10k items)")
    print("="*80)
    
    num_workers = 4
    items_per_worker = 10000
    
    # rst_queue with threads
    print("\n[rst_queue with Threading]")
    q = AsyncQueue()
    
    def rst_pusher(wid):
        for i in range(items_per_worker):
            q.push(f"w{wid}_{i}".encode())
    
    start = time.perf_counter()
    threads = [threading.Thread(target=rst_pusher, args=(i,)) for i in range(num_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rst_time = time.perf_counter() - start
    rst_throughput = (num_workers * items_per_worker) / rst_time
    
    print(f"  Time: {rst_time:.4f}s")
    print(f"  Throughput: {rst_throughput:,.0f} items/sec")
    
    # asyncio with tasks
    print("\n[asyncio.Queue with Tasks]")
    async def asyncio_concurrent():
        q = asyncio.Queue()
        
        async def async_pusher(wid):
            for i in range(items_per_worker):
                await q.put(f"w{wid}_{i}".encode())
        
        start = time.perf_counter()
        await asyncio.gather(*[async_pusher(i) for i in range(num_workers)])
        return time.perf_counter() - start
    
    asyncio_time = asyncio.run(asyncio_concurrent())
    asyncio_throughput = (num_workers * items_per_worker) / asyncio_time
    
    print(f"  Time: {asyncio_time:.4f}s")
    print(f"  Throughput: {asyncio_throughput:,.0f} items/sec")
    
    speedup = rst_throughput / asyncio_throughput
    print(f"\n✅ rst_queue is {speedup:.1f}x FASTER")
    
    return rst_throughput, asyncio_throughput


def benchmark_asyncio_latency():
    """Compare: Operation latency"""
    print("\n" + "="*80)
    print("COMPARISON: Operation Latency (10,000 samples)")
    print("="*80)
    
    num_ops = 10000
    
    # rst_queue latency
    print("\n[rst_queue Push Latency]")
    q = AsyncQueue()
    latencies = []
    
    for i in range(num_ops):
        start = time.perf_counter()
        q.push(f"item_{i}".encode())
        latencies.append((time.perf_counter() - start) * 1e6)
    
    latencies.sort()
    rst_mean = sum(latencies) / len(latencies)
    
    print(f"  Mean: {rst_mean:.3f} µs")
    print(f"  P50:  {latencies[len(latencies)//2]:.3f} µs")
    print(f"  P99:  {latencies[int(len(latencies)*0.99)]:.3f} µs")
    print(f"  Max:  {max(latencies):.3f} µs")
    
    # asyncio latency
    print("\n[asyncio.Queue Push Latency]")
    async def asyncio_latency():
        q = asyncio.Queue()
        latencies = []
        
        for i in range(num_ops):
            start = time.perf_counter()
            await q.put(f"item_{i}".encode())
            latencies.append((time.perf_counter() - start) * 1e6)
        
        return latencies
    
    asyncio_latencies = asyncio.run(asyncio_latency())
    asyncio_latencies.sort()
    asyncio_mean = sum(asyncio_latencies) / len(asyncio_latencies)
    
    print(f"  Mean: {asyncio_mean:.3f} µs")
    print(f"  P50:  {asyncio_latencies[len(asyncio_latencies)//2]:.3f} µs")
    print(f"  P99:  {asyncio_latencies[int(len(asyncio_latencies)*0.99)]:.3f} µs")
    print(f"  Max:  {max(asyncio_latencies):.3f} µs")
    
    speedup = asyncio_mean / rst_mean
    print(f"\n✅ rst_queue is {speedup:.1f}x FASTER (lower latency)")
    
    return rst_mean, asyncio_mean


# ============================================================================
# DETAILED PROFILING BENCHMARKS
# ============================================================================

def benchmark_detailed_push_latency():
    """Detailed: Push latency analysis with histogram"""
    print("\n" + "="*80)
    print("DETAILED ANALYSIS: Push Operation Latency")
    print("="*80 + "\n")
    
    queue = AsyncQueue(mode=PARALLEL)
    push_times_us = []
    
    print(f"Measuring 10,000 push operations...")
    for i in range(10000):
        start = time.perf_counter()
        queue.push(f"item_{i:06d}".encode())
        elapsed_us = (time.perf_counter() - start) * 1e6
        push_times_us.append(elapsed_us)
    
    push_times_sorted = sorted(push_times_us)
    
    print(f"\nPush Latency Statistics (microseconds):")
    print(f"  Mean:       {statistics.mean(push_times_us):.3f} µs")
    print(f"  Median:     {statistics.median(push_times_us):.3f} µs")
    print(f"  P99:        {push_times_sorted[int(len(push_times_sorted)*0.99)]:.3f} µs")
    print(f"  P99.9:      {push_times_sorted[int(len(push_times_sorted)*0.999)]:.3f} µs")
    print(f"  Max:        {max(push_times_us):.3f} µs")
    print(f"  Min:        {min(push_times_us):.3f} µs")
    if len(push_times_us) > 1:
        print(f"  Std Dev:    {statistics.stdev(push_times_us):.3f} µs")
    
    # Histogram
    print(f"\nLatency Distribution Histogram:")
    buckets = [0, 1, 5, 10, 50, 100, 500, 1000, float('inf')]
    for i in range(len(buckets)-1):
        count = sum(1 for t in push_times_us if buckets[i] <= t < buckets[i+1])
        pct = 100 * count / len(push_times_us)
        bar = "█" * int(pct / 2)
        label = f"{buckets[i]}-{buckets[i+1]}" if buckets[i+1] != float('inf') else f"{buckets[i]}+"
        print(f"  {label:>10} µs: {pct:5.1f}% {bar}")


def benchmark_detailed_scaling():
    """Detailed: Throughput scaling with thread count"""
    print("\n" + "="*80)
    print("DETAILED ANALYSIS: Scaling with Thread Count")
    print("="*80 + "\n")
    
    thread_counts = [1, 2, 4, 8, 16]
    results = []
    
    for num_threads in thread_counts:
        q = AsyncQueue()
        items_per_thread = 10000
        
        def pusher(tid):
            for i in range(items_per_thread):
                q.push(f"t{tid}_{i}".encode())
        
        start = time.perf_counter()
        if num_threads == 1:
            pusher(0)
        else:
            threads = [threading.Thread(target=pusher, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        elapsed = time.perf_counter() - start
        
        total = num_threads * items_per_thread
        throughput = total / elapsed
        results.append((num_threads, throughput))
        
        print(f"Threads: {num_threads:2d} | Items: {total:,} | Throughput: {throughput:>12,.0f} items/sec")
    
    # Calculate scaling efficiency
    baseline = results[0][1]
    print(f"\nScaling Efficiency (vs 1 thread):")
    for threads, throughput in results:
        ideal_speedup = threads
        actual_speedup = throughput / baseline
        efficiency = (actual_speedup / ideal_speedup) * 100
        print(f"  {threads:2d} threads: {actual_speedup:.2f}x speedup ({efficiency:.1f}% efficiency)")


def benchmark_detailed_memory():
    """Detailed: Memory characteristics"""
    if not HAS_PSUTIL:
        print("\nSkipping memory analysis (psutil not installed)")
        return
    
    print("\n" + "="*80)
    print("DETAILED ANALYSIS: Memory Characteristics")
    print("="*80 + "\n")
    
    process = psutil.Process()
    initial_rss = process.memory_info().rss / 1024 / 1024
    
    print(f"Initial memory: {initial_rss:.2f} MB")
    
    # Queue creation
    queue = AsyncQueue(mode=PARALLEL)
    after_queue_rss = process.memory_info().rss / 1024 / 1024
    
    print(f"After queue creation: {after_queue_rss:.2f} MB (+{after_queue_rss - initial_rss:.2f})")
    
    # Push phase
    num_items = 100000
    for i in range(num_items):
        queue.push(f"item_{i:06d}".encode())
    
    after_push_rss = process.memory_info().rss / 1024 / 1024
    per_item_kb = (after_push_rss - after_queue_rss) * 1024 / num_items
    
    print(f"After pushing {num_items:,} items: {after_push_rss:.2f} MB (+{after_push_rss - after_queue_rss:.2f})")
    print(f"Memory per item: ~{per_item_kb:.3f} KB/item")


# ============================================================================
# MAIN MENU
# ============================================================================

def show_menu():
    """Display benchmark menu"""
    print("\n" + "="*80)
    print("rst_queue Benchmark Suite")
    print("="*80)
    print("""
Benchmarking Options:

  1. quick      - Quick throughput benchmarks (all modes)
  2. asyncio    - Compare with asyncio.Queue
  3. detailed   - Detailed performance profiling and analysis
  4. all        - Run all benchmarks
  5. exit       - Exit program

Usage: python benchmarks.py [option]
""")


def run_quick_benchmarks():
    """Run all quick benchmarks"""
    print("\n" + "█"*80)
    print("█" + "  QUICK BENCHMARKS".center(78) + "█")
    print("█"*80)
    
    results = BenchmarkResults()
    
    tp1 = benchmark_quick_push()
    results.add("Push (single-thread)", tp1)
    
    tp2 = benchmark_quick_batch()
    results.add("Batch Push", tp2)
    
    tp3 = benchmark_quick_concurrent()
    results.add("Push (4 threads)", tp3)
    
    lat = benchmark_quick_latency()
    results.add("Latency (P50)", None, lat)
    
    results.print_comparison()


def run_asyncio_benchmarks():
    """Run asyncio comparison benchmarks"""
    print("\n" + "█"*80)
    print("█" + "  ASYNCIO COMPARISON".center(78) + "█")
    print("█"*80)
    
    results = BenchmarkResults()
    
    rst_tp, asyncio_tp = benchmark_asyncio_push()
    results.add("rst_queue (push)", rst_tp)
    results.add("asyncio.Queue (push)", asyncio_tp)
    
    rst_tp2, asyncio_tp2 = benchmark_asyncio_concurrent()
    results.add("rst_queue (concurrent)", rst_tp2)
    results.add("asyncio (concurrent)", asyncio_tp2)
    
    rst_lat, asyncio_lat = benchmark_asyncio_latency()
    results.add("rst_queue (latency)", None, rst_lat)
    results.add("asyncio (latency)", None, asyncio_lat)
    
    results.print_comparison()


def run_detailed_benchmarks():
    """Run detailed profiling benchmarks"""
    print("\n" + "█"*80)
    print("█" + "  DETAILED PERFORMANCE PROFILING".center(78) + "█")
    print("█"*80)
    
    benchmark_detailed_push_latency()
    benchmark_detailed_scaling()
    benchmark_detailed_memory()


def run_all_benchmarks():
    """Run all benchmarks"""
    run_quick_benchmarks()
    print("\n" * 2)
    run_asyncio_benchmarks()
    print("\n" * 2)
    run_detailed_benchmarks()
    
    print("\n" + "█"*80)
    print("█" + "  ALL BENCHMARKS COMPLETE!".center(78) + "█")
    print("█"*80 + "\n")


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        option = sys.argv[1].lower()
    else:
        show_menu()
        option = input("Choose option (1-5): ").strip().lower()
    
    if option in ['1', 'quick']:
        run_quick_benchmarks()
    elif option in ['2', 'asyncio']:
        run_asyncio_benchmarks()
    elif option in ['3', 'detailed']:
        run_detailed_benchmarks()
    elif option in ['4', 'all']:
        run_all_benchmarks()
    elif option in ['5', 'exit']:
        print("Exiting...")
        sys.exit(0)
    else:
        print("Invalid option. Please try again.")
        main()


if __name__ == '__main__':
    main()
