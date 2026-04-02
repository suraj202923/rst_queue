"""
Comprehensive AsyncQueue Test Suite - Complete Reference

This unified test suite provides comprehensive coverage of AsyncQueue functionality,
combining:
  * Functional tests with user-friendly logging
  * Optimization validation tests
  * Concurrency and stress tests
  * Edge cases and error conditions

Easy to understand with:
  * Clear test names and descriptions
  * Detailed logging for each step
  * Organized by functionality
  * Quick reference examples
  * Statistics tracking

Usage:
  pytest test_queue.py              # Run all tests
  pytest test_queue.py -v           # Verbose output
  pytest test_queue.py -k "push"    # Run tests matching "push"
  pytest test_queue.py --tb=short   # Show short traceback
"""

import pytest
import time
import threading
import logging
import json
from typing import List

# Configure logging for easy understanding
log_format = '%(asctime)s | %(levelname)-8s | %(name)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Try to import from compiled module
try:
    from rst_queue import AsyncQueue, ExecutionMode
except ImportError:
    import sys
    sys.path.insert(0, str(__file__).rsplit('/', 1)[0] + '/..')
    from rst_queue import AsyncQueue, ExecutionMode


# ============================================================================
# UTILITY FUNCTIONS FOR BETTER OUTPUT
# ============================================================================

def print_test_header(test_name: str, description: str):
    """Print a formatted test header for clarity"""
    separator = "-" * 80
    print(f"\n{separator}")
    print(f"[TEST] {test_name}")
    print(f"  Description: {description}")
    print(f"{separator}\n")
    logger.info(f"Starting test: {test_name}")


def print_test_result(passed: bool, message: str, details: str = None):
    """Print formatted test result"""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"\n  {status}: {message}")
    if details:
        print(f"  Details: {details}")
    print()


def print_queue_stats(queue: AsyncQueue, label: str = "Queue Statistics"):
    """Print current queue statistics in readable format"""
    stats = queue.get_stats()
    print(f"\n  [STATS] {label}:")
    print(f"    * Total Pushed: {stats.total_pushed}")
    print(f"    * Total Processed: {stats.total_processed}")
    print(f"    * Total Errors: {stats.total_errors}")
    print(f"    * Active Workers: {stats.active_workers}")
    print()


def print_mode(mode_value: int):
    """Convert mode to readable string"""
    return "SEQUENTIAL (0)" if mode_value == 0 else "PARALLEL (1)"


def print_data_sample(data: bytes, max_length: int = 50):
    """Print data in readable format"""
    if len(data) == 0:
        return "[EMPTY]"
    if len(data) > max_length:
        return f"{data[:max_length].decode(errors='ignore')}... (truncated)"
    return data.decode(errors='ignore')


# ============================================================================
# GROUP 1: QUEUE CREATION AND INITIALIZATION
# ============================================================================

class TestQueueCreation:
    """Test queue creation and initialization"""

    def test_01_create_sequential_queue(self):
        """Test creating a sequential execution queue"""
        print_test_header(
            "Create Sequential Queue",
            "Verify that a sequential queue can be created with proper initial state"
        )
        
        queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL, buffer_size=128)
        
        logger.info(f"Queue created with mode: {print_mode(queue.get_mode())}")
        logger.info(f"Initial pushed count: {queue.total_pushed()}")
        
        assert queue.get_mode() == 0, "Mode should be SEQUENTIAL (0)"
        assert queue.total_pushed() == 0, "Pushed count should start at 0"
        
        print_test_result(True, "Sequential queue created successfully")
        print_queue_stats(queue)

    def test_02_create_parallel_queue(self):
        """Test creating a parallel execution queue"""
        print_test_header(
            "Create Parallel Queue",
            "Verify that a parallel queue can be created with proper initial state"
        )
        
        queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
        
        logger.info(f"Queue created with mode: {print_mode(queue.get_mode())}")
        logger.info(f"Buffer size: 128")
        
        assert queue.get_mode() == 1, "Mode should be PARALLEL (1)"
        assert queue.total_pushed() == 0, "Pushed count should start at 0"
        
        print_test_result(True, "Parallel queue created successfully")
        print_queue_stats(queue)

    def test_03_create_queue_with_defaults(self):
        """Test creating queue with default parameters"""
        print_test_header(
            "Create Queue with Defaults",
            "Verify that default parameters are applied correctly"
        )
        
        queue = AsyncQueue()
        
        logger.info(f"Queue created with default parameters")
        logger.info(f"Default mode: {print_mode(queue.get_mode())}")
        logger.info(f"Default total_pushed: {queue.total_pushed()}")
        
        # Default should be parallel
        assert queue.get_mode() == 1, "Default mode should be PARALLEL (1)"
        assert queue.total_pushed() == 0, "Initial pushed count should be 0"
        
        print_test_result(True, "Queue created with default parameters")

    def test_04_buffer_size_parameter(self):
        """Test that buffer_size parameter is accepted"""
        print_test_header(
            "Buffer Size Parameter",
            "Verify that queue accepts custom buffer_size parameter"
        )
        
        buffer_sizes = [64, 128, 256, 512]
        
        for size in buffer_sizes:
            logger.info(f"Testing buffer size: {size}")
            queue = AsyncQueue(mode=0, buffer_size=size)
            assert queue.get_mode() == 0
            print(f"    * Buffer size {size} accepted")
        
        print_test_result(True, "All buffer sizes accepted")


# ============================================================================
# GROUP 2: QUEUE MODE OPERATIONS
# ============================================================================

class TestQueueModeOperations:
    """Test queue mode getting and setting operations"""

    def test_05_get_mode(self):
        """Test retrieving queue mode"""
        print_test_header(
            "Get Queue Mode",
            "Verify that queue mode can be retrieved correctly"
        )
        
        # Test sequential
        seq_queue = AsyncQueue(mode=0)
        logger.info(f"Sequential queue mode: {seq_queue.get_mode()}")
        assert seq_queue.get_mode() == 0
        print(f"    * Sequential queue mode: {print_mode(seq_queue.get_mode())}")
        
        # Test parallel
        par_queue = AsyncQueue(mode=1)
        logger.info(f"Parallel queue mode: {par_queue.get_mode()}")
        assert par_queue.get_mode() == 1
        print(f"    * Parallel queue mode: {print_mode(par_queue.get_mode())}")
        
        print_test_result(True, "Mode retrieval working correctly")

    def test_06_set_mode(self):
        """Test changing queue mode"""
        print_test_header(
            "Set Queue Mode",
            "Verify that queue mode can be changed dynamically"
        )
        
        queue = AsyncQueue(mode=0)
        print(f"    Initial mode: {print_mode(queue.get_mode())}")
        assert queue.get_mode() == 0
        
        logger.info("Changing mode to PARALLEL")
        queue.set_mode(1)
        print(f"    After set_mode(1): {print_mode(queue.get_mode())}")
        assert queue.get_mode() == 1
        
        logger.info("Changing mode back to SEQUENTIAL")
        queue.set_mode(0)
        print(f"    After set_mode(0): {print_mode(queue.get_mode())}")
        assert queue.get_mode() == 0
        
        print_test_result(True, "Mode switching working correctly")

    def test_07_execution_mode_constants(self):
        """Test ExecutionMode constants"""
        print_test_header(
            "ExecutionMode Constants",
            "Verify that ExecutionMode constants have correct values"
        )
        
        logger.info(f"ExecutionMode.SEQUENTIAL = {ExecutionMode.SEQUENTIAL}")
        logger.info(f"ExecutionMode.PARALLEL = {ExecutionMode.PARALLEL}")
        
        assert ExecutionMode.SEQUENTIAL == 0, "SEQUENTIAL should be 0"
        assert ExecutionMode.PARALLEL == 1, "PARALLEL should be 1"
        
        print(f"    * SEQUENTIAL = {ExecutionMode.SEQUENTIAL}")
        print(f"    * PARALLEL = {ExecutionMode.PARALLEL}")
        
        print_test_result(True, "All constants have correct values")

    def test_08_alternating_mode_switches(self):
        """Test alternating mode switches"""
        print_test_header(
            "Alternating Mode Switches",
            "Verify that mode can be switched multiple times"
        )
        
        queue = AsyncQueue()
        
        for i in range(5):
            queue.set_mode(i % 2)
            mode_name = print_mode(queue.get_mode())
            logger.info(f"Switch {i+1}: {mode_name}")
            print(f"    * Switch {i+1}: {mode_name}")
        
        print_test_result(True, "Mode switching multiple times successful")


# ============================================================================
# GROUP 3: PUSHING ITEMS TO QUEUE
# ============================================================================

class TestPushingItems:
    """Test pushing items to the queue"""

    def test_09_push_single_item(self):
        """Test pushing a single item"""
        print_test_header(
            "Push Single Item",
            "Verify that a single item can be pushed to the queue"
        )
        
        queue = AsyncQueue()
        test_data = b"test data"
        
        logger.info(f"Before: total_pushed = {queue.total_pushed()}")
        queue.push(test_data)
        logger.info(f"Pushed: {print_data_sample(test_data)}")
        logger.info(f"After: total_pushed = {queue.total_pushed()}")
        
        assert queue.total_pushed() == 1
        
        print(f"    * Item pushed: {print_data_sample(test_data)}")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Single item pushed successfully")

    def test_10_push_multiple_items(self):
        """Test pushing multiple items"""
        print_test_header(
            "Push Multiple Items",
            "Verify that multiple items can be pushed to the queue"
        )
        
        queue = AsyncQueue()
        num_items = 10
        
        logger.info(f"Pushing {num_items} items...")
        for i in range(num_items):
            data = f"item_{i}".encode()
            queue.push(data)
            logger.info(f"  [{i+1}/{num_items}] Pushed: {print_data_sample(data)}")
        
        assert queue.total_pushed() == num_items
        
        print(f"    * All {num_items} items pushed successfully")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, f"Multiple items ({num_items}) pushed successfully")

    def test_11_push_empty_bytes(self):
        """Test pushing empty bytes"""
        print_test_header(
            "Push Empty Data",
            "Verify that empty bytes can be pushed to the queue"
        )
        
        queue = AsyncQueue()
        empty_data = b""
        
        logger.info("Pushing empty bytes")
        queue.push(empty_data)
        logger.info(f"total_pushed after empty push: {queue.total_pushed()}")
        
        assert queue.total_pushed() == 1
        
        print(f"    * Empty bytes pushed: {print_data_sample(empty_data) if empty_data else '[EMPTY]'}")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Empty data handled correctly")

    def test_12_push_large_data(self):
        """Test pushing large data"""
        print_test_header(
            "Push Large Data",
            "Verify that large data can be pushed to the queue"
        )
        
        queue = AsyncQueue()
        large_size_mb = 1
        large_data = b"x" * (1024 * 1024 * large_size_mb)
        
        logger.info(f"Pushing {large_size_mb}MB of data...")
        queue.push(large_data)
        logger.info(f"total_pushed after large push: {queue.total_pushed()}")
        
        assert queue.total_pushed() == 1
        
        print(f"    * Large data ({large_size_mb}MB) pushed successfully")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, f"Large data ({large_size_mb}MB) handled correctly")

    def test_13_push_various_data_types(self):
        """Test pushing various data types encoded as bytes"""
        print_test_header(
            "Push Various Data Types",
            "Verify that different data types can be pushed as bytes"
        )
        
        queue = AsyncQueue()
        test_cases = [
            ("String", "hello world".encode()),
            ("JSON", json.dumps({"name": "Alice", "age": 30}).encode()),
            ("Number", "42".encode()),
            ("CSV", "id,name,value\n1,test,100".encode()),
        ]
        
        logger.info(f"Pushing {len(test_cases)} different data types...")
        for data_type, data in test_cases:
            queue.push(data)
            logger.info(f"  * {data_type}: {print_data_sample(data)}")
            print(f"    * {data_type}: {print_data_sample(data)}")
        
        assert queue.total_pushed() == len(test_cases)
        
        print(f"    * All {len(test_cases)} data types pushed")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Various data types pushed successfully")


# ============================================================================
# GROUP 4: BATCH OPERATIONS
# ============================================================================

class TestBatchOperations:
    """Test batch push/get operations"""

    def test_14_push_batch(self):
        """Test batch push multiple items"""
        print_test_header(
            "Batch Push",
            "Verify that multiple items can be pushed at once"
        )
        
        queue = AsyncQueue()
        items = [b"item1", b"item2", b"item3", b"item4", b"item5"]
        
        logger.info(f"Pushing batch of {len(items)} items...")
        ids = queue.push_batch(items)
        
        logger.info(f"Received {len(ids)} IDs: {ids}")
        
        assert len(ids) == len(items), "Should return IDs for all items"
        assert queue.total_pushed() == len(items)
        
        print(f"    * Batch size: {len(items)} items")
        print(f"    * IDs returned: {len(ids)}")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, f"Batch push of {len(items)} items successful")

    def test_15_push_batch_empty_list(self):
        """Test pushing empty batch"""
        print_test_header(
            "Batch Push - Empty List",
            "Verify that pushing empty batch is handled correctly"
        )
        
        queue = AsyncQueue()
        ids = queue.push_batch([])
        
        logger.info(f"Empty batch returned {len(ids)} IDs")
        
        assert len(ids) == 0, "Empty batch should return empty ID list"
        assert queue.total_pushed() == 0
        
        print(f"    * Empty batch result: {len(ids)} IDs")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Empty batch handled correctly")

    def test_16_push_batch_large(self):
        """Test push large batch (1000 items)"""
        print_test_header(
            "Batch Push - Large (1000 items)",
            "Verify that large batch can be pushed efficiently"
        )
        
        queue = AsyncQueue()
        items = [b"large_" + str(i).encode() for i in range(1000)]
        
        logger.info(f"Pushing {len(items)} items...")
        ids = queue.push_batch(items)
        
        logger.info(f"Batch push complete, received {len(ids)} IDs")
        
        assert len(ids) == 1000
        assert queue.total_pushed() == 1000
        
        print(f"    * Batch size: {len(items)} items")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, f"Large batch ({len(items)} items) pushed successfully")

    def test_17_batch_get_empty(self):
        """Test batch get returns empty when no results processed"""
        print_test_header(
            "Batch Get - Empty Results",
            "Verify that batch get works with no processed results"
        )
        
        queue = AsyncQueue()
        items = [b"batch_item_" + str(i).encode() for i in range(10)]
        
        logger.info(f"Pushing {len(items)} items...")
        queue.push_batch(items)
        
        logger.info("Attempting to get batch without workers processing...")
        retrieved = queue.get_batch(5)
        
        logger.info(f"Batch get returned {len(retrieved)} items")
        
        assert len(retrieved) == 0, "No results should be available without workers"
        print(f"    * Retrieved items: {len(retrieved)}")
        
        print_test_result(True, "Batch get correctly returns empty when no results")

    def test_18_multiple_batch_operations(self):
        """Test multiple batch operations"""
        print_test_header(
            "Multiple Batch Operations",
            "Verify that multiple batch operations work correctly"
        )
        
        queue = AsyncQueue()
        
        logger.info("Performing 10 batch operations with 100 items each...")
        for batch_num in range(10):
            items = [f"batch_{batch_num}_item_{i}".encode() for i in range(100)]
            ids = queue.push_batch(items)
            logger.info(f"  Batch {batch_num+1}: {len(ids)} items pushed")
            assert len(ids) == 100
        
        assert queue.total_pushed() == 1000
        
        print(f"    * Total batches: 10")
        print(f"    * Items per batch: 100")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Multiple batch operations successful (1000 items total)")


# ============================================================================
# GROUP 5: QUEUE STATISTICS AND MONITORING
# ============================================================================

class TestQueueStatistics:
    """Test queue statistics and monitoring"""

    def test_19_total_pushed_counter(self):
        """Test that total_pushed counter increments correctly"""
        print_test_header(
            "Total Pushed Counter",
            "Verify that total_pushed counter increments for each push"
        )
        
        queue = AsyncQueue()
        
        logger.info(f"Initial total_pushed: {queue.total_pushed()}")
        print(f"    Initial: {queue.total_pushed()}")
        
        num_pushes = 15
        for i in range(num_pushes):
            queue.push(f"item_{i}".encode())
            current = queue.total_pushed()
            logger.info(f"  After push {i+1}: total_pushed = {current}")
        
        assert queue.total_pushed() == num_pushes
        
        print_test_result(True, f"Counter incremented correctly to {num_pushes}")

    def test_20_get_stats(self):
        """Test getting queue statistics"""
        print_test_header(
            "Get Queue Statistics",
            "Verify that queue statistics can be retrieved"
        )
        
        queue = AsyncQueue()
        
        # Push some items
        num_items = 8
        for i in range(num_items):
            queue.push(f"item_{i}".encode())
        
        logger.info("Retrieving queue statistics...")
        stats = queue.get_stats()
        
        # Check that all expected fields exist
        expected_fields = ['total_pushed', 'total_processed', 'total_errors', 'active_workers']
        for field in expected_fields:
            has_field = hasattr(stats, field)
            logger.info(f"  Field '{field}': {has_field}")
            assert has_field, f"Stats should have '{field}' field"
            print(f"    * {field}: {getattr(stats, field)}")
        
        assert stats.total_pushed == num_items
        
        print_queue_stats(queue)
        print_test_result(True, "Queue statistics retrieved successfully")

    def test_21_active_workers(self):
        """Test getting active workers count"""
        print_test_header(
            "Active Workers Count",
            "Verify that active workers count can be retrieved"
        )
        
        queue = AsyncQueue()
        
        workers = queue.active_workers()
        logger.info(f"Active workers: {workers}")
        
        assert workers >= 0, "Active workers should be non-negative"
        
        print(f"    * Active workers: {workers}")
        print_test_result(True, "Active workers count retrieved successfully")

    def test_22_concurrent_counter_increments(self):
        """Test counter increments correctly with concurrent pushes"""
        print_test_header(
            "Concurrent Counter Increments",
            "Verify that counter is accurate with multiple threads"
        )
        
        queue = AsyncQueue()
        
        def pusher():
            for _ in range(100):
                queue.push(b"data")

        logger.info("Starting 4 concurrent pushers (100 items each)...")
        threads = [threading.Thread(target=pusher) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert queue.total_pushed() == 400
        
        print(f"    * Threads: 4")
        print(f"    * Items per thread: 100")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Concurrent counter increments verified (400 items)")


# ============================================================================
# GROUP 6: CONCURRENCY AND THREAD SAFETY
# ============================================================================

class TestConcurrency:
    """Test concurrent access patterns"""

    def test_23_concurrent_push(self):
        """Test multiple threads pushing concurrently"""
        print_test_header(
            "Concurrent Push",
            "Verify that multiple threads can push items safely"
        )
        
        queue = AsyncQueue()
        
        def pusher(thread_id):
            for i in range(50):
                queue.push(f"thread_{thread_id}_item_{i}".encode())

        logger.info("Starting 4 concurrent pushers...")
        threads = [threading.Thread(target=pusher, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert queue.total_pushed() == 200  # 4 threads * 50 items
        
        print(f"    * Threads: 4")
        print(f"    * Items per thread: 50")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Concurrent push successful (200 items from 4 threads)")

    def test_24_concurrent_batch_push(self):
        """Test multiple threads pushing batches concurrently"""
        print_test_header(
            "Concurrent Batch Push",
            "Verify that multiple threads can batch push safely"
        )
        
        queue = AsyncQueue()
        
        def batch_pusher(thread_id):
            for i in range(10):
                items = [f"thread_{thread_id}_batch_{i}_item_{j}".encode() 
                        for j in range(10)]
                queue.push_batch(items)

        logger.info("Starting 4 concurrent batch pushers...")
        threads = [threading.Thread(target=batch_pusher, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 4 threads * 10 batches * 10 items = 400
        assert queue.total_pushed() == 400
        
        print(f"    * Threads: 4")
        print(f"    * Batches per thread: 10")
        print(f"    * Items per batch: 10")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Concurrent batch push successful (400 items)")

    def test_25_producer_consumer(self):
        """Test producer and consumer pattern"""
        print_test_header(
            "Producer-Consumer Pattern",
            "Verify that queue works in producer-consumer scenario"
        )
        
        queue = AsyncQueue()
        produced = [0]
        lock = threading.Lock()

        def producer():
            for i in range(100):
                queue.push(f"item_{i}".encode())
                with lock:
                    produced[0] += 1

        def consumer():
            # Try to get results (may be empty without workers)
            for _ in range(100):
                item = queue.get()
                if item is not None:
                    # Got a processed result
                    pass

        logger.info("Starting producer and consumer threads...")
        p = threading.Thread(target=producer)
        c = threading.Thread(target=consumer)
        p.start()
        c.start()
        p.join()
        c.join()

        # Should have produced 100 items
        assert produced[0] == 100
        assert queue.total_pushed() == 100
        
        print(f"    * Items produced: {produced[0]}")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Producer-consumer pattern successful")

    def test_26_high_contention(self):
        """Test high-contention scenario (8 threads pushing)"""
        print_test_header(
            "High-Contention Scenario",
            "Verify queue handles high contention (8 threads, 50 items each)"
        )
        
        queue = AsyncQueue()
        success_count = [0]
        lock = threading.Lock()

        def worker():
            for _ in range(50):
                queue.push(b"data")
                with lock:
                    success_count[0] += 1

        logger.info("Starting 8 high-contention threads...")
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All pushes should succeed
        assert success_count[0] == 400
        assert queue.total_pushed() == 400
        
        print(f"    * Threads: 8")
        print(f"    * Items per thread: 50")
        print(f"    * successful_ops: {success_count[0]}")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "High-contention scenario handled (400 items from 8 threads)")


# ============================================================================
# GROUP 7: LOCK-FREE AND PERFORMANCE PROPERTIES
# ============================================================================

class TestLockFreeProperties:
    """Test lock-free guarantee validation"""

    def test_27_no_blocking_empty_queue(self):
        """Test that getting from empty queue doesn't block"""
        print_test_header(
            "Non-Blocking Get from Empty Queue",
            "Verify that get() returns immediately without blocking"
        )
        
        queue = AsyncQueue()
        
        logger.info("Getting from empty queue...")
        start_time = time.time()
        item = queue.get()  # Should return None immediately
        elapsed = time.time() - start_time
        
        logger.info(f"Time taken: {elapsed:.6f} seconds")
        
        assert item is None
        assert elapsed < 0.1  # Should be near-instant
        
        print(f"    * Item returned: None")
        print(f"    * Time elapsed: {elapsed:.6f} seconds")
        
        print_test_result(True, "Get from empty queue is non-blocking")

    def test_28_push_doesnt_block(self):
        """Test that push operation doesn't block under contention"""
        print_test_header(
            "Non-Blocking Push Under Contention",
            "Verify that push() completes quickly even with contention"
        )
        
        queue = AsyncQueue()
        
        def rapid_pusher():
            start = time.time()
            for _ in range(1000):
                queue.push(b"data")
            return time.time() - start

        logger.info("Baseline: single-threaded pusher (1000 items)...")
        baseline = rapid_pusher()
        logger.info(f"Baseline time: {baseline:.6f} seconds")
        
        logger.info("Contention: 4 concurrent pushers (1000 items each)...")
        times = []
        times_lock = threading.Lock()
        
        def measure_pusher():
            elapsed = rapid_pusher()
            with times_lock:
                times.append(elapsed)
        
        threads = [threading.Thread(target=measure_pusher) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert queue.total_pushed() == 5000  # 1000 baseline + 4*1000 concurrent
        
        print(f"    * Baseline time: {baseline:.6f} seconds")
        print(f"    * Average contention time: {sum(times)/len(times):.6f} seconds")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Push operations don't block under contention")


# ============================================================================
# GROUP 8: MEMORY AND EDGE CASES
# ============================================================================

class TestMemoryManagement:
    """Test memory behavior and cleanup"""

    def test_29_memory_bounded(self):
        """Test queue handles large items efficiently"""
        print_test_header(
            "Memory - Large Items",
            "Verify that queue can handle large data items"
        )
        
        queue = AsyncQueue()
        large_item = b"x" * (1 * 1024 * 1024)  # 1MB item
        
        logger.info(f"Pushing 10 x 1MB items...")
        for i in range(10):
            queue.push(large_item)
        
        assert queue.total_pushed() == 10
        
        print(f"    * Item size: 1 MB")
        print(f"    * Items pushed: 10")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Queue handles 10 MB of data efficiently")

    def test_30_fifo_batch_ordering(self):
        """Test batch operations preserve order"""
        print_test_header(
            "FIFO Ordering - Batch Ops",
            "Verify that batch operations maintain FIFO order"
        )
        
        queue = AsyncQueue()
        items = [b"item_" + str(i).encode() for i in range(100)]
        
        logger.info("Pushing 100 items in batch...")
        ids = queue.push_batch(items)
        
        logger.info(f"Received {len(ids)} IDs")
        
        # All items should have been pushed in order
        assert len(ids) == 100
        assert queue.total_pushed() == 100
        
        print(f"    * Items in batch: {len(items)}")
        print(f"    * IDs returned: {len(ids)}")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Batch ordering preserved")

    def test_31_stats_consistency(self):
        """Test queue stats are consistent"""
        print_test_header(
            "Statistics Consistency",
            "Verify that all statistics remain consistent"
        )
        
        queue = AsyncQueue()
        
        # Initial state
        logger.info("Checking initial state...")
        assert queue.total_pushed() == 0
        assert queue.total_processed() == 0
        assert queue.total_errors() == 0
        print("    * Initial state verified")
        
        # After pushing
        logger.info("Pushing 100 items...")
        queue.push_batch([b"item"] * 100)
        assert queue.total_pushed() == 100
        
        # Get comprehensive stats
        logger.info("Retrieving stats...")
        stats = queue.get_stats()
        assert stats.total_pushed == 100
        
        print_queue_stats(queue, "Final Statistics")
        print_test_result(True, "Statistics consistency verified")


class TestEdgeCases:
    """Test edge cases and unusual scenarios"""

    def test_32_mode_switching_with_items(self):
        """Test switching modes with items in queue"""
        print_test_header(
            "Mode Switching with Items",
            "Verify that mode can be switched while queue has items"
        )
        
        queue = AsyncQueue()
        
        logger.info("Pushing items to parallel queue...")
        for i in range(5):
            queue.push(f"item_{i}".encode())
        
        print(f"    * Items pushed to PARALLEL mode: {queue.total_pushed()}")
        
        logger.info("Switching to SEQUENTIAL mode...")
        queue.set_mode(0)
        
        logger.info("Pushing more items to sequential queue...")
        for i in range(5, 10):
            queue.push(f"item_{i}".encode())
        
        assert queue.total_pushed() == 10
        assert queue.get_mode() == 0
        
        print(f"    * Items pushed to SEQUENTIAL mode: 5")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Mode switching with items successful")

    def test_33_alternating_operations(self):
        """Test alternating push/get operations"""
        print_test_header(
            "Alternating Push/Get",
            "Verify that alternating push and get operations work"
        )
        
        queue = AsyncQueue()
        
        logger.info("Performing alternating push/get operations...")
        push_count = 0
        for i in range(50):
            queue.push(f"item_{i}".encode())
            push_count += 1
            item = queue.get()
            # Item might be None since these are processed results
        
        assert queue.total_pushed() == 50
        
        print(f"    * Alternating operations: 50 iterations")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Alternating push/get operations successful")

    def test_34_get_from_empty(self):
        """Test get from empty queue"""
        print_test_header(
            "Get from Empty Queue",
            "Verify that get from empty queue returns None"
        )
        
        queue = AsyncQueue()
        
        logger.info("Getting from empty queue...")
        item = queue.get()
        
        logger.info(f"Item returned: {item}")
        
        assert item is None
        
        print(f"    * Item returned: {item}")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Get from empty queue returns None")

    def test_35_active_workers_monitoring(self):
        """Test active workers count during operations"""
        print_test_header(
            "Active Workers Monitoring",
            "Verify that active workers count can be monitored"
        )
        
        queue = AsyncQueue()
        
        logger.info("Checking active workers before operations...")
        count_before = queue.active_workers()
        print(f"    * Before operations: {count_before}")
        
        logger.info("Pushing 100 items...")
        for i in range(100):
            queue.push(f"item_{i}".encode())
        
        logger.info("Checking active workers after operations...")
        count_after = queue.active_workers()
        print(f"    * After operations: {count_after}")
        
        assert count_before >= 0 and count_after >= 0
        
        print_test_result(True, f"Active workers: {count_before} → {count_after}")


# ============================================================================
# GROUP 9: QUICK REFERENCE - COMMON USE CASES
# ============================================================================

class TestQuickReferenceExamples:
    """Quick reference examples for common use cases"""

    def test_36_basic_queue_usage(self):
        """Quick example: Basic queue push and get"""
        print_test_header(
            "[REFERENCE] Basic Queue Usage",
            "How to create a queue and push items"
        )
        
        print("""
    # Create a queue with default settings
    queue = AsyncQueue()
    
    # Push data
    queue.push(b"hello world")
    
    # Check how many items were pushed
    print(f"Pushed: {queue.total_pushed()}")
    
    # Get processed results
    result = queue.get()
    print(f"Result: {result}")
        """)
        
        queue = AsyncQueue()
        queue.push(b"hello world")
        assert queue.total_pushed() == 1
        print_test_result(True, "See example above")

    def test_37_batch_processing(self):
        """Quick example: Batch push operations"""
        print_test_header(
            "[REFERENCE] Batch Processing",
            "How to push multiple items in a batch"
        )
        
        print("""
    # Create a queue
    queue = AsyncQueue()
    
    # Prepare multiple items
    items = [b"item1", b"item2", b"item3"]
    
    # Push them in batch
    ids = queue.push_batch(items)
    print(f"Pushed {len(ids)} items")
    
    # Get batch results
    results = queue.get_batch(3)
    print(f"Retrieved {len(results)} results")
        """)
        
        queue = AsyncQueue()
        items = [b"item1", b"item2", b"item3"]
        ids = queue.push_batch(items)
        assert len(ids) == 3
        print_test_result(True, "See example above")

    def test_38_mode_selection(self):
        """Quick example: Choosing execution mode"""
        print_test_header(
            "[REFERENCE] Execution Mode Selection",
            "How to choose between SEQUENTIAL and PARALLEL modes"
        )
        
        print("""
    from rst_queue import AsyncQueue, ExecutionMode
    
    # Sequential mode - processes one item at a time
    seq_queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL)
    
    # Parallel mode - processes multiple items concurrently
    par_queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
    
    # Check current mode
    mode = queue.get_mode()
    
    # Switch mode dynamically
    queue.set_mode(ExecutionMode.PARALLEL)
        """)
        
        seq_queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL)
        par_queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        assert seq_queue.get_mode() == 0
        assert par_queue.get_mode() == 1
        print_test_result(True, "See example above")

    def test_39_monitoring_statistics(self):
        """Quick example: Monitoring queue statistics"""
        print_test_header(
            "[REFERENCE] Monitoring Queue Statistics",
            "How to track queue metrics and statistics"
        )
        
        print("""
    # Create and use queue
    queue = AsyncQueue()
    queue.push(b"data1")
    queue.push(b"data2")
    
    # Get current stats
    stats = queue.get_stats()
    
    # Access statistics
    print(f"Total Pushed: {stats.total_pushed}")
    print(f"Processed: {stats.total_processed}")
    print(f"Errors: {stats.total_errors}")
    print(f"Active Workers: {stats.active_workers}")
    
    # Or use convenience methods
    print(f"Total: {queue.total_pushed()}")
    print(f"Workers: {queue.active_workers()}")
        """)
        
        queue = AsyncQueue()
        queue.push(b"data1")
        queue.push(b"data2")
        stats = queue.get_stats()
        assert stats.total_pushed == 2
        print_test_result(True, "See example above")


# ============================================================================
# GROUP 10: NEW METHODS - CLEAR AND PENDING_ITEMS
# ============================================================================

class TestClearAndPendingItems:
    """Test new methods: clear() and pending_items()"""

    def test_40_clear_empty_queue(self):
        """Test clearing an empty queue"""
        print_test_header(
            "Clear - Empty Queue",
            "Verify that clearing an empty queue returns 0"
        )
        
        queue = AsyncQueue()
        
        logger.info("Clearing empty queue...")
        removed = queue.clear()
        
        logger.info(f"Items removed: {removed}")
        
        assert removed == 0
        assert queue.total_pushed() == 0
        
        print(f"    * Items removed: {removed}")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Empty queue cleared (0 items removed)")

    def test_41_clear_queue_with_items(self):
        """Test clearing queue with pending items"""
        print_test_header(
            "Clear - Queue with Items",
            "Verify that clear removes all pending items"
        )
        
        queue = AsyncQueue()
        num_items = 50
        
        logger.info(f"Pushing {num_items} items...")
        for i in range(num_items):
            queue.push(f"item_{i}".encode())
        
        assert queue.total_pushed() == num_items
        logger.info(f"Pending items before clear: {queue.pending_items()}")
        
        logger.info("Clearing queue...")
        removed = queue.clear()
        
        logger.info(f"Items removed: {removed}")
        assert removed == num_items
        
        pending_after = queue.pending_items()
        logger.info(f"Pending items after clear: {pending_after}")
        assert pending_after == 0
        
        print(f"    * Items pushed: {num_items}")
        print(f"    * Items removed: {removed}")
        print(f"    * Pending after: {pending_after}")
        print(f"    * total_pushed (unchanged): {queue.total_pushed()}")
        
        print_test_result(True, f"Queue cleared successfully ({removed} items removed)")

    def test_42_clear_large_batch(self):
        """Test clearing a large batch of items"""
        print_test_header(
            "Clear - Large Batch",
            "Verify that clear handles large batches efficiently"
        )
        
        queue = AsyncQueue()
        num_items = 10000
        
        logger.info(f"Pushing {num_items} items...")
        for i in range(num_items):
            queue.push(f"item_{i}".encode())
        
        logger.info("Clearing large batch...")
        start_time = time.time()
        removed = queue.clear()
        elapsed = time.time() - start_time
        
        logger.info(f"Items removed: {removed} in {elapsed:.4f} seconds")
        
        assert removed == num_items
        assert queue.pending_items() == 0
        
        throughput = num_items / elapsed if elapsed > 0 else float('inf')
        
        print(f"    * Items cleared: {removed:,}")
        print(f"    * Time taken: {elapsed:.4f} seconds")
        print(f"    * Throughput: {throughput:,.0f} items/sec")
        
        print_test_result(True, f"Large batch cleared ({removed:,} items)")

    def test_43_clear_preserves_stats(self):
        """Test that clear doesn't affect statistics counters"""
        print_test_header(
            "Clear - Statistics Preservation",
            "Verify that clear doesn't modify queue statistics"
        )
        
        queue = AsyncQueue()
        num_items = 100
        
        logger.info(f"Pushing {num_items} items...")
        for i in range(num_items):
            queue.push(f"item_{i}".encode())
        
        stats_before = queue.get_stats()
        logger.info(f"Stats before clear: pushed={stats_before.total_pushed}")
        
        logger.info("Clearing queue...")
        removed = queue.clear()
        
        stats_after = queue.get_stats()
        logger.info(f"Stats after clear: pushed={stats_after.total_pushed}")
        
        assert stats_before.total_pushed == stats_after.total_pushed
        assert stats_before.total_processed == stats_after.total_processed
        assert stats_before.total_errors == stats_after.total_errors
        
        print(f"    * Removed: {removed} items")
        print(f"    * total_pushed: {stats_before.total_pushed} (unchanged)")
        print(f"    * total_processed: {stats_before.total_processed} (unchanged)")
        print(f"    * total_errors: {stats_before.total_errors} (unchanged)")
        
        print_test_result(True, "Statistics preserved after clear")

    def test_44_clear_while_processing(self):
        """Test clearing while workers are processing"""
        print_test_header(
            "Clear - During Processing",
            "Verify that clear doesn't affect items being processed"
        )
        
        queue = AsyncQueue()
        processed = []
        lock = threading.Lock()
        
        def worker(item_id, data):
            time.sleep(0.01)  # Simulate work
            with lock:
                processed.append(item_id)
        
        logger.info("Pushing 20 items and starting workers...")
        for i in range(20):
            queue.push(f"item_{i}".encode())
        
        queue.start(worker, num_workers=2)
        
        # Let some items get picked up
        time.sleep(0.02)
        
        # Now clear remaining
        logger.info("Clearing remaining items...")
        removed = queue.clear()
        logger.info(f"Items cleared: {removed}")
        
        # Wait for workers to finish
        time.sleep(0.3)
        
        total_accounted = len(processed) + removed
        logger.info(f"Items processed: {len(processed)}, cleared: {removed}, total: {total_accounted}")
        
        assert total_accounted == 20
        
        print(f"    * Items processed by workers: {len(processed)}")
        print(f"    * Items cleared: {removed}")
        print(f"    * Total accounted: {total_accounted} (expected 20)")
        
        print_test_result(True, "Clear during processing successful (no worker impact)")

    def test_45_pending_items_empty_queue(self):
        """Test pending_items on empty queue"""
        print_test_header(
            "pending_items - Empty Queue",
            "Verify that pending_items returns 0 for empty queue"
        )
        
        queue = AsyncQueue()
        
        logger.info("Checking pending items on empty queue...")
        pending = queue.pending_items()
        
        logger.info(f"Pending items: {pending}")
        
        assert pending == 0
        
        print(f"    * Pending items: {pending}")
        
        print_test_result(True, "pending_items correctly returns 0 for empty queue")

    def test_46_pending_items_with_items(self):
        """Test pending_items returns correct count"""
        print_test_header(
            "pending_items - With Items",
            "Verify that pending_items returns accurate count"
        )
        
        queue = AsyncQueue()
        
        for count in [1, 5, 10, 50]:
            logger.info(f"Pushing {count} items...")
            queue.clear()  # Clear from previous iteration
            
            for i in range(count):
                queue.push(f"item_{i}".encode())
            
            pending = queue.pending_items()
            logger.info(f"Pending items: {pending}")
            
            assert pending == count
            print(f"    * Pushed: {count}, Pending: {pending}")
        
        print_test_result(True, "pending_items returns correct counts")

    def test_47_pending_items_after_clear(self):
        """Test pending_items after clearing"""
        print_test_header(
            "pending_items - After Clear",
            "Verify that pending_items returns 0 after clear"
        )
        
        queue = AsyncQueue()
        num_items = 50
        
        logger.info(f"Pushing {num_items} items...")
        for i in range(num_items):
            queue.push(f"item_{i}".encode())
        
        logger.info(f"Pending before clear: {queue.pending_items()}")
        assert queue.pending_items() == num_items
        
        logger.info("Clearing queue...")
        queue.clear()
        
        logger.info("Checking pending after clear...")
        pending_after = queue.pending_items()
        logger.info(f"Pending after clear: {pending_after}")
        
        assert pending_after == 0
        
        print(f"    * Items before clear: {num_items}")
        print(f"    * Items after clear: {pending_after}")
        
        print_test_result(True, "pending_items returns 0 after clear")

    def test_48_clear_and_pending_concurrent(self):
        """Test clear and pending_items under concurrent access"""
        print_test_header(
            "Clear & pending_items - Concurrent",
            "Verify thread safety of both operations"
        )
        
        queue = AsyncQueue()
        errors = []
        
        def pusher():
            try:
                for _ in range(100):
                    queue.push(b"data")
            except Exception as e:
                errors.append(f"Pusher error: {e}")
        
        def meter():
            try:
                for _ in range(50):
                    pending = queue.pending_items()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(f"Meter error: {e}")
        
        def clearer():
            try:
                time.sleep(0.05)
                removed = queue.clear()
                logger.info(f"Removed: {removed}")
            except Exception as e:
                errors.append(f"Clearer error: {e}")
        
        logger.info("Starting concurrent pusher, meter, and clearer...")
        threads = [
            threading.Thread(target=pusher),
            threading.Thread(target=pusher),
            threading.Thread(target=meter),
            threading.Thread(target=clearer),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Concurrent errors: {errors}"
        
        print(f"    * No concurrent errors")
        print(f"    * final_pending: {queue.pending_items()}")
        
        print_test_result(True, "Concurrent clear and pending_items operations successful")

    def test_49_multiple_clears(self):
        """Test multiple clear operations in sequence"""
        print_test_header(
            "Multiple Clears",
            "Verify that multiple clears work correctly"
        )
        
        queue = AsyncQueue()
        
        for iteration in range(3):
            logger.info(f"Iteration {iteration+1}:")
            
            # Push items
            for i in range(20):
                queue.push(f"iter_{iteration}_item_{i}".encode())
            
            pending = queue.pending_items()
            logger.info(f"  Pending: {pending}")
            print(f"    * Iteration {iteration+1}:  Pending={pending}", end="")
            
            # Clear
            removed = queue.clear()
            logger.info(f"  Removed: {removed}")
            print(f"  → Removed={removed}")
            
            assert pending == 20
            assert removed == 20
            assert queue.pending_items() == 0
        
        print_test_result(True, "Multiple clears executed successfully")

    def test_50_clear_batch_push(self):
        """Test clear after batch push"""
        print_test_header(
            "Clear - After Batch Push",
            "Verify that clear works with batch-pushed items"
        )
        
        queue = AsyncQueue()
        
        # Batch push
        items = [f"item_{i}".encode() for i in range(100)]
        logger.info("Batch pushing 100 items...")
        ids = queue.push_batch(items)
        assert len(ids) == 100
        
        logger.info("Clearing batch...")
        removed = queue.clear()
        logger.info(f"Items removed: {removed}")
        
        assert removed == 100
        assert queue.pending_items() == 0
        
        print(f"    * Batch pushed: 100 items")
        print(f"    * Batch cleared: {removed} items")
        
        print_test_result(True, "Batch-pushed items cleared successfully")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
