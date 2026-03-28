use rst_queue::AsyncQueue;
use std::time::Duration;
use std::thread;
use std::sync::Arc;

fn main() {
    println!("=== Rust Queue System Example ===\n");

    // Sequential execution example
    println!("Sequential Mode:");
    sequential_example();

    thread::sleep(Duration::from_secs(1));

    // Parallel execution example
    println!("\nParallel Mode:");
    parallel_example();
}

fn sequential_example() {
    let mut queue = AsyncQueue::new(0, 128).expect("Failed to create queue");
    
    println!("Mode: {}", queue.get_mode());
    
    // Define a worker function
    let worker = Arc::new(|id: u64, data: Vec<u8>| {
        let message = String::from_utf8_lossy(&data);
        println!("  [Sequential] Processing item {}: {}", id, message);
        thread::sleep(Duration::from_millis(100));
    });
    
    queue.start(worker, 1).expect("Failed to start queue");
    
    // Push items
    for i in 1..=5 {
        let data = format!("Item {}", i).into_bytes();
        queue.push(data).expect("Failed to push");
        println!("Pushed item {}", i);
    }

    // Give time to process
    thread::sleep(Duration::from_secs(2));
    println!("Total items pushed: {}", queue.total_pushed());
}

fn parallel_example() {
    let mut queue = AsyncQueue::new(1, 128).expect("Failed to create queue");
    
    println!("Mode: {}", queue.get_mode());
    
    // Define a worker function
    let worker = Arc::new(|id: u64, data: Vec<u8>| {
        let message = String::from_utf8_lossy(&data);
        println!("  [Parallel] Processing item {}: {}", id, message);
        thread::sleep(Duration::from_millis(100));
    });
    
    queue.start(worker, 4).expect("Failed to start queue");
    
    // Push items
    for i in 1..=10 {
        let data = format!("Item {}", i).into_bytes();
        queue.push(data).expect("Failed to push");
        println!("Pushed item {}", i);
    }

    // Give time to process
    thread::sleep(Duration::from_secs(2));
    println!("Total items pushed: {}", queue.total_pushed());
}
