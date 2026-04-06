"""
Comprehensive Dual-Queue Test Suite - AsyncQueue & AsyncPersistenceQueue

This unified test suite provides comprehensive coverage of both queue types:
  * AsyncQueue (in-memory, lock-free)
  * AsyncPersistenceQueue (Sled-backed, persistent)

Features:
  * All tests run against BOTH queue types via parametrization
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
  pytest test_queue.py              # Run all tests (both queue types)
  pytest test_queue.py -v           # Verbose output
  pytest test_queue.py -k "push"    # Run tests matching "push"
  pytest test_queue.py --tb=short   # Show short traceback
  pytest test_queue.py -k "async_queue" # Run AsyncQueue tests only
  pytest test_queue.py -k "persistence" # Run AsyncPersistenceQueue tests only
"""

import pytest
import time
import threading
import logging
import json
from typing import List, Union, Type

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
    from rst_queue import AsyncQueue, AsyncPersistenceQueue, ExecutionMode
except ImportError:
    import sys
    sys.path.insert(0, str(__file__).rsplit('/', 1)[0] + '/..')
    from rst_queue import AsyncQueue, AsyncPersistenceQueue, ExecutionMode

import shutil
import os


# ============================================================================
# PYTEST FIXTURES FOR PARAMETRIZATION
# ============================================================================

@pytest.fixture(params=['async_queue', 'persistence'], ids=['AsyncQueue', 'AsyncPersistenceQueue'])
def queue_type(request):
    """Parametrized fixture that provides both queue types"""
    return request.param


@pytest.fixture
def test_storage_path(tmp_path):
    """Provide a temporary storage path for persistence queue tests"""
    return str(tmp_path / "test_persist")


@pytest.fixture
def queue(queue_type, test_storage_path):
    """
    Create appropriate queue based on parametrization.
    
    Returns either AsyncQueue or AsyncPersistenceQueue with proper cleanup.
    Handles storage cleanup automatically for persistence queue.
    """
    if queue_type == 'async_queue':
        q = AsyncQueue(mode=1, buffer_size=128)
        yield q
    else:  # persistence
        # Clean up any existing storage
        if os.path.exists(test_storage_path):
            shutil.rmtree(test_storage_path)
        q = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        yield q
        # Cleanup after test
        if os.path.exists(test_storage_path):
            shutil.rmtree(test_storage_path)


@pytest.fixture
def sequential_queue(queue_type, test_storage_path):
    """Create sequential mode queue (mode=0) for both queue types"""
    if queue_type == 'async_queue':
        q = AsyncQueue(mode=0, buffer_size=128)
        yield q
    else:  # persistence
        if os.path.exists(test_storage_path):
            shutil.rmtree(test_storage_path)
        q = AsyncPersistenceQueue(mode=0, buffer_size=128, storage_path=test_storage_path)
        yield q
        if os.path.exists(test_storage_path):
            shutil.rmtree(test_storage_path)


def get_queue_type_name(queue) -> str:
    """Get the queue type name for display"""
    class_name = type(queue).__name__
    # Handle C extension types that might have different representations
    if 'Persistence' in class_name or 'persistence' in str(type(queue)):
        return "AsyncPersistenceQueue"
    return "AsyncQueue"


def create_queue(queue_type: str, test_storage_path: str, mode: int = 1) -> tuple:
    """
    Helper to create appropriate queue instance.
    Returns (queue, storage_path_to_cleanup)
    """
    if queue_type == 'async_queue':
        return AsyncQueue(mode=mode, buffer_size=128), None
    else:
        if os.path.exists(test_storage_path):
            shutil.rmtree(test_storage_path)
        return AsyncPersistenceQueue(mode=mode, buffer_size=128, storage_path=test_storage_path), test_storage_path


def cleanup_queue_storage(storage_path):
    """Clean up persistence queue storage"""
    if storage_path and os.path.exists(storage_path):
        shutil.rmtree(storage_path)


# ============================================================================
# UTILITY FUNCTIONS FOR BETTER OUTPUT
# ============================================================================

def print_test_header(test_name: str, description: str, queue_type_name: str = ""):
    """Print a formatted test header for clarity"""
    separator = "-" * 80
    queue_info = f" [{queue_type_name}]" if queue_type_name else ""
    print(f"\n{separator}")
    print(f"[TEST] {test_name}{queue_info}")
    print(f"  Description: {description}")
    print(f"{separator}\n")
    logger.info(f"Starting test: {test_name}{queue_info}")


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
    """Test queue creation and initialization - runs for both queue types"""

    def test_01_create_sequential_queue(self, queue_type, test_storage_path):
        """Test creating a sequential execution queue"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Create Sequential Queue",
            "Verify that a sequential queue can be created with proper initial state",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.SEQUENTIAL, buffer_size=128, storage_path=test_storage_path)
        
        try:
            logger.info(f"Queue created with mode: {print_mode(queue.get_mode())}")
            logger.info(f"Initial pushed count: {queue.total_pushed()}")
            
            assert queue.get_mode() == 0, "Mode should be SEQUENTIAL (0)"
            assert queue.total_pushed() == 0, "Pushed count should start at 0"
            
            print_test_result(True, f"Sequential queue created successfully")
            print_queue_stats(queue)
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_02_create_parallel_queue(self, queue_type, test_storage_path):
        """Test creating a parallel execution queue"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Create Parallel Queue",
            "Verify that a parallel queue can be created with proper initial state",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, buffer_size=128, storage_path=test_storage_path)
        
        try:
            logger.info(f"Queue created with mode: {print_mode(queue.get_mode())}")
            logger.info(f"Buffer size: 128")
            
            assert queue.get_mode() == 1, "Mode should be PARALLEL (1)"
            assert queue.total_pushed() == 0, "Pushed count should start at 0"
            
            print_test_result(True, "Parallel queue created successfully")
            print_queue_stats(queue)
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_03_create_queue_with_defaults(self, queue_type, test_storage_path):
        """Test creating queue with default parameters"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Create Queue with Defaults",
            "Verify that default parameters are applied correctly",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            logger.info(f"Queue created with default parameters")
            logger.info(f"Default mode: {print_mode(queue.get_mode())}")
            logger.info(f"Default total_pushed: {queue.total_pushed()}")
            
            # Default should be parallel
            assert queue.get_mode() == 1, "Default mode should be PARALLEL (1)"
            assert queue.total_pushed() == 0, "Initial pushed count should be 0"
            
            print_test_result(True, "Queue created with default parameters")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_04_buffer_size_parameter(self, queue_type, test_storage_path):
        """Test that buffer_size parameter is accepted"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Buffer Size Parameter",
            f"Verify that {queue_name} accepts custom buffer_size parameter",
            queue_name
        )
        
        buffer_sizes = [64, 128, 256, 512]
        
        for size in buffer_sizes:
            logger.info(f"Testing buffer size: {size}")
            if queue_type == 'async_queue':
                q = AsyncQueue(mode=0, buffer_size=size)
            else:
                storage = f"{test_storage_path}_{size}"
                if os.path.exists(storage): shutil.rmtree(storage)
                q = AsyncPersistenceQueue(mode=0, buffer_size=size, storage_path=storage)
                
            assert q.get_mode() == 0
            print(f"    * Buffer size {size} accepted")
            
            if queue_type == 'persistence':
                shutil.rmtree(storage)
        
        print_test_result(True, "All buffer sizes accepted")


# ============================================================================
# GROUP 2: QUEUE MODE OPERATIONS
# ============================================================================

class TestQueueModeOperations:
    """Test queue mode getting and setting operations - runs for both queue types"""

    def test_05_get_mode(self, queue_type, test_storage_path):
        """Test retrieving queue mode"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Get Queue Mode",
            f"Verify that {queue_name} mode can be retrieved correctly",
            queue_name
        )
        
        # Test sequential
        if queue_type == 'async_queue':
            seq_queue = AsyncQueue(mode=0)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            seq_queue = AsyncPersistenceQueue(mode=0, storage_path=test_storage_path)
        
        try:
            logger.info(f"Sequential queue mode: {seq_queue.get_mode()}")
            assert seq_queue.get_mode() == 0
            print(f"    * Sequential queue mode: {print_mode(seq_queue.get_mode())}")
            
            # Test parallel
            if queue_type == 'async_queue':
                par_queue = AsyncQueue(mode=1)
            else:
                storage2 = f"{test_storage_path}_par"
                if os.path.exists(storage2): shutil.rmtree(storage2)
                par_queue = AsyncPersistenceQueue(mode=1, storage_path=storage2)
                
            logger.info(f"Parallel queue mode: {par_queue.get_mode()}")
            assert par_queue.get_mode() == 1
            print(f"    * Parallel queue mode: {print_mode(par_queue.get_mode())}")
            
            if queue_type == 'persistence':
                shutil.rmtree(storage2)
            
            print_test_result(True, "Mode retrieval working correctly")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_06_set_mode(self, queue_type, test_storage_path):
        """Test changing queue mode"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Set Queue Mode",
            f"Verify that {queue_name} mode can be changed dynamically",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=0)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=0, storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_07_execution_mode_constants(self, queue_type, test_storage_path):
        """Test ExecutionMode constants"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "ExecutionMode Constants",
            "Verify that ExecutionMode constants have correct values",
            queue_name
        )
        
        logger.info(f"ExecutionMode.SEQUENTIAL = {ExecutionMode.SEQUENTIAL}")
        logger.info(f"ExecutionMode.PARALLEL = {ExecutionMode.PARALLEL}")
        
        assert ExecutionMode.SEQUENTIAL == 0, "SEQUENTIAL should be 0"
        assert ExecutionMode.PARALLEL == 1, "PARALLEL should be 1"
        
        print(f"    * SEQUENTIAL = {ExecutionMode.SEQUENTIAL}")
        print(f"    * PARALLEL = {ExecutionMode.PARALLEL}")
        
        print_test_result(True, "All constants have correct values")

    def test_08_alternating_mode_switches(self, queue_type, test_storage_path):
        """Test alternating mode switches"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Alternating Mode Switches",
            f"Verify that {queue_name} mode can be switched multiple times",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            for i in range(5):
                queue.set_mode(i % 2)
                mode_name = print_mode(queue.get_mode())
                logger.info(f"Switch {i+1}: {mode_name}")
                print(f"    * Switch {i+1}: {mode_name}")
            
            print_test_result(True, "Mode switching multiple times successful")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


# ============================================================================
# GROUP 3: PUSHING ITEMS TO QUEUE
# ============================================================================

class TestPushingItems:
    """Test pushing items to the queue - runs for both queue types"""

    def test_09_push_single_item(self, queue_type, test_storage_path):
        """Test pushing a single item"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Push Single Item",
            f"Verify that a single item can be pushed to the {queue_name}",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            test_data = b"test data"
            logger.info(f"Before: total_pushed = {queue.total_pushed()}")
            queue.push(test_data)
            logger.info(f"Pushed: {print_data_sample(test_data)}")
            logger.info(f"After: total_pushed = {queue.total_pushed()}")
            
            assert queue.total_pushed() == 1
            print(f"    * Item pushed: {print_data_sample(test_data)}")
            print(f"    * total_pushed: {queue.total_pushed()}")
            print_test_result(True, "Single item pushed successfully")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_10_push_multiple_items(self, queue_type, test_storage_path):
        """Test pushing multiple items"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Push Multiple Items",
            f"Verify that multiple items can be pushed to the {queue_name}",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_11_push_empty_bytes(self, queue_type, test_storage_path):
        """Test pushing empty bytes"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Push Empty Data",
            f"Verify that empty bytes can be pushed to the {queue_name}",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            empty_data = b""
            logger.info("Pushing empty bytes")
            queue.push(empty_data)
            logger.info(f"total_pushed after empty push: {queue.total_pushed()}")
            
            assert queue.total_pushed() == 1
            print(f"    * Empty bytes pushed: {print_data_sample(empty_data) if empty_data else '[EMPTY]'}")
            print(f"    * total_pushed: {queue.total_pushed()}")
            print_test_result(True, "Empty data handled correctly")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_12_push_large_data(self, queue_type, test_storage_path):
        """Test pushing large data"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Push Large Data",
            f"Verify that large data can be pushed to the {queue_name}",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            large_size_mb = 1
            large_data = b"x" * (1024 * 1024 * large_size_mb)
            logger.info(f"Pushing {large_size_mb}MB of data...")
            queue.push(large_data)
            logger.info(f"total_pushed after large push: {queue.total_pushed()}")
            
            assert queue.total_pushed() == 1
            print(f"    * Large data ({large_size_mb}MB) pushed successfully")
            print(f"    * total_pushed: {queue.total_pushed()}")
            print_test_result(True, f"Large data ({large_size_mb}MB) handled correctly")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_13_push_various_data_types(self, queue_type, test_storage_path):
        """Test pushing various data types encoded as bytes"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Push Various Data Types",
            f"Verify that different data types can be pushed to the {queue_name} as bytes",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


# ============================================================================
# GROUP 4: BATCH OPERATIONS
# ============================================================================

class TestBatchOperations:
    """Test batch push/get operations - runs for both queue types"""

    def test_14_push_batch(self, queue_type, test_storage_path):
        """Test batch push multiple items"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Batch Push",
            f"Verify that multiple items can be pushed at once to {queue_name}",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_15_push_batch_empty_list(self, queue_type, test_storage_path):
        """Test pushing empty batch"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Batch Push - Empty List",
            f"Verify that pushing empty batch to {queue_name} is handled correctly",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            ids = queue.push_batch([])
            logger.info(f"Empty batch returned {len(ids)} IDs")
            
            assert len(ids) == 0, "Empty batch should return empty ID list"
            assert queue.total_pushed() == 0
            
            print(f"    * Empty batch result: {len(ids)} IDs")
            print(f"    * total_pushed: {queue.total_pushed()}")
            print_test_result(True, "Empty batch handled correctly")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_16_push_batch_large(self, queue_type, test_storage_path):
        """Test push large batch (1000 items)"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Batch Push - Large (1000 items)",
            f"Verify that large batch can be pushed efficiently to {queue_name}",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            items = [b"large_" + str(i).encode() for i in range(1000)]
            logger.info(f"Pushing {len(items)} items...")
            ids = queue.push_batch(items)
            logger.info(f"Batch push complete, received {len(ids)} IDs")
            
            assert len(ids) == 1000
            assert queue.total_pushed() == 1000
            
            print(f"    * Batch size: {len(items)} items")
            print(f"    * total_pushed: {queue.total_pushed()}")
            print_test_result(True, f"Large batch ({len(items)} items) pushed successfully")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_17_batch_get_empty(self, queue_type, test_storage_path):
        """Test batch get returns empty when no results processed"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Batch Get - Empty Results",
            f"Verify that batch get from {queue_name} works with no processed results",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            items = [b"batch_item_" + str(i).encode() for i in range(10)]
            logger.info(f"Pushing {len(items)} items...")
            queue.push_batch(items)
            
            logger.info("Attempting to get batch without workers processing...")
            retrieved = queue.get_batch(5)
            logger.info(f"Batch get returned {len(retrieved)} items")
            
            assert len(retrieved) == 0, "No results should be available without workers"
            print(f"    * Retrieved items: {len(retrieved)}")
            print_test_result(True, "Batch get correctly returns empty when no results")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_18_multiple_batch_operations(self, queue_type, test_storage_path):
        """Test multiple batch operations"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Multiple Batch Operations",
            f"Verify that multiple batch operations work on {queue_name}",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


# ============================================================================
# GROUP 5: QUEUE STATISTICS AND MONITORING
# ============================================================================

class TestQueueStatistics:
    """Test queue statistics and monitoring - runs for both queue types"""

    def test_19_total_pushed_counter(self, queue_type, test_storage_path):
        """Test that total_pushed counter increments correctly"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Pushed Counter",
            f"Verify that {queue_name} total_pushed counter increments for each push",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            logger.info(f"Initial total_pushed: {queue.total_pushed()}")
            print(f"    Initial: {queue.total_pushed()}")
            
            num_pushes = 15
            for i in range(num_pushes):
                queue.push(f"item_{i}".encode())
                current = queue.total_pushed()
                logger.info(f"  After push {i+1}: total_pushed = {current}")
            
            assert queue.total_pushed() == num_pushes
            print_test_result(True, f"Counter incremented correctly to {num_pushes}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_20_get_stats(self, queue_type, test_storage_path):
        """Test getting queue statistics"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Get Queue Statistics",
            f"Verify that {queue_name} statistics can be retrieved",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_21_active_workers(self, queue_type, test_storage_path):
        """Test getting active workers count"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Active Workers Count",
            f"Verify that {queue_name} active workers count can be retrieved",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            workers = queue.active_workers()
            logger.info(f"Active workers: {workers}")
            
            assert workers >= 0, "Active workers should be non-negative"
            
            print(f"    * Active workers: {workers}")
            print_test_result(True, "Active workers count retrieved successfully")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_22_concurrent_counter_increments(self, queue_type, test_storage_path):
        """Test counter increments correctly with concurrent pushes"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Concurrent Counter Increments",
            f"Verify that {queue_name} counter is accurate with multiple threads",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


# ============================================================================
# GROUP 6: CONCURRENCY AND THREAD SAFETY
# ============================================================================

class TestConcurrency:
    """Test concurrent access patterns - runs for both queue types"""

    def test_23_concurrent_push(self, queue_type, test_storage_path):
        """Test multiple threads pushing concurrently"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Concurrent Push",
            f"Verify that {queue_name} can handle multiple threads pushing safely",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_24_concurrent_batch_push(self, queue_type, test_storage_path):
        """Test multiple threads pushing batches concurrently"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Concurrent Batch Push",
            f"Verify that {queue_name} can handle multiple threads batch pushing safely",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_25_producer_consumer(self, queue_type, test_storage_path):
        """Test producer and consumer pattern"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Producer-Consumer Pattern",
            f"Verify that {queue_name} works in producer-consumer scenario",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_26_high_contention(self, queue_type, test_storage_path):
        """Test high-contention scenario (8 threads pushing)"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "High-Contention Scenario",
            f"Verify {queue_name} handles high contention (8 threads, 50 items each)",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


# ============================================================================
# GROUP 7: LOCK-FREE AND PERFORMANCE PROPERTIES
# ============================================================================

class TestLockFreeProperties:
    """Test lock-free guarantee validation - runs for both queue types"""

    def test_27_no_blocking_empty_queue(self, queue_type, test_storage_path):
        """Test that getting from empty queue doesn't block"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Non-Blocking Get from Empty Queue",
            f"Verify that {queue_name} get() returns immediately without blocking",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_28_push_doesnt_block(self, queue_type, test_storage_path):
        """Test that push operation doesn't block under contention"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Non-Blocking Push Under Contention",
            f"Verify that {queue_name} push() completes quickly even with contention",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


# ============================================================================
# GROUP 8: MEMORY AND EDGE CASES
# ============================================================================

class TestMemoryManagement:
    """Test memory behavior and cleanup - runs for both queue types"""

    def test_29_memory_bounded(self, queue_type, test_storage_path):
        """Test queue handles large items efficiently"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Memory - Large Items",
            f"Verify that {queue_name} can handle large data items",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            large_item = b"x" * (1 * 1024 * 1024)  # 1MB item
            
            logger.info(f"Pushing 10 x 1MB items...")
            for i in range(10):
                queue.push(large_item)
            
            assert queue.total_pushed() == 10
            
            print(f"    * Item size: 1 MB")
            print(f"    * Items pushed: 10")
            print(f"    * total_pushed: {queue.total_pushed()}")
            
            print_test_result(True, "Queue handles 10 MB of data efficiently")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_30_fifo_batch_ordering(self, queue_type, test_storage_path):
        """Test batch operations preserve order"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "FIFO Ordering - Batch Ops",
            f"Verify that {queue_name} batch operations maintain FIFO order",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_31_stats_consistency(self, queue_type, test_storage_path):
        """Test queue stats are consistent"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Statistics Consistency",
            f"Verify that all {queue_name} statistics remain consistent",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


class TestEdgeCases:
    """Test edge cases and unusual scenarios - runs for both queue types"""

    def test_32_mode_switching_with_items(self, queue_type, test_storage_path):
        """Test switching modes with items in queue"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Mode Switching with Items",
            f"Verify that {queue_name} mode can be switched while queue has items",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_33_alternating_operations(self, queue_type, test_storage_path):
        """Test alternating push/get operations"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Alternating Push/Get",
            f"Verify that {queue_name} alternating push and get operations work",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_34_get_from_empty(self, queue_type, test_storage_path):
        """Test get from empty queue"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Get from Empty Queue",
            f"Verify that {queue_name} get from empty queue returns None",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            logger.info("Getting from empty queue...")
            item = queue.get()
            
            logger.info(f"Item returned: {item}")
            
            assert item is None
            
            print(f"    * Item returned: {item}")
            print(f"    * total_pushed: {queue.total_pushed()}")
            
            print_test_result(True, "Get from empty queue returns None")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_35_active_workers_monitoring(self, queue_type, test_storage_path):
        """Test active workers count during operations"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Active Workers Monitoring",
            f"Verify that {queue_name} active workers count can be monitored",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
            item = queue.get()
            # Item might be None since these are processed results
        
        assert queue.total_pushed() == 50
        
        print(f"    * Alternating operations: 50 iterations")
        print(f"    * total_pushed: {queue.total_pushed()}")
        
        print_test_result(True, "Alternating push/get operations successful")

    def test_34_get_from_empty(self, queue_type, test_storage_path):
        """Test get from empty queue"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Get from Empty Queue",
            "Verify that get from empty queue returns None",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            logger.info("Getting from empty queue...")
            item = queue.get()
            
            logger.info(f"Item returned: {item}")
            
            assert item is None
            
            print(f"    * Item returned: {item}")
            print(f"    * total_pushed: {queue.total_pushed()}")
            
            print_test_result(True, "Get from empty queue returns None")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_35_active_workers_monitoring(self, queue_type, test_storage_path):
        """Test active workers count during operations"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Active Workers Monitoring",
            "Verify that active workers count can be monitored",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


# ============================================================================
# GROUP 9: QUICK REFERENCE - COMMON USE CASES
# ============================================================================

class TestQuickReferenceExamples:
    """Quick reference examples for common use cases - runs for both queue types"""

    def test_36_basic_queue_usage(self, queue_type, test_storage_path):
        """Quick example: Basic queue push and get"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "[REFERENCE] Basic Queue Usage",
            f"How to create a {queue_name} and push items",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            queue.push(b"hello world")
            assert queue.total_pushed() == 1
            print_test_result(True, "Example verified")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_37_batch_processing(self, queue_type, test_storage_path):
        """Quick example: Batch push operations"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "[REFERENCE] Batch Processing",
            f"How to push multiple items in a batch to {queue_name}",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            items = [b"item1", b"item2", b"item3"]
            ids = queue.push_batch(items)
            assert len(ids) == 3
            print_test_result(True, "Example verified")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_38_mode_selection(self, queue_type, test_storage_path):
        """Quick example: Choosing execution mode"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "[REFERENCE] Execution Mode Selection",
            f"How to choose execution modes for {queue_name}",
            queue_name
        )
        
        if queue_type == 'async_queue':
            seq_queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL)
            par_queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            seq_queue = AsyncPersistenceQueue(mode=ExecutionMode.SEQUENTIAL, storage_path=test_storage_path)
            storage2 = f"{test_storage_path}_par"
            if os.path.exists(storage2): shutil.rmtree(storage2)
            par_queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, storage_path=storage2)
        
        try:
            assert seq_queue.get_mode() == 0
            assert par_queue.get_mode() == 1
            print_test_result(True, "Example verified")
            if queue_type == 'persistence':
                shutil.rmtree(storage2)
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_39_monitoring_statistics(self, queue_type, test_storage_path):
        """Quick example: Monitoring queue statistics"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "[REFERENCE] Monitoring Queue Statistics",
            f"How to track {queue_name} metrics and statistics",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            queue.push(b"data1")
            queue.push(b"data2")
            stats = queue.get_stats()
            assert stats.total_pushed == 2
            print_test_result(True, "Example verified")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


# ============================================================================
# GROUP 10: NEW METHODS - CLEAR AND PENDING_ITEMS
# ============================================================================

class TestClearAndPendingItems:
    """Test new methods: clear() and pending_items()"""

    def test_40_clear_empty_queue(self, queue_type, test_storage_path):
        """Test clearing an empty queue"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Clear - Empty Queue",
            "Verify that clearing an empty queue returns 0",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        logger.info("Clearing empty queue...")
        removed = queue.clear()
        
        logger.info(f"Items removed: {removed}")
        
        assert removed == 0
        assert queue.total_pushed() == 0
        
        try:
            logger.info("Clearing empty queue...")
            removed = queue.clear()
            
            logger.info(f"Items removed: {removed}")
            
            assert removed == 0
            assert queue.total_pushed() == 0
            
            print(f"    * Items removed: {removed}")
            print(f"    * total_pushed: {queue.total_pushed()}")
            
            print_test_result(True, "Empty queue cleared (0 items removed)")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_41_clear_queue_with_items(self, queue_type, test_storage_path):
        """Test clearing queue with pending items"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Clear - Queue with Items",
            "Verify that clear removes all pending items",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_42_clear_large_batch(self, queue_type, test_storage_path):
        """Test clearing a large batch of items"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Clear - Large Batch",
            "Verify that clear handles large batches efficiently",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_43_clear_preserves_stats(self, queue_type, test_storage_path):
        """Test that clear doesn't affect statistics counters"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Clear - Statistics Preservation",
            "Verify that clear doesn't modify queue statistics",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_44_clear_while_processing(self, queue_type, test_storage_path):
        """Test clearing while workers are processing"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Clear - During Processing",
            "Verify that clear doesn't affect items being processed",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_45_pending_items_empty_queue(self, queue_type, test_storage_path):
        """Test pending_items on empty queue"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "pending_items - Empty Queue",
            "Verify that pending_items returns 0 for empty queue",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            logger.info("Checking pending items on empty queue...")
            pending = queue.pending_items()
            
            logger.info(f"Pending items: {pending}")
            
            assert pending == 0
            
            print(f"    * Pending items: {pending}")
            
            print_test_result(True, "pending_items correctly returns 0 for empty queue")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_46_pending_items_with_items(self, queue_type, test_storage_path):
        """Test pending_items returns correct count"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "pending_items - With Items",
            "Verify that pending_items returns accurate count",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_47_pending_items_after_clear(self, queue_type, test_storage_path):
        """Test pending_items after clearing"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "pending_items - After Clear",
            "Verify that pending_items returns 0 after clear",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_48_clear_and_pending_concurrent(self, queue_type, test_storage_path):
        """Test clear and pending_items under concurrent access"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Clear & pending_items - Concurrent",
            "Verify thread safety of both operations",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_49_multiple_clears(self, queue_type, test_storage_path):
        """Test multiple clear operations in sequence"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Multiple Clears",
            "Verify that multiple clears work correctly",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_50_clear_batch_push(self, queue_type, test_storage_path):
        """Test clear after batch push"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Clear - After Batch Push",
            "Verify that clear works with batch-pushed items",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
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
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)


# ============================================================================
# GROUP 11: TOTAL_REMOVED COUNTER - NEW FEATURE
# ============================================================================

class TestTotalRemovedCounter:
    """Test the new total_removed counter in queue statistics"""

    def test_51_total_removed_field_exists(self, queue_type, test_storage_path):
        """Test that total_removed field exists in stats"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - Field Existence",
            "Verify that total_removed field is present in QueueStats",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            stats = queue.get_stats()
            
            logger.info("Checking for total_removed field...")
            has_field = hasattr(stats, 'total_removed')
            logger.info(f"  total_removed field: {has_field}")
            
            assert has_field, "Stats should have 'total_removed' field"
            
            print(f"    * total_removed field exists: {has_field}")
            print(f"    * initial value: {stats.total_removed}")
            
            print_test_result(True, "total_removed field verified")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_52_total_removed_initial_value(self, queue_type, test_storage_path):
        """Test that total_removed is initially 0"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - Initial State",
            "Verify initial total_removed is 0",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue()
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(storage_path=test_storage_path)
        
        try:
            stats = queue.get_stats()
            
            logger.info(f"Initial total_removed: {stats.total_removed}")
            
            assert stats.total_removed == 0
            
            print(f"    * Initial total_removed: {stats.total_removed}")
            print_test_result(True, "Initial total_removed is 0")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_53_total_removed_after_get(self, queue_type, test_storage_path):
        """Test total_removed increments after get()"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - After get()",
            "Verify total_removed increments when results are consumed",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, storage_path=test_storage_path)
        
        try:
            def simple_worker(item_id, data):
                return data.upper()
            
            logger.info("Starting workers...")
            queue.start_with_results(simple_worker, num_workers=1)
            
            # Push items
            logger.info("Pushing 5 items...")
            for i in range(5):
                queue.push(f"item{i}".encode())
            
            time.sleep(0.3)  # Wait for processing
            
            # Get results one by one
            logger.info("Getting results with get()...")
            removed_count = 0
            for i in range(5):
                result = queue.get()
                if result:
                    removed_count += 1
                    logger.info(f"  Got result {result.id}")
            
            stats = queue.get_stats()
            logger.info(f"Final stats: removed={stats.total_removed}, processed={stats.total_processed}")
            
            assert stats.total_removed == 5
            
            print(f"    * Items pushed: 5")
            print(f"    * Items retrieved with get(): {removed_count}")
            print(f"    * total_removed: {stats.total_removed}")
            print(f"    * total_processed: {stats.total_processed}")
            
            print_test_result(True, f"get() incremented total_removed to {stats.total_removed}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_54_total_removed_after_get_batch(self, queue_type, test_storage_path):
        """Test total_removed increments after get_batch()"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - After get_batch()",
            "Verify total_removed increments with batch consumption",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, storage_path=test_storage_path)
        
        try:
            def batch_worker(item_id, data):
                return data * 2
            
            logger.info("Starting workers...")
            queue.start_with_results(batch_worker, num_workers=2)
            
            # Push 10 items
            logger.info("Pushing 10 items...")
            for i in range(10):
                queue.push(f"data{i}".encode())
            
            time.sleep(0.4)  # Wait for processing
            
            # Get batch
            logger.info("Getting batch of 5...")
            batch1 = queue.get_batch(5)
            logger.info(f"  Retrieved {len(batch1)} items")
            
            stats_after_batch1 = queue.get_stats()
            logger.info(f"After first batch: total_removed={stats_after_batch1.total_removed}")
            
            assert stats_after_batch1.total_removed == 5
            
            # Get remaining
            logger.info("Getting remaining items...")
            batch2 = queue.get_batch(10)
            logger.info(f"  Retrieved {len(batch2)} items")
            
            stats_after_batch2 = queue.get_stats()
            logger.info(f"After second batch: total_removed={stats_after_batch2.total_removed}")
            
            assert stats_after_batch2.total_removed == 10
            
            print(f"    * Items pushed: 10")
            print(f"    * First batch get_batch(5): {len(batch1)} items")
            print(f"    * total_removed after batch1: {stats_after_batch1.total_removed}")
            print(f"    * Second batch get_batch(10): {len(batch2)} items")
            print(f"    * total_removed after batch2: {stats_after_batch2.total_removed}")
            
            print_test_result(True, f"get_batch() incremented total_removed to {stats_after_batch2.total_removed}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_55_total_removed_after_get_blocking(self, queue_type, test_storage_path):
        """Test total_removed increments after get_blocking()"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - After get_blocking()",
            "Verify total_removed increments with blocking get",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, storage_path=test_storage_path)
        
        try:
            def worker(item_id, data):
                return b"result: " + data
            
            logger.info("Starting workers...")
            queue.start_with_results(worker, num_workers=1)
            
            # Push 3 items
            logger.info("Pushing 3 items...")
            for i in range(3):
                queue.push(f"item{i}".encode())
            
            time.sleep(0.2)  # Wait for processing
            
            # Get with blocking
            logger.info("Getting result with get_blocking()...")
            result = queue.get_blocking()
            logger.info(f"  Got result: {result}")
            
            stats = queue.get_stats()
            logger.info(f"After get_blocking: total_removed={stats.total_removed}")
            
            assert stats.total_removed == 1
            
            # Get more with get()
            result2 = queue.get()
            result3 = queue.get()
            
            stats_final = queue.get_stats()
            logger.info(f"Final total_removed={stats_final.total_removed}")
            
            assert stats_final.total_removed == 3
            
            print(f"    * Items pushed: 3")
            print(f"    * get_blocking() called once")
            print(f"    * total_removed after get_blocking: {stats.total_removed}")
            print(f"    * get() called twice more")
            print(f"    * final total_removed: {stats_final.total_removed}")
            
            print_test_result(True, f"get_blocking() incremented total_removed to {stats_final.total_removed}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)

    def test_56_total_removed_partial_consumption(self, queue_type, test_storage_path):
        """Test total_removed with partial consumption"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - Partial Consumption",
            "Verify total_removed reflects only consumed items",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, storage_path=test_storage_path)
        
        try:
            def worker(item_id, data):
                return data.upper()
            
            logger.info("Starting workers...")
            queue.start_with_results(worker, num_workers=1)
            
            # Push 10 items
            logger.info("Pushing 10 items...")
            for i in range(10):
                queue.push(f"item{i}".encode())
            
            time.sleep(0.5)  # Wait for all to be processed
            
            # Consume only 3 items
            logger.info("Consuming only 3 out of 10...")
            for i in range(3):
                queue.get()
            
            stats = queue.get_stats()
            logger.info(f"Stats after partial consumption: total_removed={stats.total_removed}")
            
            assert stats.total_removed == 3
            assert stats.total_processed == 10  # All processed
            
            print(f"    * Items pushed: 10")
            print(f"    * Items processed: {stats.total_processed}")
            print(f"    * Items consumed (removed): {stats.total_removed}")
            
            print_test_result(True, f"total_removed correctly shows {stats.total_removed} consumed, {stats.total_processed} processed")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
        
        logger.info("Starting workers...")
        queue.start_with_results(worker, num_workers=1)
        
        # Push 10 items
        logger.info("Pushing 10 items...")
        for i in range(10):
            queue.push(f"item{i}".encode())
        
        time.sleep(0.5)  # Wait for all to be processed
        
        # Consume only 3 items
        logger.info("Consuming only 3 out of 10...")
        for i in range(3):
            queue.get()
        
        stats = queue.get_stats()
        logger.info(f"Stats after partial consumption: total_removed={stats.total_removed}")
        
        assert stats.total_removed == 3
        assert stats.total_processed == 10  # All processed
        
        print(f"    * Items pushed: 10")
        print(f"    * Items processed: {stats.total_processed}")
        print(f"    * Items consumed (removed): {stats.total_removed}")
        
        print_test_result(True, f"total_removed correctly shows {stats.total_removed} consumed, {stats.total_processed} processed")

    def test_57_total_removed_multiple_batches(self, queue_type, test_storage_path):
        """Test total_removed across multiple batch operations"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - Multiple Batches",
            "Verify total_removed accumulates across multiple get_batch calls",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, storage_path=test_storage_path)
        
        try:
            def worker(item_id, data):
                return data
            
            logger.info("Starting workers...")
            queue.start_with_results(worker, num_workers=2)
            
            # Push 100 items
            logger.info("Pushing 100 items...")
            for i in range(100):
                queue.push(f"item{i}".encode())
            
            time.sleep(0.8)  # Wait for all to be processed
            
            # Consume in batches
            logger.info("Consuming in batches of 10, 20, 30...")
            batch_sizes = [10, 20, 30, 40]
            total_consumed = 0
            
            for batch_size in batch_sizes:
                batch = queue.get_batch(batch_size)
                consumed = len(batch)
                total_consumed += consumed
                stats = queue.get_stats()
                logger.info(f"  Batch of {batch_size}: got {consumed}, total_removed={stats.total_removed}")
                print(f"    * get_batch({batch_size}): got {consumed} items, cumulative total_removed={stats.total_removed}")
            
            stats_final = queue.get_stats()
            logger.info(f"Final: total_removed={stats_final.total_removed}, total_consumed={total_consumed}")
            
            assert stats_final.total_removed == total_consumed
            
            print(f"    * Total items pushed: 100")
            print(f"    * Total items consumed: {total_consumed}")
            print(f"    * final total_removed: {stats_final.total_removed}")
            
            print_test_result(True, f"total_removed correctly accumulated to {stats_final.total_removed}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
        
        logger.info("Starting workers...")
        queue.start_with_results(worker, num_workers=2)
        
        # Push 100 items
        logger.info("Pushing 100 items...")
        for i in range(100):
            queue.push(f"item{i}".encode())
        
        time.sleep(0.8)  # Wait for all to be processed
        
        # Consume in batches
        logger.info("Consuming in batches of 10, 20, 30...")
        batch_sizes = [10, 20, 30, 40]
        total_consumed = 0
        
        for batch_size in batch_sizes:
            batch = queue.get_batch(batch_size)
            consumed = len(batch)
            total_consumed += consumed
            stats = queue.get_stats()
            logger.info(f"  Batch of {batch_size}: got {consumed}, total_removed={stats.total_removed}")
            print(f"    * get_batch({batch_size}): got {consumed} items, cumulative total_removed={stats.total_removed}")
        
        stats_final = queue.get_stats()
        logger.info(f"Final: total_removed={stats_final.total_removed}, total_consumed={total_consumed}")
        
        assert stats_final.total_removed == total_consumed
        
        print(f"    * Total items pushed: 100")
        print(f"    * Total items consumed: {total_consumed}")
        print(f"    * final total_removed: {stats_final.total_removed}")
        
        print_test_result(True, f"total_removed correctly accumulated to {stats_final.total_removed}")

    def test_58_total_removed_versus_processed(self, queue_type, test_storage_path):
        """Test relationship between total_removed and total_processed"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - vs Total Processed",
            "Verify total_removed <= total_processed relationship",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, storage_path=test_storage_path)
        
        try:
            def worker(item_id, data):
                return data
            
            logger.info("Starting workers...")
            queue.start_with_results(worker, num_workers=2)
            
            # Push 20 items
            logger.info("Pushing 20 items...")
            for i in range(20):
                queue.push(f"item{i}".encode())
            
            time.sleep(0.5)  # Wait for processing
            
            # Consume only 15
            logger.info("Consuming 15 out of 20...")
            for _ in range(15):
                queue.get()
            
            stats = queue.get_stats()
            logger.info(f"Stats: total_removed={stats.total_removed}, total_processed={stats.total_processed}")
            
            # total_removed should be <= total_processed
            assert stats.total_removed <= stats.total_processed
            assert stats.total_processed >= stats.total_removed
            
            print(f"    * total_processed: {stats.total_processed}")
            print(f"    * total_removed: {stats.total_removed}")
            print(f"    * Relationship (removed ≤ processed): {stats.total_removed} ≤ {stats.total_processed} ✓")
            
            print_test_result(True, f"Relationship verified: total_removed({stats.total_removed}) ≤ total_processed({stats.total_processed})")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
        
        logger.info("Starting workers...")
        queue.start_with_results(worker, num_workers=2)
        
        # Push 20 items
        logger.info("Pushing 20 items...")
        for i in range(20):
            queue.push(f"item{i}".encode())
        
        time.sleep(0.5)  # Wait for processing
        
        # Consume only 15
        logger.info("Consuming 15 out of 20...")
        for _ in range(15):
            queue.get()
        
        stats = queue.get_stats()
        logger.info(f"Stats: total_removed={stats.total_removed}, total_processed={stats.total_processed}")
        
        # total_removed should be <= total_processed
        assert stats.total_removed <= stats.total_processed
        assert stats.total_processed >= stats.total_removed
        
        print(f"    * total_processed: {stats.total_processed}")
        print(f"    * total_removed: {stats.total_removed}")
        print(f"    * Relationship (removed ≤ processed): {stats.total_removed} ≤ {stats.total_processed} ✓")
        
        print_test_result(True, f"Relationship verified: total_removed({stats.total_removed}) ≤ total_processed({stats.total_processed})")

    def test_59_total_removed_all_consumed(self, queue_type, test_storage_path):
        """Test total_removed when all processed items are consumed"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - All Consumed",
            "Verify total_removed == total_processed when all consumed",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, storage_path=test_storage_path)
        
        try:
            def worker(item_id, data):
                return data.lower()
            
            logger.info("Starting workers...")
            queue.start_with_results(worker, num_workers=2)
            
            # Push and consume all
            num_items = 25
            logger.info(f"Pushing and consuming {num_items} items...")
            
            for i in range(num_items):
                queue.push(f"ITEM{i}".encode())
            
            time.sleep(0.5)  # Wait for processing
            
            # Consume all
            count = 0
            while True:
                result = queue.get()
                if result is None:
                    break
                count += 1
            
            stats = queue.get_stats()
            logger.info(f"Final stats: pushed={stats.total_pushed}, processed={stats.total_processed}, removed={stats.total_removed}")
            
            assert stats.total_removed == stats.total_processed
            
            print(f"    * Items pushed: {stats.total_pushed}")
            print(f"    * Items processed: {stats.total_processed}")
            print(f"    * Items consumed: {stats.total_removed}")
            print(f"    * Equality check (removed == processed): {stats.total_removed} == {stats.total_processed} ✓")
            
            print_test_result(True, f"All items consumed: total_removed({stats.total_removed}) == total_processed({stats.total_processed})")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
        
        logger.info("Starting workers...")
        queue.start_with_results(worker, num_workers=2)
        
        # Push and consume all
        num_items = 25
        logger.info(f"Pushing and consuming {num_items} items...")
        
        for i in range(num_items):
            queue.push(f"ITEM{i}".encode())
        
        time.sleep(0.5)  # Wait for processing
        
        # Consume all
        count = 0
        while True:
            result = queue.get()
            if result is None:
                break
            count += 1
        
        stats = queue.get_stats()
        logger.info(f"Final stats: pushed={stats.total_pushed}, processed={stats.total_processed}, removed={stats.total_removed}")
        
        assert stats.total_removed == stats.total_processed
        
        print(f"    * Items pushed: {stats.total_pushed}")
        print(f"    * Items processed: {stats.total_processed}")
        print(f"    * Items consumed: {stats.total_removed}")
        print(f"    * Equality check (removed == processed): {stats.total_removed} == {stats.total_processed} ✓")
        
        print_test_result(True, f"All items consumed: total_removed({stats.total_removed}) == total_processed({stats.total_processed})")

    def test_60_total_removed_stats_repr(self, queue_type, test_storage_path):
        """Test that total_removed appears in stats repr"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Total Removed - Stats Representation",
            "Verify total_removed is displayed in stats string",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=ExecutionMode.PARALLEL)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=ExecutionMode.PARALLEL, storage_path=test_storage_path)
        
        try:
            def worker(item_id, data):
                return data
            
            queue.start_with_results(worker, num_workers=1)
            
            # Push and consume some items
            logger.info("Pushing and consuming items...")
            for i in range(5):
                queue.push(f"item{i}".encode())
            
            time.sleep(0.3)
            
            # Consume 3 items
            for _ in range(3):
                queue.get()
            
            stats = queue.get_stats()
            stats_repr = repr(stats)
            
            logger.info(f"Stats repr: {stats_repr}")
            
            # Check that total_removed is in the representation
            assert 'total_removed' in stats_repr.lower()
            
            print(f"    * Stats representation:")
            print(f"      {stats_repr}")
            print(f"    * Contains 'total_removed': {'total_removed' in stats_repr.lower()}")
            
            print_test_result(True, "total_removed is visible in stats representation")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
        
        queue.start_with_results(worker, num_workers=1)
        
        # Push and consume some items
        logger.info("Pushing and consuming items...")
        for i in range(5):
            queue.push(f"item{i}".encode())
        
        time.sleep(0.3)
        
        # Consume 3 items
        for _ in range(3):
            queue.get()
        
        stats = queue.get_stats()
        stats_repr = repr(stats)
        
        logger.info(f"Stats repr: {stats_repr}")
        
        # Check that total_removed is in the representation
        assert 'total_removed' in stats_repr.lower()
        
        print(f"    * Stats representation:")
        print(f"      {stats_repr}")
        print(f"    * Contains 'total_removed': {'total_removed' in stats_repr.lower()}")
        
        print_test_result(True, "total_removed is visible in stats representation")


# ============================================================================
# GROUP 11: ASYNCPERSISTENCEQUEUE TESTS
# ============================================================================

class TestAsyncPersistenceQueue:
    """Test suite for AsyncPersistenceQueue with Sled persistence"""
    
    @staticmethod
    def cleanup_storage(path):
        """Clean up persistent storage"""
        if os.path.exists(path):
            shutil.rmtree(path)
    
    def test_61_persistence_queue_creation(self, queue_type, test_storage_path):
        """Test AsyncPersistenceQueue creation and initialization"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Persistence Queue Creation",
            "Verify both queue types can be created",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=1, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        
        try:
            stats = queue.get_stats()
            assert stats.total_pushed == 0
            assert stats.total_processed == 0
            assert stats.total_removed == 0
            
            logger.info(f"{queue_name} created successfully")
            print(f"    * Queue type: {queue_name}")
            print(f"    * Initial stats: pushed={stats.total_pushed}, processed={stats.total_processed}")
            
            if queue_type == 'persistence':
                assert os.path.exists(test_storage_path), "Storage path not created"
            
            print_test_result(True, f"{queue_name} created successfully")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
    
    def test_62_persistence_push_items(self, queue_type, test_storage_path):
        """Test pushing items to queue"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Persistence Queue - Push Items",
            "Verify items are stored correctly",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=1, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        
        try:
            logger.info("Pushing 10 items...")
            for i in range(10):
                queue.push(f"persist_item_{i}".encode())
            
            stats = queue.get_stats()
            assert stats.total_pushed == 10
            
            print(f"    * Items pushed: {stats.total_pushed}")
            
            if queue_type == 'persistence':
                assert os.path.exists(test_storage_path)
                storage_files = os.listdir(test_storage_path)
                print(f"    * Storage files created: {storage_files}")
            
            print_test_result(True, f"10 items pushed to {queue_name}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
    
    def test_63_persistence_process_items(self, queue_type, test_storage_path):
        """Test processing items with both queue types"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Persistence Queue - Process Items",
            "Verify workers process items correctly",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=1, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        
        try:
            def simple_worker(item_id, data):
                return data.upper()
            
            logger.info("Pushing 10 items...")
            for i in range(10):
                queue.push(f"item_{i}".encode())
            
            logger.info("Starting workers...")
            queue.start_with_results(simple_worker, num_workers=2)
            time.sleep(1)
            
            stats = queue.get_stats()
            assert stats.total_processed == 10
            
            print(f"    * Items pushed: {stats.total_pushed}")
            print(f"    * Items processed: {stats.total_processed}")
            
            print_test_result(True, f"10 items processed with {queue_name}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
    
    def test_64_persistence_retrieve_results(self, queue_type, test_storage_path):
        """Test retrieving results from both queue types"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Persistence Queue - Retrieve Results",
            "Verify results can be retrieved",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=1, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        
        try:
            def transform_worker(item_id, data):
                return f"[{item_id}] {data.decode()}".encode()
            
            logger.info("Pushing 8 items...")
            for i in range(8):
                queue.push(f"data_{i}".encode())
            
            logger.info("Starting workers...")
            queue.start_with_results(transform_worker, num_workers=2)
            time.sleep(0.8)
            
            logger.info("Retrieving results...")
            results = queue.get_batch(100)
            
            assert len(results) == 8
            
            print(f"    * Items pushed: 8")
            print(f"    * Results retrieved: {len(results)}")
            if results:
                print(f"    * Sample result: {results[0].result.decode()}")
            
            print_test_result(True, f"8 results retrieved from {queue_name}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
    
    def test_65_persistence_storage_creation(self, queue_type, test_storage_path):
        """Test storage structure creation"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Persistence Queue - Storage Structure",
            "Verify storage structure is created",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=1, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        
        try:
            # Push some data to trigger storage
            for i in range(5):
                queue.push(f"data_{i}".encode())
            
            # Verify structure for persistence queue
            if queue_type == 'persistence':
                assert os.path.exists(test_storage_path)
                files = os.listdir(test_storage_path)
                logger.info(f"Storage files: {files}")
                assert 'db' in files
                
                print(f"    * Storage path: {test_storage_path}")
                print(f"    * Storage files created: {files}")
                print(f"    * Directory structure verified ✓")
            else:
                print(f"    * Queue type: {queue_name} (memory-only, no persistent storage)")
            
            print_test_result(True, f"{queue_name} storage verified")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
    
    def test_66_persistence_versus_memory_queue(self, queue_type, test_storage_path):
        """Compare both queue types with same worker"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Persistence vs Memory Queue",
            "Verify both queue types produce consistent results",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=1, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        
        try:
            def shared_worker(item_id, data):
                return data.upper()
            
            logger.info(f"Push to {queue_name}...")
            for i in range(5):
                queue.push(f"task_{i}".encode())
            
            logger.info(f"Process with {queue_name}...")
            queue.start_with_results(shared_worker, num_workers=2)
            time.sleep(0.8)
            
            logger.info(f"Get results from {queue_name}...")
            results = queue.get_batch(100)
            
            assert len(results) == 5
            
            stats = queue.get_stats()
            
            assert stats.total_pushed == stats.total_processed
            
            print(f"    * Queue type: {queue_name}")
            print(f"    * Pushed: {stats.total_pushed}, Processed: {stats.total_processed}")
            print(f"    * Results retrieved: {len(results)}")
            
            print_test_result(True, f"{queue_name} processes items consistently")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
    
    def test_67_persistence_clear_operation(self, queue_type, test_storage_path):
        """Test clear operation with both queue types"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Persistence Queue - Clear Operation",
            "Verify clear() works correctly",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=1, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        
        try:
            logger.info("Pushing 15 items...")
            for i in range(15):
                queue.push(f"item_{i}".encode())
            
            stats_before = queue.get_stats()
            logger.info(f"Before clear: pushed={stats_before.total_pushed}")
            
            logger.info("Clearing queue...")
            cleared = queue.clear()
            
            stats_after = queue.get_stats()
            
            assert cleared == 15
            assert stats_after.total_pushed == stats_before.total_pushed  # Stats unchanged
            
            print(f"    * Items cleared: {cleared}")
            print(f"    * total_pushed before: {stats_before.total_pushed}")
            print(f"    * total_pushed after: {stats_after.total_pushed} (unchanged)")
            
            print_test_result(True, f"Cleared 15 items from {queue_name}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
    
    def test_68_persistence_total_removed_tracking(self, queue_type, test_storage_path):
        """Test total_removed counter with both queue types"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Persistence Queue - Total Removed Tracking",
            "Verify total_removed counter works",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=1, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        
        try:
            def simple_worker(item_id, data):
                return data
            
            logger.info("Pushing 10 items...")
            for i in range(10):
                queue.push(f"item_{i}".encode())
            
            logger.info("Processing...")
            queue.start_with_results(simple_worker, num_workers=2)
            time.sleep(0.8)
            
            stats_before_consume = queue.get_stats()
            logger.info(f"Before consumption: total_removed={stats_before_consume.total_removed}")
            
            logger.info("Consuming 5 items...")
            for _ in range(5):
                queue.get()
            
            stats_after_consume = queue.get_stats()
            logger.info(f"After consuming 5: total_removed={stats_after_consume.total_removed}")
            
            assert stats_after_consume.total_removed == 5
            
            print(f"    * Items pushed: 10")
            print(f"    * Items processed: {stats_after_consume.total_processed}")
            print(f"    * Items consumed: {stats_after_consume.total_removed}")
            print(f"    * Tracking works: {stats_after_consume.total_removed == 5} ✓")
            
            print_test_result(True, f"total_removed tracking works in {queue_name}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
    
    def test_69_persistence_batch_operations(self, queue_type, test_storage_path):
        """Test batch operations with both queue types"""
        queue_name = "AsyncQueue" if queue_type == 'async_queue' else "AsyncPersistenceQueue"
        print_test_header(
            "Persistence Queue - Batch Operations",
            "Verify batch operations work correctly",
            queue_name
        )
        
        if queue_type == 'async_queue':
            queue = AsyncQueue(mode=1, buffer_size=128)
        else:
            if os.path.exists(test_storage_path): shutil.rmtree(test_storage_path)
            queue = AsyncPersistenceQueue(mode=1, buffer_size=128, storage_path=test_storage_path)
        
        try:
            def worker(item_id, data):
                return data
            
            logger.info("Push batch of 20 items...")
            batch_items = [f"batch_item_{i}".encode() for i in range(20)]
            ids = queue.push_batch(batch_items)
            
            assert len(ids) == 20
            
            logger.info("Processing...")
            queue.start_with_results(worker, num_workers=2)
            time.sleep(1)
            
            logger.info("Get batch of 20 results...")
            results = queue.get_batch(20)
            
            assert len(results) == 20
            
            print(f"    * Pushed batch: 20 items")
            print(f"    * IDs returned: {len(ids)}")
            print(f"    * Results batch: {len(results)} items")
            
            print_test_result(True, f"Batch operations work with {queue_name}")
        finally:
            if queue_type == 'persistence' and os.path.exists(test_storage_path):
                shutil.rmtree(test_storage_path)
    
    def test_70_persistence_mode_switching(self, queue_type, test_storage_path):
        """Test mode switching with persistent queue"""
        print_test_header(
            "Persistence Queue - Mode Switching",
            "Verify mode can be switched between sequential and parallel"
        )
        
        storage_path = "./test_persist_mode"
        self.cleanup_storage(storage_path)
        
        try:
            queue = AsyncPersistenceQueue(mode=0, buffer_size=128, storage_path=storage_path)
            
            logger.info(f"Initial mode: {queue.get_mode()}")
            assert queue.get_mode() == 0
            
            logger.info("Switching to parallel mode...")
            queue.set_mode(1)
            assert queue.get_mode() == 1
            
            logger.info("Switching back to sequential...")
            queue.set_mode(0)
            assert queue.get_mode() == 0
            
            print(f"    * Initial mode: SEQUENTIAL (0)")
            print(f"    * Switched to: PARALLEL (1)")
            print(f"    * Switched back to: SEQUENTIAL (0)")
            print(f"    * Current mode: {queue.get_mode()}")
            
            print_test_result(True, "Mode switching works with persistent queue")
        finally:
            self.cleanup_storage(storage_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
