# Setup Guide for Rust Queue System

## Step 1: Install Rust

### Windows

Option 1: Download installer
- Visit https://win.rustup.rs/x86_64
- Run the downloaded `rustup-init.exe`
- Follow the prompts

Option 2: PowerShell
```powershell
$ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri https://win.rustup.rs/x86_64 -OutFile rustup-init.exe; .\rustup-init.exe -y
```

### Linux/macOS
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### Verify Installation
```bash
rustc --version
cargo --version
```

## Step 2: Build the Rust Project

Navigate to the project directory:

```bash
cd d:\rust_queue
```

Build in debug mode (faster compilation):

```bash
cargo build
```

Or build in release mode (optimized for performance):

```bash
cargo build --release
```

## Step 3: Run Examples

### Run the Basic Example

```bash
cargo run --release --bin queue_example
```

Expected output:
```
=== Rust Queue System Example ===

Sequential Mode:
Mode: 0
Pushed item 1
...
Total items pushed: 5

Parallel Mode:
Mode: 1
Pushed item 1
...
Total items pushed: 10
```

### Run the Benchmark

```bash
cargo run --release --bin benchmark
```

This will show throughput comparison between sequential and parallel modes.

## Step 4: Verify Everything Works

All examples should complete without errors and show performance metrics.

## Project Structure

```
rust_queue/
├── Cargo.toml           # Dependencies: crossbeam-channel
├── src/
│   ├── lib.rs           # Library root (exports AsyncQueue)
│   ├── queue.rs         # Main AsyncQueue implementation
│   └── bin/
│       ├── example.rs   # Interactive example (demonstrates both modes)
│       └── benchmark.rs # Performance benchmark (100 items each mode)
├── README.md           # Full documentation
└── SETUP.md            # This file
```

## Features

### Sequential Mode (mode=0)
- Processes items one at a time
- Items processed in the order they were pushed
- Single worker thread
- Deterministic ordering
- Best for: Order-dependent tasks, debugging

### Parallel Mode (mode=1)
- Processes items concurrently
- Multiple worker threads (configurable)
- Independent item processing
- Higher throughput
- Best for: Independent tasks, high-volume processing

## Usage Examples

### Rust (Pure)

```rust
use rust_queue::AsyncQueue;
use std::sync::Arc;
use std::thread;
use std::time::Duration;

fn main() {
    // Parallel mode with 4 workers
    let mut queue = AsyncQueue::new(1, 128).unwrap();
    
    let worker = Arc::new(|id: u64, data: Vec<u8>| {
        println!("Item {}: {:?}", id, data);
    });
    
    queue.start(worker, 4).unwrap();
    
    // Push items
    for i in 0..100 {
        queue.push(format!("Item {}", i).into_bytes()).unwrap();
    }
    
    thread::sleep(Duration::from_secs(2));
}
```

## Common Issues

### "cargo not found"
- Ensure Rust is installed and PATH is updated
- Restart PowerShell/terminal after installation
- On Windows: Check that `C:\Users\<username>\.cargo\bin` is in PATH

### Build fails with errors
- Try cleaning: `cargo clean`
- Update Rust: `rustup update`
- Check Rust version: `rustc --version` (should be 1.70+)

### Performance not as expected
- Use release mode: `cargo build --release`
- Increase buffer size when creating queue
- Ensure workers don't block each other
- Check system resources (CPU, memory)

## Performance Tips

1. **Use release mode** for benchmarks: `cargo build --release`
2. **Adjust worker count** based on CPU cores: typically 2-4 per core
3. **Buffer size** affects memory usage - use 128-256 for most cases
4. **Sequential mode** best for dependent tasks
5. **Parallel mode** best for independent, quick tasks

## Next Steps

1. ✅ Install Rust
2. ✅ Clone/extract this project
3. ✅ Run `cargo build --release`
4. ✅ Run the examples
5. ✅ Modify the worker function for your use case
6. ✅ Benchmark with your actual workload

## Dependencies

- **crossbeam-channel** (0.5.x): Multi-producer, multi-consumer MPMC channels
  - No unsafe code required
  - Efficient, battle-tested implementation
  - Used by tokio and other Rust async libraries

## API Reference

### AsyncQueue Methods

```rust
// Create a new queue
pub fn new(mode: u8, buffer_size: usize) -> Result<Self, String>

// Start processing with worker function
pub fn start(&mut self, worker: WorkerFn, num_workers: usize) -> Result<(), String>

// Push item to queue
pub fn push(&self, data: Vec<u8>) -> Result<(), String>

// Get current mode (0 = sequential, 1 = parallel)
pub fn get_mode(&self) -> u8

// Change execution mode
pub fn set_mode(&self, mode: u8) -> Result<(), String>

// Get active worker count
pub fn active_workers(&self) -> usize

// Get total items pushed
pub fn total_pushed(&self) -> u64
```

## Testing

Run tests:
```bash
cargo test
```

Run with logging:
```bash
RUST_LOG=debug cargo run --release --bin queue_example
```

## Building Documentation

Generate and view documentation:
```bash
cargo doc --open
```

## Support

For issues:
1. Check the README.md
2. Review examples in src/bin/
3. Run the benchmark to verify setup
4. Check Rust/Cargo versions match requirements
