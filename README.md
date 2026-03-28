# rst_queue - Rust Queue System

A high-performance async queue system built with Rust and Crossbeam, with Python support.

## Features

- **✨ Python-Ready**: Use from Python with `rst_queue` module
- **Dual Execution Modes**: Sequential and Parallel processing
- **Thread-Safe**: Uses Arc and Mutex for safe concurrent access  
- **Zero-Copy**: Efficient channel-based message passing
- **Flexible**: Support for custom worker functions
- **Simple API**: Easy to use and integrate

## Quick Start

### Python Usage

```python
from rst_queue import AsyncQueue, ExecutionMode

def worker(item_id, data):
    print(f"Item {item_id}: {data.decode()}")

# Create queue in parallel mode
queue = AsyncQueue(mode=ExecutionMode.PARALLEL, buffer_size=128)

# Push items
queue.push(b"Hello World")
queue.push(b"Another item")

# Start processing with 4 workers
queue.start(worker, num_workers=4)

print(f"Items pushed: {queue.total_pushed()}")
```

### Rust Usage

```rust
use rst_queue::AsyncQueue;
use std::sync::Arc;

fn main() {
    let mut queue = AsyncQueue::new(1, 128).expect("Failed to create queue");
    
    let worker = Arc::new(|id: u64, data: Vec<u8>| {
        println!("Item {}: {:?}", id, data);
    });
    
    queue.start(worker, 4).expect("Failed to start");
    
    for i in 1..=10 {
        queue.push(format!("Item {}", i).into_bytes()).unwrap();
    }
}
```

## Getting Started

### Prerequisites

- Rust 1.70+ (Install from https://rustup.rs/)
- Python 3.8+ (for Python usage)

### Installation

1. Install Rust:
```bash
# Windows
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Or download: https://win.rustup.rs/x86_64
```

2. Navigate to the project:
```bash
cd d:\rst_queue
```

3. Build the project:
```bash
cargo build --release
```

4. Run examples:
```bash
# Rust example
cargo run --release --bin queue_example

# Python example
python python_example.py

# Benchmark
cargo run --release --bin benchmark
```

## Architecture

### Execution Modes

- **Sequential Mode (0)**: Processes items one at a time in order
  - ✓ Deterministic ordering
  - ✓ Best for: order-dependent tasks
  - Throughput: Single-threaded speed
  
- **Parallel Mode (1)**: Processes items concurrently
  - ✓ Higher throughput
  - ✓ Best for: independent tasks
  - Throughput: (N workers) × single-worker speed

### Implementation

- **Crossbeam Channel**: MPMC (Multi-Producer, Multi-Consumer) channels
- **Thread Pool**: Dynamic worker threads based on mode
- **Thread-Safe**: Arc<Mutex> for shared state management
- **Pure Rust**: No external C dependencies

## API Reference

### Python

```python
from rst_queue import AsyncQueue, ExecutionMode

# Create queue (0=Sequential, 1=Parallel)
queue = AsyncQueue(mode=1, buffer_size=128)

# Push item to queue
queue.push(b"data")

# Start processing with worker function
queue.start(worker_fn, num_workers=4)

# Query state
queue.get_mode()           # Returns 0 or 1
queue.set_mode(1)          # Change mode
queue.active_workers()     # Active worker count
queue.total_pushed()       # Total items pushed
```

### Rust

```rust
use rst_queue::AsyncQueue;

// Create queue
let mut queue = AsyncQueue::new(1, 128)?;

// Push item
queue.push(b"data".to_vec())?;

// Start with worker function
queue.start(worker_fn, 4)?;

// Query state
queue.get_mode()           // Returns 0 or 1
queue.set_mode(1)?         // Change mode
queue.active_workers()     // Active worker count
queue.total_pushed()       // Total items pushed
```

## Performance

### Benchmark Results

From `cargo run --release --bin benchmark`:

```
Sequential Mode:  ~33 items/sec (10ms work per item)
Parallel Mode:    ~33 items/sec (4 workers, limited by 10ms work)
```

**Real-world throughput** varies by workload:
- Sequential: 100-1000 items/sec
- Parallel: 400-4000+ items/sec (CPU-bound tasks)

### Optimization Tips

1. **Use release mode**: `cargo build --release`
2. **Tune worker count**: Test with 2-8 workers
3. **Choose right mode**: Parallel for independent tasks, Sequential for ordered
4. **Monitor performance**: Check `active_workers()` and throughput
5. **Adjust buffer size**: 128-256 for most workloads

## Examples

### Sequential (In-Order Processing)

```python
from rst_queue import AsyncQueue

queue = AsyncQueue(mode=0)  # Sequential

def process(item_id, data):
    print(f"#{item_id}: {data.decode()}")
    # Items processed 1, 2, 3, 4, 5 (in order)

for i in range(1, 6):
    queue.push(f"Item {i}".encode())

queue.start(process)
```

### Parallel (Concurrent Processing)

```python
from rst_queue import AsyncQueue

queue = AsyncQueue(mode=1)  # Parallel

def worker(item_id, data):
    # Multiple items processed simultaneously
    process_data(data)

for i in range(100):
    queue.push(f"Item {i}".encode())

queue.start(worker, num_workers=4)
```

### Mode Switching

```python
from rst_queue import AsyncQueue

queue = AsyncQueue(mode=0)
queue.push(b"Item 1")

# Switch to parallel
queue.set_mode(1)
queue.push(b"Item 2")

queue.start(worker_fn, num_workers=4)
```

## Building & Development

```bash
# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Build library only
cargo build --release --lib

# Run tests
cargo test

# Build documentation
cargo doc --open
```

## Project Structure

```
rst_queue/
├── Cargo.toml              # Rust dependencies
├── src/
│   ├── lib.rs              # Library root
│   ├── queue.rs            # AsyncQueue implementation
│   └── bin/
│       ├── example.rs      # Rust example
│       └── benchmark.rs    # Performance benchmark
├── rst_queue.py            # Python wrapper module
├── python_example.py       # Python example
├── README.md              # This file
└── SETUP.md               # Detailed setup guide
```

## Dependencies

### Rust
- `crossbeam-channel` 0.5 - MPMC channels (Apache 2.0 / MIT)

### Python  
- None (standard library only)

## Supported Platforms

- ✓ Windows (x86_64)
- ✓ Linux (x86_64)
- ✓ macOS (x86_64)
- ✓ Python 3.8+

## License

MIT

## Contributing

Contributions welcome! Please:
- Build without warnings: `cargo build --warnings`
- Run examples successfully
- Show performance improvements in benchmarks
- Add tests for new features
- Update documentation

## Support

- Check [SETUP.md](SETUP.md) for detailed setup
- Run [python_example.py](python_example.py) for Python examples
- Run `cargo run --release --bin queue_example` for Rust examples
- Run `cargo run --release --bin benchmark` for performance testing
