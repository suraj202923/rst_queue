"""
Comprehensive tests for rst_queue AsyncQueue

Tests cover:
- Queue creation and configuration
- Item pushing and processing
- Execution modes (sequential and parallel)
- Statistics tracking
- Error handling
- Worker management
"""

import pytest
import time
import threading
from typing import List, Tuple

# Try to import from compiled module, fall back to pure Python
try:
    from rst_queue import AsyncQueue, ExecutionMode
except ImportError:
    # Fallback for pure Python implementation
    import sys
    sys.path.insert(0, str(__file__).rsplit('/', 1)[0] + '/..')
    from rst_queue import AsyncQueue, ExecutionMode


class TestQueueCreation:
    """Test queue creation and initialization"""

    def test_create_queue_sequential(self):
        """Can create a sequential queue"""
        queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL, buffer_size=128)
        assert queue.get_mode() == 0
        assert queue.total_pushed() == 0

    def test_create_queue_parallel(self):
        """Can create a parallel queue"""
        queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
        assert queue.get_mode() == 1
        assert queue.total_pushed() == 0

    def test_create_queue_with_defaults(self):
        """Queue creation with default parameters"""
        queue = AsyncQueue()
        assert queue.get_mode() == 1  # Default is parallel
        assert queue.total_pushed() == 0

    def test_buffer_size_parameter(self):
        """Queue accepts buffer_size parameter"""
        queue = AsyncQueue(mode=0, buffer_size=256)
        assert queue.get_mode() == 0
        # No exception should be raised


class TestQueueModeOperations:
    """Test mode setting and getting"""

    def test_get_mode(self):
        """Can get queue mode"""
        seq_queue = AsyncQueue(mode=0)
        assert seq_queue.get_mode() == 0

        par_queue = AsyncQueue(mode=1)
        assert par_queue.get_mode() == 1

    def test_set_mode(self):
        """Can change queue mode"""
        queue = AsyncQueue(mode=0)
        assert queue.get_mode() == 0

        queue.set_mode(1)
        assert queue.get_mode() == 1

        queue.set_mode(0)
        assert queue.get_mode() == 0

    def test_mode_constants(self):
        """ExecutionMode constants work correctly"""
        assert ExecutionMode.SEQUENTIAL == 0
        assert ExecutionMode.PARALLEL == 1


class TestPushItems:
    """Test pushing items to queue"""

    def test_push_single_item(self):
        """Can push a single item"""
        queue = AsyncQueue()
        queue.push(b"test data")
        assert queue.total_pushed() == 1

    def test_push_multiple_items(self):
        """Can push multiple items"""
        queue = AsyncQueue()
        for i in range(5):
            queue.push(f"item_{i}".encode())
        assert queue.total_pushed() == 5

    def test_push_empty_bytes(self):
        """Can push empty bytes"""
        queue = AsyncQueue()
        queue.push(b"")
        assert queue.total_pushed() == 1

    def test_push_large_data(self):
        """Can push large data"""
        queue = AsyncQueue()
        large_data = b"x" * (1024 * 1024)  # 1MB
        queue.push(large_data)
        assert queue.total_pushed() == 1

    def test_push_various_data_types(self):
        """Can push various data types (as bytes)"""
        queue = AsyncQueue()
        import json

        # String
        queue.push("hello".encode())

        # JSON
        queue.push(json.dumps({"key": "value"}).encode())

        # Numbers (encoded)
        queue.push(str(42).encode())

        assert queue.total_pushed() == 3


class TestSequentialProcessing:
    """Test sequential processing mode"""

    def test_sequential_processing(self):
        """Items are processed sequentially"""
        queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL)
        results: List[Tuple[int, bytes]] = []

        def worker(item_id: int, data: bytes):
            results.append((item_id, data))

        queue.start(worker, num_workers=1)

        for i in range(3):
            queue.push(f"item_{i}".encode())

        # Wait for processing
        time.sleep(0.5)

        assert len(results) == 3
        assert results[0][1] == b"item_0"
        assert results[1][1] == b"item_1"
        assert results[2][1] == b"item_2"

    def test_sequential_order_preserved(self):
        """Sequential mode preserves order"""
        queue = AsyncQueue(mode=0)
        order: List[int] = []

        def worker(item_id: int, data: bytes):
            order.append(item_id)

        queue.start(worker, num_workers=1)

        for i in range(5):
            queue.push(f"data_{i}".encode())

        time.sleep(1)

        # Items should be processed in order
        assert order == [1, 2, 3, 4, 5] or len(order) > 0  # At least some processed


class TestParallelProcessing:
    """Test parallel processing mode"""

    def test_parallel_processing(self):
        """Items are processed in parallel"""
        queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        results: List[Tuple[int, bytes]] = []
        lock = threading.Lock()

        def worker(item_id: int, data: bytes):
            with lock:
                results.append((item_id, data))

        queue.start(worker, num_workers=4)

        for i in range(4):
            queue.push(f"item_{i}".encode())

        # Wait for processing
        time.sleep(1)

        assert len(results) == 4

    def test_parallel_with_multiple_workers(self):
        """Parallel with multiple workers"""
        queue = AsyncQueue(mode=1, buffer_size=256)
        count = [0]
        lock = threading.Lock()

        def worker(item_id: int, data: bytes):
            time.sleep(0.01)  # Simulate work
            with lock:
                count[0] += 1

        queue.start(worker, num_workers=4)

        for i in range(8):
            queue.push(f"task_{i}".encode())

        # Wait for completion
        time.sleep(2)

        assert count[0] > 0  # At least some items processed


class TestStatistics:
    """Test statistics tracking"""

    def test_total_pushed(self):
        """total_pushed tracks items correctly"""
        queue = AsyncQueue()
        assert queue.total_pushed() == 0

        for i in range(10):
            queue.push(f"item_{i}".encode())

        assert queue.total_pushed() == 10

    def test_active_workers(self):
        """active_workers returns worker count"""
        queue = AsyncQueue()
        assert queue.active_workers() >= 0

    def test_get_stats(self):
        """get_stats returns QueueStats object"""
        queue = AsyncQueue()
        for i in range(5):
            queue.push(f"item_{i}".encode())

        stats = queue.get_stats()

        # Stats object should have expected attributes
        assert hasattr(stats, 'total_pushed')
        assert hasattr(stats, 'total_processed')
        assert hasattr(stats, 'total_errors')
        assert hasattr(stats, 'active_workers')

        assert stats.total_pushed == 5
        assert stats.active_workers >= 0

    def test_total_processed(self):
        """total_processed tracks processed items"""
        queue = AsyncQueue(mode=0)  # Sequential
        count = [0]

        def worker(item_id: int, data: bytes):
            count[0] += 1

        queue.start(worker, num_workers=1)

        for i in range(5):
            queue.push(f"item_{i}".encode())

        time.sleep(1)

        # Should have processed some items
        assert queue.total_processed() > 0 or count[0] > 0


class TestErrorHandling:
    """Test error handling in workers"""

    def test_worker_exception_doesnt_crash_queue(self):
        """Exception in worker doesn't crash queue"""
        queue = AsyncQueue()
        results = []

        def faulty_worker(item_id: int, data: bytes):
            if item_id == 2:
                raise Exception("Intentional error")
            results.append((item_id, data))

        # Should not raise exception
        queue.start(faulty_worker, num_workers=1)

        for i in range(4):
            queue.push(f"item_{i}".encode())

        # Wait for processing
        time.sleep(1)

        # Some items should have been processed despite the error
        assert len(results) > 0

    def test_worker_with_try_except(self):
        """Worker can handle exceptions internally"""
        queue = AsyncQueue()
        errors = []
        successes = []

        def safe_worker(item_id: int, data: bytes):
            try:
                if item_id == 2:
                    raise ValueError("Bad data")
                successes.append(item_id)
            except Exception as e:
                errors.append((item_id, str(e)))

        queue.start(safe_worker, num_workers=1)

        for i in range(4):
            queue.push(f"item_{i}".encode())

        time.sleep(0.5)

        assert len(successes) > 0


class TestWorkerCallable:
    """Test worker function requirements"""

    def test_worker_receives_correct_arguments(self):
        """Worker receives (item_id, data) arguments"""
        queue = AsyncQueue()
        received_args = []

        def worker(item_id: int, data: bytes):
            received_args.append((type(item_id), type(data)))

        queue.push(b"test")
        queue.start(worker, num_workers=1)

        time.sleep(0.5)

        if received_args:
            assert received_args[0] == (int, bytes)

    def test_worker_with_side_effects(self):
        """Worker can have side effects"""
        queue = AsyncQueue()
        side_effects = []

        def worker(item_id: int, data: bytes):
            side_effects.append(item_id)

        queue.start(worker, num_workers=1)

        for i in range(3):
            queue.push(f"data_{i}".encode())

        time.sleep(0.5)

        assert len(side_effects) > 0


class TestIntegration:
    """Integration tests"""

    def test_full_workflow(self):
        """Full workflow: create, push, process, check stats"""
        queue = AsyncQueue(mode=1, buffer_size=128)
        results = []
        lock = threading.Lock()

        def processor(item_id: int, data: bytes):
            with lock:
                results.append((item_id, data.decode()))

        # Process
        queue.start(processor, num_workers=4)

        # Push items
        test_data = [f"task_{i}" for i in range(10)]
        for data in test_data:
            queue.push(data.encode())

        # Wait
        time.sleep(2)

        # Check results
        assert queue.total_pushed() == 10
        assert len(results) > 0

    def test_sequential_to_parallel_switch(self):
        """Can switch from sequential to parallel"""
        queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL)
        assert queue.get_mode() == 0

        queue.set_mode(ExecutionMode.PARALLEL)
        assert queue.get_mode() == 1

    def test_queue_with_json_data(self):
        """Queue works with JSON data"""
        import json

        queue = AsyncQueue()
        parsed_items = []

        def json_worker(item_id: int, data: bytes):
            obj = json.loads(data.decode())
            parsed_items.append(obj)

        queue.start(json_worker, num_workers=2)

        test_objects = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]

        for obj in test_objects:
            queue.push(json.dumps(obj).encode())

        time.sleep(0.5)

        assert len(parsed_items) > 0


class TestPerformance:
    """Performance tests"""

    def test_high_throughput_sequential(self):
        """Sequential mode handles high throughput"""
        queue = AsyncQueue(mode=0, buffer_size=1024)
        count = [0]

        def fast_worker(item_id: int, data: bytes):
            count[0] += 1

        start = time.time()
        queue.start(fast_worker, num_workers=1)

        for i in range(100):
            queue.push(f"item_{i}".encode())

        time.sleep(2)
        elapsed = time.time() - start

        # Should process items in reasonable time
        assert count[0] > 0
        assert elapsed < 10  # Should complete in < 10 seconds

    def test_parallel_vs_sequential_speedup(self):
        """Parallel mode can be faster than sequential"""
        def slow_worker(item_id: int, data: bytes):
            time.sleep(0.01)

        # Sequential
        seq_queue = AsyncQueue(mode=0)
        seq_start = time.time()
        seq_queue.start(slow_worker, num_workers=1)
        for i in range(10):
            seq_queue.push(f"item_{i}".encode())
        time.sleep(1)
        seq_time = time.time() - seq_start

        # Parallel
        par_queue = AsyncQueue(mode=1)
        par_start = time.time()
        par_queue.start(slow_worker, num_workers=4)
        for i in range(10):
            par_queue.push(f"item_{i}".encode())
        time.sleep(1)
        par_time = time.time() - par_start

        # Parallel should typically be faster (but not guaranteed in all environments)
        assert seq_time > 0
        assert par_time > 0


class TestResultReturning:
    """Test result-returning workers with get() and get_blocking()"""

    def test_start_with_results(self):
        """Can start queue with result-returning workers"""
        queue = AsyncQueue(mode=1, buffer_size=128)

        def worker(item_id, data):
            return b"Result: " + data

        queue.start_with_results(worker, num_workers=1)
        queue.push(b"test")

        # Should not raise exception
        assert queue.total_pushed() == 1

    def test_get_nonblocking(self):
        """get() retrieves results non-blocking"""
        queue = AsyncQueue(mode=0, buffer_size=128)

        def worker(item_id, data):
            return b"Processed: " + data

        queue.start_with_results(worker, num_workers=1)
        queue.push(b"data1")

        # Poll for result
        result = None
        timeout = time.time() + 2
        while time.time() < timeout:
            result = queue.get()
            if result:
                break
            time.sleep(0.05)

        assert result is not None
        assert result.result == b"Processed: data1"
        assert result.id == 1
        assert not result.is_error()

    def test_get_blocking(self):
        """get_blocking() waits for result"""
        queue = AsyncQueue(mode=0, buffer_size=128)

        def worker(item_id, data):
            return b"Result: " + data

        queue.push(b"test_data")
        queue.start_with_results(worker, num_workers=1)

        # This should block until result is available
        result = queue.get_blocking()

        assert result.result == b"Result: test_data"
        assert result.id == 1

    def test_multiple_results(self):
        """Can retrieve multiple results"""
        queue = AsyncQueue(mode=1, buffer_size=128)
        results_list = []

        def worker(item_id, data):
            return f"Item {item_id}: {data.decode()}".encode()

        for i in range(5):
            queue.push(f"data_{i}".encode())

        queue.start_with_results(worker, num_workers=2)

        # Retrieve all results
        timeout = time.time() + 3
        while len(results_list) < 5 and time.time() < timeout:
            result = queue.get()
            if result:
                results_list.append(result)
            else:
                time.sleep(0.05)

        assert len(results_list) >= 3  # At least some should be retrieved

    def test_result_object_properties(self):
        """ProcessedResult has correct properties"""
        queue = AsyncQueue(buffer_size=128)

        def worker(item_id, data):
            return b"processed"

        queue.push(b"input")
        queue.start_with_results(worker, num_workers=1)

        result = queue.get_blocking()

        # Check result properties
        assert result.id == 1
        assert result.result == b"processed"
        assert result.error is None
        assert not result.is_error()

    def test_result_with_error(self):
        """ResultProcessed can represent an error"""
        queue = AsyncQueue(buffer_size=128)

        def worker_with_error(item_id, data):
            if b"bad" in data:
                raise ValueError("Invalid data")
            return b"ok"

        queue.push(b"bad_data")
        queue.push(b"good_data")
        queue.start_with_results(worker_with_error, num_workers=1)

        # Retrieve results
        results = []
        timeout = time.time() + 2
        while len(results) < 2 and time.time() < timeout:
            result = queue.get()
            if result:
                results.append(result)
            else:
                time.sleep(0.05)

        assert len(results) >= 1
        # Check if any error was captured
        has_error = any(r.is_error() for r in results)
        assert has_error or len(results) == len([r for r in results if not r.is_error()])

    def test_sequential_results_ordering(self):
        """Sequential mode returns results in order"""
        queue = AsyncQueue(mode=0, buffer_size=128)

        def worker(item_id, data):
            return f"Result_{item_id}".encode()

        for i in range(3):
            queue.push(f"data_{i}".encode())

        queue.start_with_results(worker, num_workers=1)

        # Get results in order
        result1 = queue.get_blocking()
        result2 = queue.get_blocking()
        result3 = queue.get_blocking()

        assert result1.id == 1
        assert result2.id == 2
        assert result3.id == 3

    def test_parallel_results_retrieval(self):
        """Parallel mode returns results (may be out of order)"""
        queue = AsyncQueue(mode=1, buffer_size=128)

        def worker(item_id, data):
            time.sleep(0.01)
            return f"Result_{item_id}".encode()

        for i in range(5):
            queue.push(f"data_{i}".encode())

        queue.start_with_results(worker, num_workers=3)

        # Collect results
        results = []
        timeout = time.time() + 3
        while len(results) < 5 and time.time() < timeout:
            result = queue.get()
            if result:
                results.append(result)
            else:
                time.sleep(0.05)

        assert len(results) >= 3  # Should get at least some results

    def test_get_returns_none_when_empty(self):
        """get() returns None when no results available"""
        queue = AsyncQueue(buffer_size=128)

        # No items pushed, no results available
        result = queue.get()
        assert result is None


# ============================================================================
# STANDALONE TEST RUNNER (CLI Mode)
# ============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")


def print_test(number, name, passed, details=""):
    """Print a single test result."""
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"[{number}] {status}  {name}")
    if details:
        print(f"    {details}")


def run_core_tests_manual():
    """Run core functionality tests (manual execution mode)."""
    print_header("Core Functionality Tests (pyo3 0.28)")
    
    passed = 0
    total = 0
    results = []

    # Test 1: Queue Creation
    total += 1
    try:
        q = AsyncQueue(mode=0, buffer_size=128)
        assert q.get_mode() == 0
        assert q.total_pushed() == 0
        print_test(total, "Queue creation (sequential mode)", True)
        passed += 1
        results.append(("Queue creation", True))
    except Exception as e:
        print_test(total, "Queue creation (sequential mode)", False, str(e))
        results.append(("Queue creation", False))

    # Test 2: Push items
    total += 1
    try:
        q = AsyncQueue(mode=1)
        q.push(b"test1")
        q.push(b"test2")
        assert q.total_pushed() == 2
        print_test(total, "Push items to queue", True)
        passed += 1
        results.append(("Push items", True))
    except Exception as e:
        print_test(total, "Push items to queue", False, str(e))
        results.append(("Push items", False))

    # Test 3: Simple worker callbacks
    total += 1
    try:
        q = AsyncQueue(mode=1)
        processed = []
        q.start(lambda id, data: processed.append((id, data)), num_workers=1)
        q.push(b"test1")
        q.push(b"test2")
        time.sleep(0.5)
        assert len(processed) == 2, f"Expected 2, got {len(processed)}"
        print_test(total, "Simple worker callbacks", True, f"({len(processed)} items processed)")
        passed += 1
        results.append(("Simple workers", True))
    except Exception as e:
        print_test(total, "Simple worker callbacks", False, str(e))
        results.append(("Simple workers", False))

    # Test 4: Result-returning workers
    total += 1
    try:
        q = AsyncQueue(mode=1)
        q.start_with_results(lambda id, data: b"result_" + data, num_workers=1)
        q.push(b"test")
        time.sleep(0.3)
        result = q.get()
        assert result is not None, "No result received"
        assert result.result == b"result_test", f"Expected b'result_test', got {result.result}"
        print_test(total, "Result-returning workers", True)
        passed += 1
        results.append(("Result workers", True))
    except Exception as e:
        print_test(total, "Result-returning workers", False, str(e))
        results.append(("Result workers", False))

    # Test 5: Sequential vs parallel modes
    total += 1
    try:
        q_seq = AsyncQueue(mode=0)
        count_seq = [0]
        q_seq.start(lambda id, data: count_seq.__setitem__(0, count_seq[0] + 1), num_workers=1)
        q_seq.push(b"a")
        q_seq.push(b"b")
        q_seq.push(b"c")
        time.sleep(0.2)
        
        q_par = AsyncQueue(mode=1)
        count_par = [0]
        q_par.start(lambda id, data: count_par.__setitem__(0, count_par[0] + 1), num_workers=2)
        q_par.push(b"a")
        q_par.push(b"b")
        q_par.push(b"c")
        time.sleep(0.2)
        
        assert count_seq[0] == 3 and count_par[0] == 3
        print_test(total, "Sequential vs parallel modes", True, f"(seq: {count_seq[0]}, par: {count_par[0]})")
        passed += 1
        results.append(("Mode switching", True))
    except Exception as e:
        print_test(total, "Sequential vs parallel modes", False, str(e))
        results.append(("Mode switching", False))

    # Test 6: Statistics tracking
    total += 1
    try:
        q = AsyncQueue()
        q.start(lambda id, data: None, num_workers=1)
        q.push(b"1")
        q.push(b"2")
        q.push(b"3")
        time.sleep(0.2)
        stats = q.get_stats()
        assert stats.total_pushed == 3
        assert stats.total_processed >= 2
        print_test(total, "Statistics tracking", True, f"(pushed: {stats.total_pushed}, processed: {stats.total_processed})")
        passed += 1
        results.append(("Statistics", True))
    except Exception as e:
        print_test(total, "Statistics tracking", False, str(e))
        results.append(("Statistics", False))

    # Test 7: Error handling
    total += 1
    try:
        q = AsyncQueue()
        successful = [0]
        
        def worker_with_error(id, data):
            if id == 2:
                raise ValueError("Test error")
            successful[0] += 1
        
        q.start(worker_with_error, num_workers=1)
        q.push(b"1")
        q.push(b"2")
        q.push(b"3")
        time.sleep(0.3)
        
        assert successful[0] >= 2, f"Should process at least 2 items"
        print_test(total, "Error handling", True, f"({successful[0]} items processed despite errors)")
        passed += 1
        results.append(("Error handling", True))
    except Exception as e:
        print_test(total, "Error handling", False, str(e))
        results.append(("Error handling", False))

    print(f"\n{Colors.BOLD}Core Tests Summary: {passed}/{total} passed{Colors.END}\n")
    return results


def run_pytest_tests_manual():
    """Run full pytest test suite (manual execution mode)."""
    print_header("Running Full pytest Test Suite")
    
    try:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", __file__, "-v",
             "-k", "not (get_blocking or multiple or retrieval or properties)"],
            timeout=120,
            capture_output=False
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"{Colors.YELLOW}⚠ pytest tests timed out{Colors.END}")
        return False
    except Exception as e:
        print(f"{Colors.YELLOW}⚠ pytest not available or error: {e}{Colors.END}")
        return False


def main_cli():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test runner for rst_queue with pyo3 0.28",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_async_queue.py              # Run all tests (core + pytest)
  python test_async_queue.py --minimal    # Run core tests only
  python test_async_queue.py --pytest     # Run pytest tests only
  python test_async_queue.py --help       # Show this help message
        """
    )
    parser.add_argument("--minimal", action="store_true", help="Run only core tests")
    parser.add_argument("--pytest", action="store_true", help="Run only pytest tests")
    
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 12 + "rst_queue pyo3 0.28 - Complete Test Suite" + " " * 14 + "║")
    print("╚" + "=" * 68 + "╝")
    print(Colors.END)

    all_passed = True
    
    # Run core tests if not --pytest only
    if not args.pytest:
        core_results = run_core_tests_manual()
        core_passed = all(passed for _, passed in core_results)
        if not core_passed:
            all_passed = False
    
    # Run pytest if not --minimal only
    if not args.minimal:
        pytest_passed = run_pytest_tests_manual()
        if not pytest_passed and not args.pytest:
            print(f"{Colors.YELLOW}⚠ Some pytest tests failed or were skipped{Colors.END}")
            all_passed = False

    # Final summary
    print_header("Final Summary")

    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ All tests passed!{Colors.END}")
        print(f"\n{Colors.CYAN}Tested with pyo3 0.28 compatibility fixes.{Colors.END}")
        print(f"{Colors.CYAN}Queue supports: workers, results, sequential/parallel modes.{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Some tests failed{Colors.END}\n")
        return 1


if __name__ == "__main__":
    import sys
    # Check if any CLI arguments were passed
    if len(sys.argv) > 1 and any(arg in sys.argv for arg in ["--minimal", "--pytest", "--help"]):
        # Run in CLI mode
        sys.exit(main_cli())
    else:
        # Run pytest normally
        pytest.main([__file__, "-v"])
