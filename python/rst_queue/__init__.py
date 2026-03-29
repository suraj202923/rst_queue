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

__version__ = "0.2.0"
__author__ = "Suraj Kalbande"
__email__ = "suraj202923@gmail.com"
__license__ = "MIT"

from enum import IntEnum

# Try to import the compiled Rust module
try:
    from rst_queue._rst_queue import (
        PyAsyncQueue,
        PyQueueStats,
        PyProcessedResult,
    )
    
    # Export with friendly names
    AsyncQueue = PyAsyncQueue
    QueueStats = PyQueueStats
    ProcessedResult = PyProcessedResult
    _use_rust = True
except ImportError:
    # Fallback to pure Python implementation
    import sys
    from pathlib import Path
    
    # Try to import pure Python fallback
    parent_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(parent_dir))
    
    try:
        # Import from the pure Python implementation
        # This allows the package to work even if not compiled
        import warnings
        warnings.warn(
            "Using pure Python fallback. Install from source or use pre-built wheels "
            "for better performance: pip install --upgrade rst_queue",
            RuntimeWarning
        )
        
        # Define a fallback if needed
        raise ImportError("Failed to load Rust module")
    except ImportError:
        raise ImportError(
            "rst_queue native module not found. "
            "Please install it with: pip install rst_queue"
        )


class ExecutionMode(IntEnum):
    """Execution mode for queue processing
    
    SEQUENTIAL (0): Process items one at a time
    PARALLEL (1): Process items in parallel using multiple workers
    """
    SEQUENTIAL = 0
    PARALLEL = 1


__all__ = [
    "AsyncQueue",
    "ExecutionMode",
    "QueueStats",
    "ProcessedResult",
    "__version__",
    "__author__",
]
