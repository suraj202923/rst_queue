"""
Python example of using the rst_queue (Rust Queue) System

To use:
    python python_example.py
"""

import time
from rst_queue import AsyncQueue, ExecutionMode


def worker_function(item_id, data):
    """Example worker function that processes queue items"""
    print(f"[Worker] Processing item {item_id}: {data.decode()}")
    time.sleep(0.05)  # Simulate work


def example_sequential():
    """Example of sequential queue processing"""
    print("=" * 50)
    print("Sequential Mode Example")
    print("=" * 50)
    
    queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL, buffer_size=128)
    
    print(f"Mode: {queue.get_mode()} (Sequential)\n")
    
    # Push items
    print("Pushing items...")
    for i in range(1, 4):
        data = f"Data_{i}".encode()
        queue.push(data)
        print(f"  Pushed: {data}")
    
    print(f"\nStarting workers...")
    queue.start(worker_function, num_workers=1)
    
    print(f"Total items processed: {queue.total_pushed()}\n")


def example_parallel():
    """Example of parallel queue processing"""
    print("=" * 50)
    print("Parallel Mode Example")
    print("=" * 50)
    
    queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
    
    print(f"Mode: {queue.get_mode()} (Parallel)\n")
    
    # Push items
    print("Pushing items...")
    for i in range(1, 6):
        data = f"Data_{i}".encode()
        queue.push(data)
        print(f"  Pushed: {data}")
    
    print(f"\nStarting workers (4 parallel)...")
    queue.start(worker_function, num_workers=4)
    
    print(f"Total items processed: {queue.total_pushed()}\n")


def example_mode_switching():
    """Example of switching between modes"""
    print("=" * 50)
    print("Mode Switching Example")
    print("=" * 50)
    
    queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL, buffer_size=128)
    print(f"Initial mode: {queue.get_mode()}\n")
    
    print("Switching to parallel...")
    queue.set_mode(ExecutionMode.PARALLEL)
    print(f"New mode: {queue.get_mode()}\n")
    
    print("Pushing 3 items and processing...")
    for i in range(1, 4):
        queue.push(f"Item {i}".encode())
    
    queue.start(worker_function, num_workers=2)
    print(f"Total items: {queue.total_pushed()}\n")


if __name__ == "__main__":
    print("\n")
    example_sequential()
    print("\n")
    example_parallel()
    print("\n")
    example_mode_switching()
    print("\nAll examples completed successfully!\n")
