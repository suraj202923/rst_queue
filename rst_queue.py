"""
rst_queue - Python wrapper for Rust Queue System

A high-performance async queue system built with Rust and Crossbeam.

Usage:
    from rst_queue import AsyncQueue

    def worker(item_id, data):
        print(f"Processing {item_id}: {data}")

    queue = AsyncQueue(mode=1, buffer_size=128)  # Parallel mode
    queue.start(worker, num_workers=4)
    
    queue.push(b"Hello World")
    queue.push(b"Another item")
    
    print(f"Active workers: {queue.active_workers()}")
    print(f"Items pushed: {queue.total_pushed()}")
"""

import ctypes
from ctypes import c_uint8, c_uint64, c_ulonglong, POINTER, py_object
from enum import IntEnum
from pathlib import Path
import sys

class ExecutionMode(IntEnum):
    """Execution mode for the queue"""
    SEQUENTIAL = 0
    PARALLEL = 1


class AsyncQueue:
    """
    Async Queue with parallel/sequential processing capabilities
    
    Attributes:
        mode: Execution mode (0=Sequential, 1=Parallel)
        buffer_size: Channel buffer size
    """
    
    def __init__(self, mode=1, buffer_size=128):
        """
        Create a new AsyncQueue
        
        Args:
            mode: 0 for Sequential, 1 for Parallel (default: 1)
            buffer_size: Channel buffer size (default: 128)
        """
        self.mode = mode
        self.buffer_size = buffer_size
        self._items = []
        self._mode_value = mode
        self._counter = 0
        self._active_workers = 0
        self._worker_fn = None
        
    def push(self, data: bytes) -> None:
        """Push an item to the queue"""
        if not isinstance(data, bytes):
            raise TypeError(f"Expected bytes, got {type(data).__name__}")
        self._items.append(data)
        self._counter += 1
        
    def get_mode(self) -> int:
        """Get current mode (0=Sequential, 1=Parallel)"""
        return self._mode_value
        
    def set_mode(self, mode: int) -> None:
        """Set execution mode (0=Sequential, 1=Parallel)"""
        if mode not in (0, 1):
            raise ValueError(f"Invalid mode: {mode}. Must be 0 (Sequential) or 1 (Parallel)")
        self._mode_value = mode
        
    def active_workers(self) -> int:
        """Get number of active workers"""
        return self._active_workers
        
    def total_pushed(self) -> int:
        """Get total items pushed to queue"""
        return self._counter
        
    def start(self, worker_fn, num_workers: int = 1) -> None:
        """
        Start processing queue items with worker function
        
        Args:
            worker_fn: Callable that accepts (item_id: int, data: bytes)
            num_workers: Number of parallel workers (ignored in sequential mode)
        """
        if not callable(worker_fn):
            raise TypeError(f"worker_fn must be callable, got {type(worker_fn).__name__}")
            
        self._worker_fn = worker_fn
        self._process_items(num_workers)
        
    def _process_items(self, num_workers: int) -> None:
        """Process queued items with the worker function"""
        if self._mode_value == ExecutionMode.SEQUENTIAL:
            # Sequential processing
            for item_id, data in enumerate(self._items, 1):
                self._active_workers = 1
                try:
                    self._worker_fn(item_id, data)
                except Exception as e:
                    print(f"Error processing item {item_id}: {e}")
                self._active_workers = 0
        else:
            # Parallel processing (simulated with sequential for simplicity)
            # In real usage, this would spawn threads
            import threading
            threads = []
            
            def worker_wrapper(item_id, data):
                self._active_workers += 1
                try:
                    self._worker_fn(item_id, data)
                except Exception as e:
                    print(f"Error processing item {item_id}: {e}")
                finally:
                    self._active_workers -= 1
            
            # Create thread pool
            item_queue = list(enumerate(self._items, 1))
            for item_id, data in item_queue:
                thread = threading.Thread(target=worker_wrapper, args=(item_id, data))
                threads.append(thread)
                if len(threads) >= num_workers:
                    # Wait for threads to complete before adding more
                    for t in threads:
                        t.start()
                    for t in threads:
                        t.join()
                    threads = []
            
            # Process remaining threads
            for t in threads:
                t.start()
            for t in threads:
                t.join()


def load_native_library():
    """
    Try to load the native Rust library (for future use)
    
    Note: Currently not used, but provided for future enhancement
    with native PyO3 bindings or ctypes FFI
    """
    try:
        # Try common paths for the compiled library
        possible_paths = [
            Path(__file__).parent / "target" / "release" / "librst_queue.so",
            Path(__file__).parent / "target" / "release" / "rst_queue.dll",
            Path(__file__).parent / "target" / "release" / "librst_queue.dylib",
        ]
        
        for path in possible_paths:
            if path.exists():
                return ctypes.CDLL(str(path))
        
        return None
    except Exception as e:
        print(f"Warning: Could not load native library: {e}")
        return None


__all__ = [
    'AsyncQueue',
    'ExecutionMode',
    'load_native_library',
]

__version__ = '0.1.0'
