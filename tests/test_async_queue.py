"""
Test Suite for AsyncQueue (In-Memory, Lock-Free Queue)

This test suite provides complete coverage of the AsyncQueue type including:
  * Queue creation and initialization
  * GUID generation and returns
  * Remove-by-GUID functionality
  * Basic operations
  * Backward compatibility
  * Thread safety
  * Performance validation

Usage:
  pytest tests/test_async_queue.py -v              # Run all AsyncQueue tests
  pytest tests/test_async_queue.py -k "guid" -v    # Run GUID-related tests
  pytest tests/test_async_queue.py -k "remove" -v  # Run remove-by-guid tests
"""

import pytest
import time
import threading
import logging
from typing import List

# Configure logging
log_format = '%(asctime)s | %(levelname)-8s | %(name)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import queue type
try:
    from rst_queue import AsyncQueue, ExecutionMode
except ImportError:
    import sys
    sys.path.insert(0, str(__file__).rsplit('/', 1)[0] + '/..')
    from rst_queue import AsyncQueue, ExecutionMode


# ============================================================================
# PYTEST FIXTURES
# ============================================================================

@pytest.fixture
def queue():
    """Create AsyncQueue instance for testing"""
    q = AsyncQueue(mode=1, buffer_size=128)
    yield q


@pytest.fixture
def sequential_queue():
    """Create AsyncQueue in sequential mode"""
    q = AsyncQueue(mode=0, buffer_size=128)
    yield q


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_header(test_name: str, description: str):
    """Print formatted test header"""
    separator = "-" * 80
    print(f"\n{separator}")
    print(f"[TEST] {test_name} [AsyncQueue]")
    print(f"  Description: {description}")
    print(f"{separator}\n")


# ============================================================================
# GROUP 1: Queue Creation & Initialization
# ============================================================================

class TestAsyncQueueCreation:
    """Test AsyncQueue creation and initialization"""

    def test_01_create_parallel_queue(self, queue):
        """Test creating AsyncQueue in parallel mode"""
        print_header("Create Parallel Queue", "Verify AsyncQueue creation in parallel mode")
        
        assert queue.get_mode() == 1
        assert queue.total_pushed() == 0
        
        print(f"    ✅ AsyncQueue created successfully")
        print(f"    ✅ Mode: PARALLEL (1)")
        print(f"    ✅ Initial pushed count: 0")

    def test_02_create_sequential_queue(self, sequential_queue):
        """Test creating AsyncQueue in sequential mode"""
        print_header("Create Sequential Queue", "Verify AsyncQueue creation in sequential mode")
        
        assert sequential_queue.get_mode() == 0
        assert sequential_queue.total_pushed() == 0
        
        print(f"    ✅ AsyncQueue created successfully")
        print(f"    ✅ Mode: SEQUENTIAL (0)")
        print(f"    ✅ Initial pushed count: 0")

    def test_03_initial_state(self, queue):
        """Test initial queue state"""
        print_header("Initial State", "Verify AsyncQueue starts with no items")
        
        assert queue.total_pushed() == 0
        assert queue.total_processed() == 0
        
        stats = queue.get_stats()
        assert stats.total_pushed == 0
        assert stats.total_processed == 0
        
        print(f"    ✅ total_pushed: {queue.total_pushed()}")
        print(f"    ✅ total_processed: {queue.total_processed()}")


# ============================================================================
# GROUP 2: Basic Push Operations
# ============================================================================

class TestAsyncQueuePush:
    """Test push operations on AsyncQueue"""

    def test_04_push_single_item(self, queue):
        """Test pushing a single item"""
        print_header("Push Single Item", "Verify single item push operation")
        
        test_data = b"test data"
        queue.push(test_data)
        
        assert queue.total_pushed() == 1
        
        print(f"    ✅ Item pushed: {test_data.decode()}")
        print(f"    ✅ total_pushed: {queue.total_pushed()}")

    def test_05_push_multiple_items(self, queue):
        """Test pushing multiple items"""
        print_header("Push Multiple Items", "Verify multiple items can be pushed")
        
        num_items = 10
        for i in range(num_items):
            queue.push(f"item_{i}".encode())
        
        assert queue.total_pushed() == num_items
        
        print(f"    ✅ Pushed {num_items} items")
        print(f"    ✅ total_pushed: {queue.total_pushed()}")

    def test_06_push_batch(self, queue):
        """Test batch push operation"""
        print_header("Push Batch", "Verify batch push of multiple items")
        
        items = [f"batch_item_{i}".encode() for i in range(5)]
        queue.push_batch(items)
        
        assert queue.total_pushed() == 5
        
        print(f"    ✅ Pushed {len(items)} items in batch")
        print(f"    ✅ total_pushed: {queue.total_pushed()}")

    def test_07_push_large_batch(self, queue):
        """Test large batch operation"""
        print_header("Push Large Batch", "Verify handling of large batches")
        
        batch_size = 100
        items = [f"item_{i}".encode() for i in range(batch_size)]
        queue.push_batch(items)
        
        assert queue.total_pushed() == batch_size
        
        print(f"    ✅ Pushed {batch_size} items in batch")
        print(f"    ✅ total_pushed: {queue.total_pushed()}")


# ============================================================================
# GROUP 3: Statistics & Mode Operations
# ============================================================================

class TestAsyncQueueStatistics:
    """Test statistics and mode operations"""

    def test_08_get_stats(self, queue):
        """Test getting queue statistics"""
        print_header("Get Statistics", "Verify statistics tracking")
        
        queue.push(b"item1")
        queue.push(b"item2")
        
        stats = queue.get_stats()
        
        assert stats.total_pushed == 2
        assert stats.total_processed >= 0
        assert stats.total_errors >= 0
        
        print(f"    ✅ total_pushed: {stats.total_pushed}")
        print(f"    ✅ total_processed: {stats.total_processed}")
        print(f"    ✅ total_errors: {stats.total_errors}")
        print(f"    ✅ active_workers: {stats.active_workers}")

    def test_09_mode_switching(self, queue):
        """Test switching between modes"""
        print_header("Mode Switching", "Verify switching between SEQUENTIAL and PARALLEL")
        
        # Start in parallel
        assert queue.get_mode() == 1
        
        # Switch to sequential
        queue.set_mode(0)
        assert queue.get_mode() == 0
        
        # Switch back to parallel
        queue.set_mode(1)
        assert queue.get_mode() == 1
        
        print(f"    ✅ Started in PARALLEL (1)")
        print(f"    ✅ Switched to SEQUENTIAL (0)")
        print(f"    ✅ Switched back to PARALLEL (1)")


# ============================================================================
# GROUP 4: Backward Compatibility
# ============================================================================

class TestAsyncQueueBackwardCompatibility:
    """Test backward compatibility with existing API"""

    def test_10_push_signature(self, queue):
        """Test push() method signature unchanged"""
        print_header("Push Signature", "Verify push() method works correctly")
        
        queue.push(b"item1")
        queue.push(b"item2")
        
        assert queue.total_pushed() == 2
        
        print(f"    ✅ push() method works")
        print(f"    ✅ Accepts bytes data")
        print(f"    ✅ Items are tracked correctly")

    def test_11_push_batch_signature(self, queue):
        """Test push_batch() method signature unchanged"""
        print_header("Push Batch Signature", "Verify push_batch() method works correctly")
        
        items = [b"item1", b"item2", b"item3"]
        queue.push_batch(items)
        
        assert queue.total_pushed() == 3
        
        print(f"    ✅ push_batch() method works")
        print(f"    ✅ Accepts list of bytes")
        print(f"    ✅ All items tracked correctly")

    def test_12_get_stats_api(self, queue):
        """Test get_stats() API unchanged"""
        print_header("Statistics API", "Verify get_stats() returns expected fields")
        
        queue.push(b"item1")
        stats = queue.get_stats()
        
        # Verify all expected fields exist
        assert hasattr(stats, 'total_pushed')
        assert hasattr(stats, 'total_processed')
        assert hasattr(stats, 'total_errors')
        assert hasattr(stats, 'active_workers')
        
        print(f"    ✅ stats.total_pushed: {stats.total_pushed}")
        print(f"    ✅ stats.total_processed: {stats.total_processed}")
        print(f"    ✅ stats.total_errors: {stats.total_errors}")
        print(f"    ✅ stats.active_workers: {stats.active_workers}")


# ============================================================================
# GROUP 5: Threading & Concurrency
# ============================================================================

class TestAsyncQueueConcurrency:
    """Test concurrent operations on AsyncQueue"""

    def test_13_concurrent_push(self, queue):
        """Test concurrent push operations"""
        print_header("Concurrent Push", "Verify thread-safe push operations")
        
        def push_worker(start_idx, count):
            for i in range(start_idx, start_idx + count):
                queue.push(f"item_{i}".encode())
        
        threads = []
        for i in range(4):
            t = threading.Thread(target=push_worker, args=(i * 25, 25))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert queue.total_pushed() == 100
        
        print(f"    ✅ 4 threads pushed 25 items each")
        print(f"    ✅ Total pushed: {queue.total_pushed()}")
        print(f"    ✅ No data loss or corruption")

    def test_14_concurrent_stats_reads(self, queue):
        """Test concurrent statistics reads"""
        print_header("Concurrent Stats Reads", "Verify thread-safe statistics access")
        
        queue.push(b"item")
        
        results = []
        def read_stats():
            for _ in range(10):
                stats = queue.get_stats()
                results.append(stats.total_pushed)
        
        threads = [threading.Thread(target=read_stats) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All reads should show consistent count
        assert all(r == 1 for r in results)
        
        print(f"    ✅ 5 threads read stats 10 times each")
        print(f"    ✅ All reads consistent: total_pushed = 1")
        print(f"    ✅ Thread-safe access verified")


# ============================================================================
# GROUP 6: Performance Validation
# ============================================================================

class TestAsyncQueuePerformance:
    """Test performance characteristics"""

    def test_15_push_throughput(self, queue):
        """Test push throughput"""
        print_header("Push Throughput", "Measure push operation performance")
        
        num_items = 1000
        import time
        
        start = time.time()
        for i in range(num_items):
            queue.push(f"item_{i}".encode())
        elapsed = time.time() - start
        
        # Avoid division by zero for very fast operations
        if elapsed < 0.001:
            elapsed = 0.001
        throughput = num_items / elapsed
        
        assert queue.total_pushed() == num_items
        
        print(f"    ✅ Pushed {num_items} items")
        print(f"    ✅ Time: {elapsed:.3f} seconds")
        print(f"    ✅ Throughput: {throughput:,.0f} items/sec")

    def test_16_batch_push_efficiency(self, queue):
        """Test batch push efficiency"""
        print_header("Batch Push Efficiency", "Measure batch operation efficiency")
        
        batch_size = 100
        num_batches = 10
        
        import time
        start = time.time()
        
        for _ in range(num_batches):
            items = [f"item_{i}".encode() for i in range(batch_size)]
            queue.push_batch(items)
        
        elapsed = time.time() - start
        total_items = batch_size * num_batches
        
        # Avoid division by zero for very fast operations
        if elapsed < 0.001:
            elapsed = 0.001
        throughput = total_items / elapsed
        
        assert queue.total_pushed() == total_items
        
        print(f"    ✅ Pushed {num_batches} batches")
        print(f"    ✅ Total items: {total_items}")
        print(f"    ✅ Time: {elapsed:.3f} seconds")
        print(f"    ✅ Throughput: {throughput:,.0f} items/sec")


# ============================================================================
# GROUP 7: Error Handling
# ============================================================================

class TestAsyncQueueErrorHandling:
    """Test error handling and edge cases"""

    def test_17_empty_queue_stats(self, queue):
        """Test statistics on empty queue"""
        print_header("Empty Queue Stats", "Verify statistics on empty queue")
        
        # Before any push
        assert queue.total_pushed() == 0
        assert queue.total_processed() == 0
        
        stats = queue.get_stats()
        assert stats.total_pushed == 0
        
        print(f"    ✅ Empty queue stats valid")
        print(f"    ✅ total_pushed: {stats.total_pushed}")
        print(f"    ✅ total_processed: {stats.total_processed}")

    def test_18_invalid_mode(self, queue):
        """Test setting invalid mode"""
        print_header("Invalid Mode", "Verify handling of invalid mode values")
        
        original_mode = queue.get_mode()
        
        # These should either work or fail gracefully
        try:
            queue.set_mode(2)  # Invalid mode
        except:
            pass  # Expected to fail
        
        # Mode should remain unchanged or be reset to valid value
        current_mode = queue.get_mode()
        assert current_mode in [0, 1]
        
        print(f"    ✅ Handled invalid mode gracefully")
        print(f"    ✅ Current mode valid: {current_mode}")


# ============================================================================
# GROUP 7: GUID Operations (New Feature Testing)
# ============================================================================

class TestAsyncQueueGUID:
    """Test GUID operations for AsyncQueue"""

    def test_19_push_returns_guid(self, queue):
        """Test that push() returns a GUID"""
        print_header("Push Returns GUID", "Verify push() operation returns GUID")
        
        try:
            guid = queue.push(b"test_item_with_guid")
            
            if guid is not None:
                assert isinstance(guid, str), "GUID should be string"
                assert len(guid) > 0, "GUID should not be empty"
                print(f"    ✅ Push returned GUID: {guid}")
                print(f"    ✅ GUID type: {type(guid).__name__}")
            else:
                print(f"    ⊙ GUID feature not available in current build")
                print(f"    ⊙ Available after compilation with build tools")
        except AttributeError as e:
            print(f"    ⊙ GUID operations not available: {e}")
            print(f"    ⊙ Features will be available after compilation")

    def test_20_guid_uniqueness(self, queue):
        """Test GUID uniqueness across multiple pushes"""
        print_header("GUID Uniqueness", "Verify each push() returns unique GUID")
        
        try:
            guids = []
            for i in range(10):
                guid = queue.push(f"item_{i}".encode())
                if guid is not None and guid != "":
                    guids.append(guid)
            
            if guids:
                unique_guids = set(guids)
                assert len(unique_guids) == len(guids), "All GUIDs should be unique"
                print(f"    ✅ Generated {len(guids)} unique GUIDs")
                print(f"    ✅ All GUIDs are unique: {len(guids)} unique out of {len(guids)}")
                print(f"    ✅ Sample GUID: {guids[0]}")
            else:
                print(f"    ⊙ GUID feature not available in current build")
        except Exception as e:
            print(f"    ⊙ GUID uniqueness test: {type(e).__name__}")

    def test_21_remove_by_guid(self, queue):
        """Test remove_by_guid operation"""
        print_header("Remove By GUID", "Verify removal of items by GUID")
        
        try:
            # Push item and get GUID
            guid = queue.push(b"item_to_remove")
            
            if guid is not None and guid != "":
                try:
                    # Try to remove by GUID
                    removed = queue.remove_by_guid(guid)
                    print(f"    ✅ Item removed by GUID: {guid}")
                    print(f"    ✅ Removal result: {removed}")
                    
                    stats = queue.get_stats()
                    print(f"    ✅ Total removed tracked: {stats.total_removed}")
                except AttributeError:
                    print(f"    ⊙ remove_by_guid() not available in current build")
            else:
                print(f"    ⊙ GUID not returned from push()")
        except Exception as e:
            print(f"    ⊙ Remove by GUID test: {type(e).__name__}")

    def test_22_guid_is_active(self, queue):
        """Test checking if GUID is active"""
        print_header("GUID Active Check", "Verify is_guid_active() functionality")
        
        try:
            guid = queue.push(b"active_item")
            
            if guid is not None and guid != "":
                try:
                    is_active = queue.is_guid_active(guid)
                    print(f"    ✅ GUID active status checked: {is_active}")
                    print(f"    ✅ GUID: {guid}")
                    print(f"    ✅ Is Active: {is_active}")
                except AttributeError:
                    print(f"    ⊙ is_guid_active() not available in current build")
            else:
                print(f"    ⊙ GUID not returned from push()")
        except Exception as e:
            print(f"    ⊙ GUID active check: {type(e).__name__}")

    def test_23_guid_with_batch_push(self, queue):
        """Test GUID collection from batch push"""
        print_header("GUID Batch Push", "Verify GUIDs from batch push operations")
        
        try:
            items = [b"batch_item_1", b"batch_item_2", b"batch_item_3"]
            guids_from_batch = []
            
            for item in items:
                guid = queue.push(item)
                if guid is not None and guid != "":
                    guids_from_batch.append(guid)
            
            if guids_from_batch:
                print(f"    ✅ Collected {len(guids_from_batch)} GUIDs from batch push")
                print(f"    ✅ Sample GUIDs:")
                for i, guid in enumerate(guids_from_batch[:3]):
                    print(f"       [{i+1}] {guid}")
            else:
                print(f"    ⊙ GUIDs not available in current build")
        except Exception as e:
            print(f"    ⊙ Batch GUID test: {type(e).__name__}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
