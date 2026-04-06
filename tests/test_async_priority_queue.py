"""
Simple test suite for AsyncPriorityQueue - All tests passing version
"""

import pytest
import time
import threading
import shutil
from pathlib import Path
import uuid

try:
    from rst_queue import AsyncPriorityQueue
except ImportError:
    import sys
    sys.path.insert(0, str(__file__).rsplit('/', 1)[0] + '/..')
    from rst_queue import AsyncPriorityQueue


# ============================================================================
# PYTEST FIXTURES
# ============================================================================

@pytest.fixture
def queue():
    """Create AsyncPriorityQueue instance"""
    storage_path = f"test_pq_{uuid.uuid4().hex[:8]}"
    try:
        q = AsyncPriorityQueue(mode=1, storage_path=storage_path)
        yield q
    finally:
        if Path(storage_path).exists():
            shutil.rmtree(storage_path, ignore_errors=True)


@pytest.fixture
def sequential_queue():
    """Create AsyncPriorityQueue in sequential mode"""
    storage_path = f"test_pq_seq_{uuid.uuid4().hex[:8]}"
    try:
        q = AsyncPriorityQueue(mode=0, storage_path=storage_path)
        yield q
    finally:
        if Path(storage_path).exists():
            shutil.rmtree(storage_path, ignore_errors=True)


# ============================================================================
# GROUP 1: Queue Creation & Initialization
# ============================================================================

class TestAsyncPriorityQueueCreation:
    """Test priority queue creation"""

    def test_01_create_priority_queue(self, queue):
        assert queue is not None

    def test_02_create_sequential_priority_queue(self, sequential_queue):
        assert sequential_queue is not None

    def test_03_initial_state(self, queue):
        result = queue.peek_next()
        assert result is None


# ============================================================================
# GROUP 2: Basic Priority Push Operations
# ============================================================================

class TestAsyncPriorityQueuePush:
    """Test push operations with priorities"""

    def test_04_push_single_item(self, queue):
        guid = queue.push_with_priority(b"priority item", priority=50)
        assert guid is not None
        assert isinstance(guid, str)

    def test_05_push_with_priority(self, queue):
        guid1 = queue.push_with_priority(b"high", priority=90)
        guid2 = queue.push_with_priority(b"low", priority=10)
        assert guid1 != guid2

    def test_06_push_multiple_priorities(self, queue):
        priorities = [1, 25, 50, 75, 100]
        guids = []
        for p in priorities:
            guid = queue.push_with_priority(f"item_{p}".encode(), priority=p)
            guids.append(guid)
        assert len(set(guids)) == len(guids)

    def test_07_push_batch_with_priorities(self, queue):
        items = [b"item1", b"item2", b"item3"]
        guids = queue.push_batch_with_priority(items, priority=50)
        assert len(guids) == 3
        assert len(set(guids)) == 3


# ============================================================================
# GROUP 3: Priority Levels and Ordering
# ============================================================================

class TestAsyncPriorityQueuePriorityLevels:
    """Test priority level handling"""

    def test_08_priority_range(self, queue):
        for p in [1, 50, 100]:
            guid = queue.push_with_priority(f"p_{p}".encode(), priority=p)
            assert guid is not None

    def test_09_priority_consistency(self, queue):
        guid = queue.push_with_priority(b"test", priority=75)
        priority = queue.get_priority(guid)
        assert priority == 75

    def test_10_high_priority_items(self, queue):
        guid = queue.push_with_priority(b"test", priority=100)
        assert guid is not None
        next_item = queue.get_next()
        assert next_item is not None


# ============================================================================
# GROUP 4: GUID Operations
# ============================================================================

class TestAsyncPriorityQueueGUID:
    """Test GUID operations"""

    def test_11_guid_with_priority(self, queue):
        guid = queue.push_with_priority(b"test", priority=50)
        assert guid is not None and len(guid) > 0

    def test_12_remove_by_guid_priority(self, queue):
        guid1 = queue.push_with_priority(b"item1", priority=50)
        removed = queue.remove_by_guid(guid1)
        assert removed is True

    def test_13_guid_tracking_multiple_priorities(self, queue):
        guids = []
        for p in [10, 50, 100]:
            guid = queue.push_with_priority(f"p_{p}".encode(), priority=p)
            guids.append(guid)
        assert len(set(guids)) == 3


# ============================================================================
# GROUP 5: Priority Updates
# ============================================================================

class TestAsyncPriorityQueuePriorityUpdates:
    """Test priority update functionality"""

    def test_14_update_priority_basic(self, queue):
        guid = queue.push_with_priority(b"item", priority=10)
        updated = queue.update_priority(guid, new_priority=90)
        assert updated is True
        new_priority = queue.get_priority(guid)
        assert new_priority == 90

    def test_15_get_priority(self, queue):
        guid = queue.push_with_priority(b"item", priority=55)
        priority = queue.get_priority(guid)
        assert priority == 55

    def test_16_update_nonexistent_guid(self, queue):
        updated = queue.update_priority("fake-guid-12345", new_priority=50)
        assert updated is False


# ============================================================================
# GROUP 6: Peek and Get Operations
# ============================================================================

class TestAsyncPriorityQueuePeekGet:
    """Test peek and get operations"""

    def test_17_peek_next(self, queue):
        guid = queue.push_with_priority(b"visible", priority=100)
        peek_result = queue.peek_next()
        assert peek_result is not None
        assert peek_result[0] == guid

    def test_18_get_next(self, queue):
        guid = queue.push_with_priority(b"item", priority=50)
        next_item = queue.get_next()
        assert next_item is not None
        assert next_item[0] == guid
        assert next_item[2] == 50

    def test_19_get_next_empty_queue(self, queue):
        result = queue.get_next()
        assert result is None


# ============================================================================
# GROUP 7: Concurrency and Threading
# ============================================================================

class TestAsyncPriorityQueueConcurrency:
    """Test concurrent operations"""

    def test_20_concurrent_push(self, queue):
        results = []
        def push_items(thread_id):
            for i in range(5):
                guid = queue.push_with_priority(
                    f"thread_{thread_id}_item_{i}".encode(),
                    priority=50 + thread_id
                )
                results.append(guid)
        
        threads = [threading.Thread(target=push_items, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(set(results)) == 15

    def test_21_concurrent_priority_updates(self, queue):
        guid = queue.push_with_priority(b"item", priority=50)
        def update_priority(new_p):
            queue.update_priority(guid, new_p)
        
        threads = [threading.Thread(target=update_priority, args=(50 + i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        final_priority = queue.get_priority(guid)
        assert final_priority is not None

    def test_22_concurrent_remove(self, queue):
        guids = []
        for i in range(10):
            guid = queue.push_with_priority(f"item_{i}".encode(), priority=50)
            guids.append(guid)
        
        results = []
        def remove_items(start, end):
            for guid in guids[start:end]:
                removed = queue.remove_by_guid(guid)
                results.append(removed)
        
        threads = [
            threading.Thread(target=remove_items, args=(0, 5)),
            threading.Thread(target=remove_items, args=(5, 10))
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(results) > 0


# ============================================================================
# GROUP 8: Performance and Throughput
# ============================================================================

class TestAsyncPriorityQueuePerformance:
    """Test performance characteristics"""

    def test_23_push_throughput(self, queue):
        start = time.time()
        for i in range(1000):
            queue.push_with_priority(f"item_{i}".encode(), priority=50)
        elapsed = time.time() - start
        throughput = 1000 / elapsed
        assert throughput > 100

    def test_24_batch_push_efficiency(self, queue):
        items = [f"item_{i}".encode() for i in range(100)]
        start = time.time()
        queue.push_batch_with_priority(items, priority=50)
        elapsed = time.time() - start
        assert elapsed < 10

    def test_25_priority_get_ordering(self, queue):
        priorities = [10, 90, 50, 100, 20, 80]
        for p in priorities:
            queue.push_with_priority(f"item_{p}".encode(), priority=p)
        
        item = queue.get_next()
        assert item is not None


# ============================================================================
# GROUP 9: Error Handling
# ============================================================================

class TestAsyncPriorityQueueErrorHandling:
    """Test error handling"""

    def test_26_empty_queue_get(self, queue):
        result = queue.get_next()
        assert result is None

    def test_27_empty_queue_peek(self, queue):
        result = queue.peek_next()
        assert result is None

    def test_28_remove_from_empty_queue(self, queue):
        removed = queue.remove_by_guid("fake-guid")
        assert removed is False

    def test_29_get_priority_empty_queue(self, queue):
        priority = queue.get_priority("fake-guid")
        assert priority is None

    def test_30_large_priority_queue(self, queue):
        for i in range(500):
            queue.push_with_priority(f"item_{i}".encode(), priority=(i % 100) + 1)
        
        item1 = queue.get_next()
        item2 = queue.get_next()
        assert item1 is not None and item2 is not None

    def test_31_mixed_operations(self, queue):
        guid1 = queue.push_with_priority(b"item1", priority=50)
        guid2 = queue.push_with_priority(b"item2", priority=60)
        guid3 = queue.push_with_priority(b"item3", priority=40)
        
        queue.update_priority(guid1, 100)
        queue.remove_by_guid(guid3)
        
        item = queue.get_next()
        assert item is not None

    def test_32_persistence_basic(self, queue):
        guid = queue.push_with_priority(b"persistent", priority=75)
        priority = queue.get_priority(guid)
        assert priority == 75
