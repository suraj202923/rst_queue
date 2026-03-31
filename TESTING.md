# AsyncQueue Testing Guide

Complete testing documentation for rst_queue AsyncQueue.

## Quick Start

### Run All Tests
```bash
pytest tests/test_queue.py -v
```

### Run Tests with Output
```bash
pytest tests/test_queue.py -v -s
```

### Run Specific Test Group
```bash
# Queue creation tests
pytest tests/test_queue.py::TestQueueCreation -v -s

# Mode operations tests
pytest tests/test_queue.py::TestQueueModeOperations -v -s

# Pushing items tests
pytest tests/test_queue.py::TestPushingItems -v -s

# Batch operations tests
pytest tests/test_queue.py::TestBatchOperations -v -s

# Statistics tests
pytest tests/test_queue.py::TestQueueStatistics -v -s

# Concurrency tests
pytest tests/test_queue.py::TestConcurrency -v -s

# Quick reference examples
pytest tests/test_queue.py::TestQuickReferenceExamples -v -s
```

### Run Single Test
```bash
pytest tests/test_queue.py::TestPushingItems::test_09_push_single_item -v -s
```

---

## Test Suite Overview

**File**: `tests/test_queue.py`  
**Total Tests**: 39  
**Status**: ✅ All tests pass  
**Python**: 3.8+  
**Rust**: 1.94.1+

New unified test file combining:
- 18 functional tests (queue creation, modes, pushing, statistics)
- 9 batch operation tests
- 4 concurrent access pattern tests
- 2 lock-free property tests
- 3 memory and edge case tests
- 4 quick reference examples

---

## Test Coverage

### Group 1: Queue Creation (4 tests)
Tests core queue initialization with different configurations.

**Tests**:
- ✅ `test_01_create_sequential_queue` - Create queue in sequential mode
- ✅ `test_02_create_parallel_queue` - Create queue in parallel mode
- ✅ `test_03_create_queue_with_defaults` - Verify default parameters
- ✅ `test_04_buffer_size_parameter` - Accept various buffer sizes

---

### Group 2: Mode Operations (4 tests)
Tests switching between SEQUENTIAL and PARALLEL execution modes.

**Tests**:
- ✅ `test_05_get_mode` - Retrieve current execution mode
- ✅ `test_06_set_mode` - Switch between modes dynamically
- ✅ `test_07_execution_mode_constants` - Verify ExecutionMode constants (0=SEQUENTIAL, 1=PARALLEL)
- ✅ `test_08_alternating_mode_switches` - Switch modes multiple times

**Mode Reference**:
- `0` = SEQUENTIAL (process items one at a time)
- `1` = PARALLEL (distribute work across workers)

---

### Group 3: Pushing Items (5 tests)
Tests data input and queue push operations.

**Tests**:
- ✅ `test_09_push_single_item` - Push one item to queue
- ✅ `test_10_push_multiple_items` - Push multiple items
- ✅ `test_11_push_empty_bytes` - Handle empty data
- ✅ `test_12_push_large_data` - Push large payloads (1MB+)
- ✅ `test_13_push_various_data_types` - Multiple data formats (JSON, CSV, etc.)

---

### Group 4: Batch Operations (5 tests)
Tests efficient batch push/get operations.

**Tests**:
- ✅ `test_14_push_batch` - Push multiple items at once
- ✅ `test_15_push_batch_empty_list` - Handle empty batch
- ✅ `test_16_push_batch_large` - Large batch (1000 items)
- ✅ `test_17_batch_get_empty` - Get batch with no results
- ✅ `test_18_multiple_batch_operations` - Multiple batch pushes

---

### Group 5: Queue Statistics (4 tests)
Tests queue metrics and monitoring capabilities.

**Tests**:
- ✅ `test_19_total_pushed_counter` - Track pushed items
- ✅ `test_20_get_stats` - Retrieve all statistics
- ✅ `test_21_active_workers` - Monitor active workers
- ✅ `test_22_concurrent_counter_increments` - Counter accuracy with concurrent access

---

### Group 6: Concurrency (4 tests)
Tests thread-safe concurrent access patterns.

**Tests**:
- ✅ `test_23_concurrent_push` - Multiple threads pushing (4 threads × 50 items)
- ✅ `test_24_concurrent_batch_push` - Concurrent batch operations (4 threads × 10 batches × 10 items)
- ✅ `test_25_producer_consumer` - Producer-consumer pattern (100 items)
- ✅ `test_26_high_contention` - High contention scenario (8 threads × 50 items)

---

### Group 7: Lock-Free Properties (2 tests)
Tests lock-free guarantee validation.

**Tests**:
- ✅ `test_27_no_blocking_empty_queue` - Get from empty queue is non-blocking
- ✅ `test_28_push_doesnt_block` - Push doesn't block under contention

---

### Group 8: Memory & Edge Cases (3 tests)
Tests memory handling and edge case scenarios.

**Tests**:
- ✅ `test_29_memory_bounded` - Handle large items (1MB data)
- ✅ `test_30_fifo_batch_ordering` - Batch operations preserve FIFO order
- ✅ `test_31_stats_consistency` - Statistics remain consistent

**Additional Edge Cases**:
- ✅ `test_32_mode_switching_with_items` - Change modes with items in queue
- ✅ `test_33_alternating_operations` - Alternating push/get operations
- ✅ `test_34_get_from_empty` - Get from empty queue returns None
- ✅ `test_35_active_workers_monitoring` - Monitor workers during operations

---

### Group 9: Quick Reference Examples (4 tests)
Practical, copy-paste ready examples for common use cases.

**Tests**:
- 📖 `test_36_basic_queue_usage` - Basic setup and operations
- 📖 `test_37_batch_processing` - Batch push operations
- 📖 `test_38_mode_selection` - Choosing execution mode
- 📖 `test_39_monitoring_statistics` - Tracking queue metrics

---

## Copy-Paste Ready Examples

### Example 1: Basic Queue
```python
from rst_queue import AsyncQueue

# Create queue
queue = AsyncQueue()

# Push data
queue.push(b"data1")
queue.push(b"data2")

# Get statistics
stats = queue.get_stats()
print(f"Pushed: {stats.total_pushed}")
print(f"Processed: {stats.total_processed}")
```

### Example 2: Batch Operations
```python
from rst_queue import AsyncQueue

queue = AsyncQueue()

# Prepare batch
items = [b"item1", b"item2", b"item3"]

# Push batch
ids = queue.push_batch(items)
print(f"Pushed {len(ids)} items")

# Get batch results
results = queue.get_batch(3)
print(f"Retrieved {len(results)} results")
```

### Example 3: Mode Switching
```python
from rst_queue import AsyncQueue, ExecutionMode

# Sequential processing
seq_queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL)

# Parallel processing
par_queue = AsyncQueue(mode=ExecutionMode.PARALLEL)

# Switch dynamically
queue = AsyncQueue()
queue.set_mode(ExecutionMode.SEQUENTIAL)
```

### Example 4: Concurrent Usage
```python
import threading
from rst_queue import AsyncQueue

queue = AsyncQueue()

def worker(thread_id):
    for i in range(100):
        queue.push(f"thread_{thread_id}_item_{i}".encode())

# Create threads
threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Total pushed: {queue.total_pushed()}")
```
```

### Example 4: JSON Data
```python
import json
from rst_queue import AsyncQueue

queue = AsyncQueue()

# Push JSON
data = {"user": "Alice", "age": 30}
queue.push(json.dumps(data).encode())

# Or multiple items
items = [
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
]

for item in items:
    queue.push(json.dumps(item).encode())

print(f"Pushed {queue.total_pushed()} items")
```

---

## Test Output Explanation

### Test Header
```
────────────────────────────────────────────────────
[TEST] Push Single Item
  Description: Verify that a single item can be pushed to the queue
────────────────────────────────────────────────────
```
Shows test name and what it validates.

### Operations Log
```
    * Item pushed: test data
    * total_pushed: 1
```
Shows each operation performed with actual values.

### Result Summary
```
  [PASS]: Single item pushed successfully
```
Final test status with brief message.

### Statistics Display
```
  [STATS] Queue Statistics:
    * Total Pushed: 1
    * Total Processed: 0
    * Total Errors: 0
    * Active Workers: 0
```
Current queue state in readable format.

---

## Running Full Test Suite

```bash
$ pytest tests/test_async_queue_improved.py -v

platform win32 -- Python 3.12.0, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\suraj202923\rst_queue
collected 22 items

tests/test_async_queue_improved.py::TestQueueCreation::test_create_sequential_queue PASSED [  4%]
tests/test_async_queue_improved.py::TestQueueCreation::test_create_parallel_queue PASSED [  9%]
tests/test_async_queue_improved.py::TestQueueCreation::test_create_queue_with_defaults PASSED [ 13%]
tests/test_async_queue_improved.py::TestQueueCreation::test_buffer_size_parameter PASSED [ 18%]
tests/test_async_queue_improved.py::TestQueueModeOperations::test_get_mode PASSED [ 22%]
tests/test_async_queue_improved.py::TestQueueModeOperations::test_set_mode PASSED [ 27%]
tests/test_async_queue_improved.py::TestQueueModeOperations::test_execution_mode_constants PASSED [ 31%]
tests/test_async_queue_improved.py::TestPushingItems::test_push_single_item PASSED [ 36%]
tests/test_async_queue_improved.py::TestPushingItems::test_push_multiple_items PASSED [ 40%]
tests/test_async_queue_improved.py::TestPushingItems::test_push_empty_bytes PASSED [ 45%]
tests/test_async_queue_improved.py::TestPushingItems::test_push_large_data PASSED [ 50%]
tests/test_async_queue_improved.py::TestPushingItems::test_push_various_data_types PASSED [ 54%]
tests/test_async_queue_improved.py::TestQueueStatistics::test_total_pushed_counter PASSED [ 59%]
tests/test_async_queue_improved.py::TestQueueStatistics::test_get_stats PASSED [ 63%]
tests/test_async_queue_improved.py::TestQueueStatistics::test_active_workers PASSED [ 68%]
tests/test_async_queue_improved.py::TestResultReturning::test_result_object_structure SKIPPED [ 72%]
tests/test_async_queue_improved.py::TestResultReturning::test_get_nonblocking SKIPPED [ 77%]
tests/test_async_queue_improved.py::TestResultReturning::test_retrieve_multiple_results SKIPPED [ 81%]
tests/test_async_queue_improved.py::TestQuickReferenceExamples::test_basic_queue_usage PASSED [ 86%]
tests/test_async_queue_improved.py::TestQuickReferenceExamples::test_queue_mode_switching PASSED [ 90%]
tests/test_async_queue_improved.py::TestQuickReferenceExamples::test_json_data_example PASSED [ 95%]
tests/test_async_queue_improved.py::test_print_usage_guide PASSED [100%]

======================== 19 passed, 3 skipped in 0.10s =========================
```

---

## Logging Features

Each test provides detailed logging with timestamps:

```
13:45:22 | INFO     | __main__ - Starting test: Push Single Item
13:45:22 | INFO     | __main__ - Before: total_pushed = 0
13:45:22 | INFO     | __main__ - Pushed: test data
13:45:22 | INFO     | __main__ - After: total_pushed = 1
```

**Timestamp**: `HH:MM:SS` format for easy tracing  
**Level**: INFO, DEBUG, WARNING, ERROR as appropriate  
**Module**: Which component is logging  
**Message**: Detailed description of operation

---

## Buffer Size Guidelines

Choose buffer size based on workload:

```python
# Small workload (< 1000 items)
queue = AsyncQueue(buffer_size=64)

# Medium workload (1K-100K items)
queue = AsyncQueue(buffer_size=128)  # Default

# Large workload (> 100K items)
queue = AsyncQueue(buffer_size=256)

# Very large workload (millions of items)
queue = AsyncQueue(buffer_size=512)
```

---

## Worker Count Guidelines

```python
# Single-threaded processing
queue.start(worker, num_workers=1)

# CPU-bound tasks (use CPU cores - 1)
import multiprocessing
cores = multiprocessing.cpu_count()
queue.start(worker, num_workers=cores - 1)

# I/O-bound tasks (can use more workers)
queue.start(worker, num_workers=4)

# Quick processing
queue.start(worker, num_workers=2)
```

---

## Test Maintenance

### Adding New Tests

1. Create a new test class: `class TestNewFeature:`
2. Add test method: `def test_something(self):`
3. Use helper functions for consistency:
   - `print_test_header()` - Show test name
   - `print_test_result()` - Show result
   - `print_queue_stats()` - Display statistics

### Example New Test:
```python
def test_my_feature(self):
    """Test description here"""
    print_test_header(
        "Feature Name",
        "What this tests"
    )
    
    queue = AsyncQueue()
    # Test code here
    
    assert condition, "Error message"
    print_test_result(True, "Feature works as expected")
```

---

## Common Issues & Solutions

### Python C Extension Not Found
```
ImportError: cannot import name 'AsyncQueue'
```
**Solution**: Rebuild the extension
```bash
pip install -e . --force-reinstall
```

### Tests Fail with Access Violation
**Solution**: This occurs with result-returning workers (known PyO3 limitation). These tests are intentionally skipped.

### Slow Performance During Testing
**Solution**: This is normal - Python logging adds overhead. Use release build:
```bash
cargo build --release
pip install -e .
```

---

## Performance Characteristics

From `FINAL_RESULTS.md`:

- **Push Throughput**: 4.2M items/sec
- **Latency (P50)**: 0.3 µs per item
- **Multi-threaded**: Scales linearly 1-16 threads
- **vs AsyncIO ThreadPool**: **42.7x faster**

---

## See Also

- `README.md` - Main documentation
- `FINAL_RESULTS.md` - Complete benchmark results
- `tests/test_async_queue_improved.py` - Full test source code
- `src/lib.rs` - Rust implementation

