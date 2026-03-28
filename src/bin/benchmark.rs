use rst_queue::AsyncQueue;
use std::time::{Duration, Instant};
use std::thread;
use std::sync::Arc;

fn main() {
    println!("=== Rust Queue System Benchmark ===\n");

    // Benchmark sequential mode
    println!("📊 Sequential Mode Benchmark:");
    benchmark_sequential();

    thread::sleep(Duration::from_secs(1));

    // Benchmark parallel mode
    println!("\n📊 Parallel Mode Benchmark:");
    benchmark_parallel();

    println!("\n✅ Benchmarks complete!");
}

fn benchmark_sequential() {
    let mut queue = AsyncQueue::new(0, 256).expect("Failed to create queue");
    
    println!("Mode: Sequential (0)");
    println!("Processing 100 items...\n");

    let worker = Arc::new(|_id: u64, _data: Vec<u8>| {
        thread::sleep(Duration::from_millis(10));
    });
    
    queue.start(worker, 1).expect("Failed to start");

    let start = Instant::now();

    // Push items
    for i in 1..=100 {
        let data = format!("Item_{:03}", i).into_bytes();
        queue.push(data).expect("Failed to push");
        
        if i % 20 == 0 {
            println!("  Pushed {} items", i);
        }
    }

    // Wait for processing
    thread::sleep(Duration::from_secs(3));

    let elapsed = start.elapsed();
    let total = queue.total_pushed();

    println!("\nResults:");
    println!("  Total items: {}", total);
    println!("  Time elapsed: {:?}", elapsed);
    println!("  Throughput: {:.2} items/sec", 100.0 / elapsed.as_secs_f64());
}

fn benchmark_parallel() {
    let mut queue = AsyncQueue::new(1, 256).expect("Failed to create queue");
    
    println!("Mode: Parallel (1)");
    println!("Processing 100 items with 4 workers...\n");

    let worker = Arc::new(|_id: u64, _data: Vec<u8>| {
        thread::sleep(Duration::from_millis(10));
    });
    
    queue.start(worker, 4).expect("Failed to start");

    let start = Instant::now();

    // Push items
    for i in 1..=100 {
        let data = format!("Item_{:03}", i).into_bytes();
        queue.push(data).expect("Failed to push");
        
        if i % 20 == 0 {
            println!("  Pushed {} items", i);
        }
    }

    // Wait for processing
    thread::sleep(Duration::from_secs(3));

    let elapsed = start.elapsed();
    let total = queue.total_pushed();

    println!("\nResults:");
    println!("  Total items: {}", total);
    println!("  Time elapsed: {:?}", elapsed);
    println!("  Throughput: {:.2} items/sec", 100.0 / elapsed.as_secs_f64());
}
