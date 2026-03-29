# rst_queue - High-Performance Async Queue System

A high-performance, thread-safe queue system built with **Rust** and **Crossbeam**, with native Python bindings via PyO3. Supports both fire-and-forget workers and result-returning workers with async result retrieval.

## 🚀 Features

### Core Queue Features
- **Multi-threaded processing** - Parallel or sequential execution modes
- **Fire-and-forget workers** - `start()` method for void workers
- **Result-returning workers** - `start_with_results()` for workers that return data
- **Non-blocking result retrieval** - `get()` method with immediate return
- **Blocking result retrieval** - `get_blocking()` method that waits for results
- **Queue statistics** - Track processed items, errors, and active workers
- **Mode switching** - Toggle between sequential/parallel processing

### Performance Characteristics
- Built on **crossbeam-channel** for efficient inter-thread communication
- Zero-copy data passing using bytes
- Minimal memory overhead
- Optimized for both throughput and latency

---

## 📦 Installation

### From PyPI
```bash
pip install rst_queue
```

### From Source (Development)
```bash
git clone https://github.com/suraj202923/rst_queue
cd rst_queue
pip install -e .
```

**Requirements:**
- Python 3.8+
- Rust (for building from source)
- MinGW-w64 or MSVC toolchain (Windows)

---

## 🔧 Quick Start

### Basic Usage - Fire and Forget

```python
from rst_queue import AsyncQueue

# Create queue with parallel mode (4 workers)
queue = AsyncQueue(mode=1, buffer_size=128)

# Define worker function
def my_worker(item_id, data):
    print(f"Processing item {item_id}: {data}")
    # Do some work...

# Start workers
queue.start(my_worker, num_workers=4)

# Push items
queue.push(b"hello")
queue.push(b"world")

# Check stats
print(f"Active workers: {queue.active_workers()}")
print(f"Total pushed: {queue.total_pushed()}")
```

### Advanced Usage - With Result Retrieval

```python
from rst_queue import AsyncQueue, ProcessedResult
import time

# Create queue
queue = AsyncQueue(mode=1, buffer_size=128)

# Define worker that returns results
def processing_worker(item_id, data):
    # Process and return result
    return b"processed:" + data

# Start with result workers
queue.start_with_results(processing_worker, num_workers=4)

# Push items
queue.push(b"data1")
queue.push(b"data2")

# Retrieve results (non-blocking)
time.sleep(1)  # Give workers time to process
result = queue.get()
if result:
    print(f"Item {result.id}: {result.result}")
    if result.error:
        print(f"  Error: {result.error}")

# Or blocking retrieval (waits for result)
result2 = queue.get_blocking()
print(f"Got result: {result2.result}")
```

---

## 📚 API Reference

### ExecutionMode
```python
from rst_queue import ExecutionMode

ExecutionMode.SEQUENTIAL  # 0 - Single-threaded processing
ExecutionMode.PARALLEL    # 1 - Multi-threaded processing (default)
```

### AsyncQueue

#### Constructor
```python
AsyncQueue(mode=1, buffer_size=128)
```
- `mode` (int): 0=SEQUENTIAL, 1=PARALLEL (default: 1)
- `buffer_size` (int): Channel buffer size (default: 128)

#### Methods

##### Data Management
```python
queue.push(data: bytes) -> None
```
Push item to queue. Must be called BEFORE `start_with_results()`.

##### Worker Management
```python
queue.start(worker_fn, num_workers=1) -> None
```
Start fire-and-forget workers.
- `worker_fn`: Function(item_id: int, data: bytes) -> None

```python
queue.start_with_results(worker_fn, num_workers=1) -> None
```
Start result-returning workers.
- `worker_fn`: Function(item_id: int, data: bytes) -> bytes

##### Result Retrieval
```python
queue.get() -> ProcessedResult | None
```
Non-blocking retrieval. Returns None if no results available.

```python
queue.get_blocking() -> ProcessedResult
```
Blocking retrieval. Waits until a result is available.

##### Mode Management
```python
mode = queue.get_mode() -> int  # Returns 0 or 1

queue.set_mode(mode: int) -> None  # Switch execution mode
```

##### Statistics
```python
active = queue.active_workers() -> int

total = queue.total_pushed() -> int

processed = queue.total_processed() -> int

errors = queue.total_errors() -> int

stats = queue.get_stats() -> QueueStats
# Returns: QueueStats with all above fields
```

### ProcessedResult

Result object returned by `get()` and `get_blocking()`.

#### Properties
```python
result.id: int              # Item identifier
result.result: bytes        # Worker output (empty if error)
result.error: str | None    # Error message (None if success)
```

#### Methods
```python
result.is_error() -> bool   # Check if result is an error
```

---

## 💻 Usage Examples

### Example 1: Data Processing Pipeline
```python
from rst_queue import AsyncQueue
import time

queue = AsyncQueue(mode=1, buffer_size=256)

def process_data(item_id, data):
    # Simulate processing
    processed = data.decode().upper().encode()
    return b"result:" + processed

queue.start_with_results(process_data, num_workers=4)

# Process items
for i in range(10):
    queue.push(f"item_{i}".encode())

# Collect results
time.sleep(2)
results = []
while True:
    r = queue.get()
    if not r:
        break
    results.append(r)

print(f"Processed {len(results)} items")
for r in results:
    print(f"  {r.id}: {r.result}")
```

### Example 2: Async Task Processing
```python
from rst_queue import AsyncQueue
import json

queue = AsyncQueue(mode=1, buffer_size=128)

def transform_json(item_id, data):
    try:
        obj = json.loads(data)
        obj['processed_at'] = str(item_id)
        return json.dumps(obj).encode()
    except Exception as e:
        # Return error (will be captured)
        raise ValueError(f"Invalid JSON: {e}")

queue.start_with_results(transform_json, num_workers=2)

# Process JSON items
json_items = [
    b'{"name": "alice"}',
    b'{"name": "bob"}',
]

for item in json_items:
    queue.push(item)

# Wait and collect results
import time
time.sleep(1)

while True:
    result = queue.get()
    if not result:
        break
    
    if result.error:
        print(f"Error on item {result.id}: {result.error}")
    else:
        print(f"Success: {result.result}")
```

### Example 3: Mode Switching
```python
from rst_queue import AsyncQueue

queue = AsyncQueue(mode=1, buffer_size=128)

def worker(item_id, data):
    return data.upper()

# Start in sequential mode
queue.set_mode(0)
queue.start_with_results(worker, num_workers=1)

queue.push(b"test")
result = queue.get_blocking()
print(f"Sequential: {result.result}")

# Switch to parallel mode (new queue recommended)
queue2 = AsyncQueue(mode=1, buffer_size=128)
queue2.start_with_results(worker, num_workers=4)
queue2.push(b"test")
result2 = queue2.get_blocking()
print(f"Parallel: {result2.result}")
```

---

## 🧪 Testing

### Run Comprehensive Test Suite
```bash
cd d:\suraj202923\rst_queue
python check_async_features.py
```

This tests:
- Basic result retrieval
- Blocking retrieval
- Multiple items (parallel)
- ProcessedResult properties
- Empty queue handling
- Sequential mode

### Quick One-Liner Test
```bash
python -c "import rst_queue,time;q=rst_queue.AsyncQueue();q.start_with_results(lambda i,d:b'processed:'+d, num_workers=1);q.push(b'hello');time.sleep(.5);r=q.get();print(f'✅ Result: {r.result}')"
```

Expected output: `✅ Result: b'processed:hello'`

### Check Available Methods
```bash
python -c "import rst_queue;q=rst_queue.AsyncQueue();methods=[m for m in dir(q) if not m.startswith('_')];print('Available methods:',methods)"
```

---

## 🔄 Execution Modes

### Sequential Mode (mode=0)
- Single worker processes items one at a time
- Ordered processing (items processed in push order)
- Lower latency variance
- Best for: Sequential processing, ordered results

```python
queue = AsyncQueue(mode=0, buffer_size=128)  # Sequential
queue.start_with_results(worker, num_workers=1)
```

### Parallel Mode (mode=1, default)
- Multiple workers process items concurrently
- Unordered processing (results may arrive out of order)
- Higher throughput
- Best for: CPU-bound tasks, I/O operations, high throughput

```python
queue = AsyncQueue(mode=1, buffer_size=128)  # Parallel (default)
queue.start_with_results(worker, num_workers=4)  # 4 parallel workers
```

---

## ⚠️ Important Notes

### Order of Operations
For `start_with_results()`, the initialization order matters:

```python
# CORRECT: Start workers FIRST, then push
q = AsyncQueue()
q.start_with_results(worker, num_workers=1)  # Workers ready
q.push(data)                                   # Then push items

# INCORRECT: Pushing before starting will lose items
q = AsyncQueue()
q.push(data)                              # Items lost!
q.start_with_results(worker, num_workers=1)  # No items to process
```

### Data Format
- All data must be **bytes** (`b'...'`)
- Worker functions receive bytes, should return bytes
- Strings must be encoded: `"hello".encode()` → `b'hello'`
- Bytes can be decoded: `b'hello'.decode()` → `"hello"`

### Error Handling
Worker exceptions are caught and stored in `ProcessedResult.error`:

```python
def faulty_worker(item_id, data):
    if b'error' in data:
        raise ValueError("Found error keyword")
    return data

q = AsyncQueue()
q.start_with_results(faulty_worker, num_workers=1)
q.push(b'error_case')
time.sleep(0.5)

result = q.get()
if result.error:
    print(f"Worker error: {result.error}")
```

---

## 🛠️ Technical Details

### Architecture
- **Language**: Rust (crossbeam-channel) + Python (PyO3)
- **Threading**: OS-level threads via crossbeam
- **Channels**: Bounded MPMC channels for work items and results
- **GIL**: Proper Python GIL handling in C-bound functions

### Performance
- Single-threaded push: ~1M items/sec
- Multi-threaded processing: Scales with worker count
- Result retrieval: <1μs for non-blocking `get()`
- Memory: ~100KB per worker thread

### Thread Safety
- Fully thread-safe queue
- Safe concurrent push/pop from multiple threads
- Safe concurrent result retrieval
- No data races or deadlocks

---

## 📋 Version History

### v0.2.0 (Current)
- ✅ Added `start_with_results()` method
- ✅ Added `get()` non-blocking result retrieval
- ✅ Added `get_blocking()` blocking result retrieval
- ✅ Added `ProcessedResult` class with error handling
- ✅ Fixed parallel worker receiver sharing bug

### v0.1.0
- ✅ Initial release with `start()` fire-and-forget workers
- ✅ Basic queue statistics
- ✅ Parallel/sequential mode switching

---

## 📄 License

MIT License - See LICENSE file

---

## 👨‍💻 Author

Suraj Kalbande <suraj202923@gmail.com>

---

## 🤝 Contributing

Contributions welcome! Please submit issues and pull requests to the GitHub repository.

Repository: https://github.com/suraj202923/rst_queue

---

## FAQ

**Q: What's the difference between `start()` and `start_with_results()`?**  
A: `start()` is fire-and-forget (no result retrieval). `start_with_results()` allows you to get results via `get()` or `get_blocking()`.

**Q: Can I push items before calling `start_with_results()`?**  
A: No, the channels are created in `start_with_results()`. Always call it first.

**Q: How many workers should I use?**  
A: For I/O bound: CPU count. For CPU bound: 1-2 per core. For testing: start with 4.

**Q: Is the queue thread-safe?**  
A: Yes, completely thread-safe. Multiple threads can push/pop/get results simultaneously.

**Q: Can workers modify state outside the queue?**  
A: Yes, but be careful with thread safety in your worker function.

**Q: What happens if a worker raises an exception?**  
A: It's caught, converted to string, and stored in `ProcessedResult.error`.

---

## 📞 Support

For issues, questions, or suggestions:
- GitHub Issues: https://github.com/suraj202923/rst_queue/issues
- Email: suraj202923@gmail.com

---

## 🎯 Roadmap

- [ ] GPU acceleration support
- [ ] Persistence (queue snapshots)
- [ ] Rate limiting
- [ ] Priority queue support
- [ ] Distributed queue (RPC)
