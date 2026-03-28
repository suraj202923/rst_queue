"""
rst_queue - Complete Python Usage Examples

This file contains 10 practical examples showing how to use rst_queue in real-world scenarios.
Run this file to see all examples: python examples_advanced.py
"""

from rst_queue import AsyncQueue, ExecutionMode
import time
import json


# ============================================================================
# EXAMPLE 1: Basic Sequential Processing
# ============================================================================

def example_1_basic_sequential():
    """Process items one at a time in sequential mode"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Sequential Processing")
    print("="*60)
    
    queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL, buffer_size=128)
    
    def process_item(item_id, data):
        print(f"  Item {item_id}: {data.decode()}")
        time.sleep(0.05)
    
    items = ["First", "Second", "Third"]
    for item in items:
        queue.push(item.encode())
    
    print("Processing items sequentially...")
    queue.start(process_item, num_workers=1)
    print(f"✓ Total processed: {queue.total_pushed()}\n")


# ============================================================================
# EXAMPLE 2: Parallel Processing with Multiple Workers
# ============================================================================

def example_2_parallel_workers():
    """Process multiple items concurrently"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Parallel Processing (4 Workers)")
    print("="*60)
    
    queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
    
    def process_task(item_id, data):
        print(f"  Task {item_id}: {data.decode()}")
        time.sleep(0.1)
    
    tasks = [f"Task-{i}" for i in range(1, 9)]
    for task in tasks:
        queue.push(task.encode())
    
    start = time.time()
    print(f"Processing {len(tasks)} tasks with 4 workers...")
    queue.start(process_task, num_workers=4)
    elapsed = time.time() - start
    
    print(f"✓ Completed in {elapsed:.2f}s\n")


# ============================================================================
# EXAMPLE 3: Processing JSON Data
# ============================================================================

def example_3_json_data():
    """Process structured JSON data"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Processing JSON Data")
    print("="*60)
    
    queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
    
    def process_user(item_id, data):
        user = json.loads(data.decode())
        print(f"  {user['name']}: {user['email']}")
    
    users = [
        {"name": "Alice", "email": "alice@example.com"},
        {"name": "Bob", "email": "bob@example.com"},
        {"name": "Charlie", "email": "charlie@example.com"},
    ]
    
    for user in users:
        queue.push(json.dumps(user).encode())
    
    print("Processing user data...")
    queue.start(process_user, num_workers=2)
    print(f"✓ Processed {queue.total_pushed()} users\n")


# ============================================================================
# EXAMPLE 4: Error Handling in Workers
# ============================================================================

def example_4_error_handling():
    """Safely handle errors in worker functions"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Error Handling")
    print("="*60)
    
    queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
    
    stats = {"success": 0, "failed": 0}
    
    def safe_process(item_id, data):
        try:
            num = int(data.decode())
            if num < 0:
                raise ValueError("Negative not allowed")
            result = num ** 2
            print(f"  {num}² = {result} ✓")
            stats["success"] += 1
        except Exception as e:
            print(f"  Error: {e} ✗")
            stats["failed"] += 1
    
    values = [b"2", b"3", b"-5", b"abc", b"4"]
    for val in values:
        queue.push(val)
    
    print("Processing with error handling...")
    queue.start(safe_process, num_workers=2)
    print(f"✓ Results: {stats['success']} success, {stats['failed']} failed\n")


# ============================================================================
# EXAMPLE 5: Switching between Sequential and Parallel
# ============================================================================

def example_5_mode_switching():
    """Switch between modes dynamically"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Dynamic Mode Switching")
    print("="*60)
    
    queue = AsyncQueue(mode=ExecutionMode.SEQUENTIAL)
    
    def worker(item_id, data):
        mode = "Sequential" if queue.get_mode() == 0 else "Parallel"
        print(f"  [{mode}] Item {item_id}: {data.decode()}")
    
    # Sequential
    queue.push(b"Item 1")
    queue.push(b"Item 2")
    print("Mode: SEQUENTIAL")
    queue.start(worker, num_workers=1)
    
    # Switch to parallel
    queue.set_mode(ExecutionMode.PARALLEL)
    queue.push(b"Item 3")
    queue.push(b"Item 4")
    print("\nMode: PARALLEL")
    queue.start(worker, num_workers=2)
    
    print(f"✓ Total items: {queue.total_pushed()}\n")


# ============================================================================
# EXAMPLE 6: Processing Lines from Text
# ============================================================================

def example_6_text_processing():
    """Process text data line by line"""
    print("\n" + "="*60)
    print("EXAMPLE 6: Text Processing")
    print("="*60)
    
    queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
    
    def analyze_line(item_id, data):
        line = data.decode().strip()
        word_count = len(line.split())
        print(f"  Line {item_id}: {word_count} words")
    
    text_lines = [
        b"Python is a great programming language",
        b"rst_queue makes parallel processing easy",
        b"Process multiple items concurrently",
        b"Fast and efficient",
        b"Easy to use API",
    ]
    
    for line in text_lines:
        queue.push(line)
    
    print("Processing text lines...")
    queue.start(analyze_line, num_workers=3)
    print(f"✓ Processed {queue.total_pushed()} lines\n")


# ============================================================================
# EXAMPLE 7: Benchmark - Sequential vs Parallel Performance
# ============================================================================

def example_7_benchmark():
    """Compare performance between modes"""
    print("\n" + "="*60)
    print("EXAMPLE 7: Sequential vs Parallel Benchmark")
    print("="*60)
    
    def slow_worker(item_id, data):
        time.sleep(0.1)
    
    # Sequential
    q1 = AsyncQueue(mode=ExecutionMode.SEQUENTIAL)
    for i in range(10):
        q1.push(b"item")
    
    print("Sequential (1 worker):")
    start = time.time()
    q1.start(slow_worker, num_workers=1)
    seq_time = time.time() - start
    print(f"  Time: {seq_time:.2f}s")
    
    # Parallel
    q2 = AsyncQueue(mode=ExecutionMode.PARALLEL)
    for i in range(10):
        q2.push(b"item")
    
    print("\nParallel (4 workers):")
    start = time.time()
    q2.start(slow_worker, num_workers=4)
    par_time = time.time() - start
    print(f"  Time: {par_time:.2f}s")
    
    speedup = seq_time / par_time
    print(f"\n✓ Speedup: {speedup:.2f}x faster\n")


# ============================================================================
# EXAMPLE 8: API Request Simulation
# ============================================================================

def example_8_api_requests():
    """Simulate processing API requests"""
    print("\n" + "="*60)
    print("EXAMPLE 8: API Request Processing")
    print("="*60)
    
    queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
    
    def handle_request(item_id, data):
        request = json.loads(data.decode())
        print(f"  [{item_id}] {request['method']} {request['path']}")
        time.sleep(0.05)
    
    requests = [
        {"method": "GET", "path": "/users"},
        {"method": "POST", "path": "/users"},
        {"method": "GET", "path": "/users/1"},
        {"method": "PUT", "path": "/users/1"},
        {"method": "DELETE", "path": "/users/1"},
    ]
    
    for req in requests:
        queue.push(json.dumps(req).encode())
    
    print("Processing API requests...")
    queue.start(handle_request, num_workers=3)
    print(f"✓ Processed {queue.total_pushed()} requests\n")


# ============================================================================
# EXAMPLE 9: Data Transformation Pipeline
# ============================================================================

def example_9_data_transformation():
    """Transform data in a pipeline"""
    print("\n" + "="*60)
    print("EXAMPLE 9: Data Transformation Pipeline")
    print("="*60)
    
    queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
    
    def transform_data(item_id, data):
        # Parse, transform, process
        value = int(data.decode())
        
        # Transformations
        doubled = value * 2
        squared = value ** 2
        cubed = value ** 3
        
        print(f"  {value}: ×2={doubled}, ²={squared}, ³={cubed}")
    
    numbers = [b"2", b"3", b"5", b"7", b"10"]
    for num in numbers:
        queue.push(num)
    
    print("Transforming data...")
    queue.start(transform_data, num_workers=2)
    print(f"✓ Transformed {queue.total_pushed()} items\n")


# ============================================================================
# EXAMPLE 10: Complete Real-World Application
# ============================================================================

def example_10_complete_app():
    """Complete application with multiple features"""
    print("\n" + "="*60)
    print("EXAMPLE 10: Complete Real-World Application")
    print("="*60)
    
    class DataProcessor:
        def __init__(self):
            self.queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)
            self.processed = 0
            self.errors = 0
        
        def process_item(self, item_id, data):
            try:
                record = json.loads(data.decode())
                
                # Validate
                if not record.get("id"):
                    raise ValueError("Missing id")
                
                # Process
                print(f"  [{record['id']}] {record['name']}: {record['value']}")
                self.processed += 1
            except Exception as e:
                print(f"  Error: {e}")
                self.errors += 1
        
        def run(self, data_list):
            for record in data_list:
                self.queue.push(json.dumps(record).encode())
            
            self.queue.start(self.process_item, num_workers=2)
        
        def report(self):
            print(f"\n✓ Summary:")
            print(f"  Processed: {self.processed}")
            print(f"  Errors: {self.errors}")
            print(f"  Total: {self.queue.total_pushed()}")
    
    # Create sample data
    records = [
        {"id": 1, "name": "Product A", "value": 100},
        {"id": 2, "name": "Product B", "value": 200},
        {"id": 3, "name": "Product C", "value": 150},
        {"id": 4, "value": 300},  # Missing name
        {"id": 5, "name": "Product E", "value": 250},
    ]
    
    # Process
    processor = DataProcessor()
    processor.run(records)
    processor.report()
    print()


# ============================================================================
# Main - Run All Examples
# ============================================================================

if __name__ == "__main__":
    examples = [
        ("Basic Sequential", example_1_basic_sequential),
        ("Parallel Workers", example_2_parallel_workers),
        ("JSON Data", example_3_json_data),
        ("Error Handling", example_4_error_handling),
        ("Mode Switching", example_5_mode_switching),
        ("Text Processing", example_6_text_processing),
        ("Benchmark", example_7_benchmark),
        ("API Requests", example_8_api_requests),
        ("Data Transform", example_9_data_transformation),
        ("Complete App", example_10_complete_app),
    ]
    
    print("\n" + "="*60)
    print("rst_queue - Complete Python Examples")
    print("="*60)
    print("\nRunning all examples...")
    
    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"\n✗ Error in {name}: {e}\n")
    
    print("\n" + "="*60)
    print("All examples completed successfully!")
    print("="*60 + "\n")
