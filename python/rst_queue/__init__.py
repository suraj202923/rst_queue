"""
rst_queue - High-Performance Async Queue

A high-performance async queue system built with Rust and Crossbeam,
with native Python support via PyO3.

Quick Usage:

    from rst_queue import AsyncQueue, ExecutionMode

    def worker(item_id, data):
        print(f"Processing {item_id}: {data}")

    queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
    queue.push(b"Hello World")
    queue.start(worker, num_workers=4)

    # Get results if using start_with_results
    def result_worker(item_id, data):
        return b"processed: " + data

    queue2 = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
    queue2.push(b"Hello")
    queue2.start_with_results(result_worker, num_workers=4)

    # Retrieve result
    result = queue2.get_blocking()
    print(f"Result: {result.result}")
"""

__version__ = "0.1.8"
__author__ = "Suraj Kalbande"
__email__ = "suraj202923@gmail.com"
__license__ = "MIT"

from enum import IntEnum
import warnings

# Try to import the compiled Rust module
try:
    from rst_queue._rst_queue import (
        PyAsyncQueue,
        PyAsyncPersistenceQueue,
        PyQueueStats,
        PyProcessedResult,
    )
    
    # Try to import AsyncPriorityQueue if available
    try:
        from rst_queue._rst_queue import PyAsyncPriorityQueue
        AsyncPriorityQueue = PyAsyncPriorityQueue
    except ImportError:
        # Fall back to mock if not available
        from rst_queue.mock_implementation import AsyncPriorityQueue
    
    # Export with friendly names
    AsyncQueue = PyAsyncQueue
    AsyncPersistenceQueue = PyAsyncPersistenceQueue
    QueueStats = PyQueueStats
    ProcessedResult = PyProcessedResult
    _use_rust = True
except ImportError as e:
    # Fallback to pure Python mock implementation
    warnings.warn(
        "Using pure Python mock implementation. Install from source or use pre-built wheels "
        "for better performance: pip install --upgrade rst_queue",
        RuntimeWarning
    )
    
    from rst_queue.mock_implementation import (
        AsyncQueue,
        AsyncPersistenceQueue,
        AsyncPriorityQueue,
        ExecutionMode,
        Priority,
        QueueStats,
        ProcessedResult,
    )
    _use_rust = False


class ExecutionMode(IntEnum):
    """Execution mode for queue processing
    
    SEQUENTIAL (0): Process items one at a time
    PARALLEL (1): Process items in parallel using multiple workers
    """
    SEQUENTIAL = 0
    PARALLEL = 1


class Priority(IntEnum):
    """Priority levels for queue processing
    
    HIGH (2): High priority, processed first
    NORMAL (1): Normal priority (default)
    LOW (0): Low priority, processed last
    """
    HIGH = 2
    NORMAL = 1
    LOW = 0


__all__ = [
    "AsyncQueue",
    "AsyncPersistenceQueue",
    "AsyncPriorityQueue",
    "ExecutionMode",
    "Priority",
    "QueueStats",
    "ProcessedResult",
    "__version__",
    "__author__",
]
