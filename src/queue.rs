use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use crossbeam::queue::SegQueue;

/// Execution mode for the queue
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ExecutionMode {
    /// Process items sequentially, one at a time
    Sequential,
    /// Process items in parallel with work-stealing
    Parallel,
}

impl ExecutionMode {
    /// Convert from integer: 0 = Sequential, 1 = Parallel
    pub fn from_int(val: u8) -> Self {
        match val {
            0 => ExecutionMode::Sequential,
            _ => ExecutionMode::Parallel,
        }
    }

    /// Convert to integer: 0 = Sequential, 1 = Parallel
    pub fn to_int(&self) -> u8 {
        match self {
            ExecutionMode::Sequential => 0,
            ExecutionMode::Parallel => 1,
        }
    }
}

/// Item in the queue
#[derive(Clone, Debug)]
pub struct QueueItem {
    pub id: u64,
    pub data: Vec<u8>,
}

/// Processed result returned from worker
#[derive(Clone, Debug)]
pub struct ProcessedResult {
    pub id: u64,
    pub result: Vec<u8>,
    pub error: Option<String>,
}

/// Worker function type for processing queue items (fire-and-forget)
pub type WorkerFn = Arc<dyn Fn(u64, Vec<u8>) + Send + Sync>;

/// Worker function type that returns results
pub type ResultWorkerFn = Arc<dyn Fn(u64, Vec<u8>) -> Result<Vec<u8>, String> + Send + Sync>;

/// Queue statistics
#[derive(Clone, Debug)]
pub struct QueueStats {
    pub total_pushed: u64,
    pub total_processed: u64,
    pub total_errors: u64,
    pub active_workers: usize,
}

/// Optimized Async Queue with parallel/sequential processing capabilities
/// Uses lock-free SegQueue, atomic counters, and work-stealing parallelism
pub struct AsyncQueue {
    /// Lock-free queue for items
    item_queue: Arc<SegQueue<QueueItem>>,
    /// Lock-free queue for results
    result_queue: Arc<SegQueue<ProcessedResult>>,
    
    /// Atomic counters (wait-free, no locks)
    counter: Arc<AtomicU64>,
    active_workers: Arc<AtomicUsize>,
    processed_count: Arc<AtomicU64>,
    error_count: Arc<AtomicU64>,
    
    /// Execution mode
    mode: Arc<Mutex<ExecutionMode>>,
    
    /// Flag to signal workers to stop
    is_closed: Arc<AtomicUsize>, // Using 1=closed, 0=open
}

/// Result batch for processing multiple items at once
#[derive(Debug)]
struct ResultBatch {
    results: Vec<ProcessedResult>,
}

impl AsyncQueue {
    /// Create a new optimized AsyncQueue
    ///
    /// # Arguments
    ///
    /// * `mode` - 0 for Sequential, 1 for Parallel
    /// * `_buffer_size` - Ignored (SegQueue is unbounded), kept for API compatibility
    ///
    /// # Example
    ///
    /// ```
    /// let queue = AsyncQueue::new(1, 128).expect("Failed to create queue");
    /// ```
    pub fn new(mode: u8, _buffer_size: usize) -> Result<Self, String> {
        let execution_mode = ExecutionMode::from_int(mode);

        Ok(AsyncQueue {
            item_queue: Arc::new(SegQueue::new()),
            result_queue: Arc::new(SegQueue::new()),
            counter: Arc::new(AtomicU64::new(0)),
            active_workers: Arc::new(AtomicUsize::new(0)),
            processed_count: Arc::new(AtomicU64::new(0)),
            error_count: Arc::new(AtomicU64::new(0)),
            mode: Arc::new(Mutex::new(execution_mode)),
            is_closed: Arc::new(AtomicUsize::new(0)),
        })
    }

    /// Push an item to the queue (lock-free)
    pub fn push(&self, data: Vec<u8>) -> Result<(), String> {
        if self.is_closed.load(Ordering::Acquire) != 0 {
            return Err("Queue is closed".to_string());
        }

        let id = self.counter.fetch_add(1, Ordering::AcqRel) + 1;
        let item = QueueItem { id, data };
        self.item_queue.push(item);
        Ok(())
    }

    /// Batch push items for higher throughput
    pub fn push_batch(&self, items: Vec<Vec<u8>>) -> Result<Vec<u64>, String> {
        if self.is_closed.load(Ordering::Acquire) != 0 {
            return Err("Queue is closed".to_string());
        }

        let mut ids = Vec::with_capacity(items.len());
        for data in items {
            let id = self.counter.fetch_add(1, Ordering::AcqRel) + 1;
            self.item_queue.push(QueueItem { id, data });
            ids.push(id);
        }
        Ok(ids)
    }

    /// Get the current mode (0 for Sequential, 1 for Parallel)
    pub fn get_mode(&self) -> u8 {
        self.mode.lock().unwrap().to_int()
    }

    /// Set the execution mode
    pub fn set_mode(&self, mode: u8) -> Result<(), String> {
        *self.mode.lock().unwrap() = ExecutionMode::from_int(mode);
        Ok(())
    }

    /// Get number of active workers
    pub fn active_workers(&self) -> usize {
        self.active_workers.load(Ordering::Acquire)
    }

    /// Get total items pushed to the queue
    pub fn total_pushed(&self) -> u64 {
        self.counter.load(Ordering::Acquire)
    }

    /// Get total items processed
    pub fn total_processed(&self) -> u64 {
        self.processed_count.load(Ordering::Acquire)
    }

    /// Get total errors during processing
    pub fn total_errors(&self) -> u64 {
        self.error_count.load(Ordering::Acquire)
    }

    /// Get queue statistics (lock-free read)
    pub fn get_stats(&self) -> QueueStats {
        QueueStats {
            total_pushed: self.total_pushed(),
            total_processed: self.total_processed(),
            total_errors: self.total_errors(),
            active_workers: self.active_workers(),
        }
    }

    /// Get a processed result from the result queue (non-blocking)
    pub fn get(&self) -> Option<ProcessedResult> {
        self.result_queue.pop()
    }

    /// Get multiple results in batch (non-blocking)
    pub fn get_batch(&self, max_items: usize) -> Vec<ProcessedResult> {
        let mut results = Vec::with_capacity(max_items);
        for _ in 0..max_items {
            match self.result_queue.pop() {
                Some(result) => results.push(result),
                None => break,
            }
        }
        results
    }

    /// Block and get a processed result (uses spin-wait with backoff)
    pub fn get_blocking(&self) -> Result<ProcessedResult, String> {
        let mut backoff = crossbeam::utils::Backoff::new();
        loop {
            if let Some(result) = self.result_queue.pop() {
                return Ok(result);
            }
            backoff.snooze();
        }
    }

    /// Close the queue (prevent new items)
    pub fn close(&self) {
        self.is_closed.store(1, Ordering::Release);
    }

    /// Start the queue with a worker function that returns results
    pub fn start_with_results(&mut self, worker: ResultWorkerFn, num_workers: usize) -> Result<(), String> {
        let mode = self.mode.lock().unwrap().clone();
        let num_workers = optimize_worker_count(num_workers);

        match mode {
            ExecutionMode::Sequential => {
                self.spawn_sequential_workers_with_results(worker, 1)?;
            }
            ExecutionMode::Parallel => {
                self.spawn_parallel_workers_with_results(worker, num_workers)?;
            }
        }

        Ok(())
    }

    /// Start the queue with a fire-and-forget worker function
    pub fn start(&mut self, worker: WorkerFn, num_workers: usize) -> Result<(), String> {
        let mode = self.mode.lock().unwrap().clone();
        let num_workers = optimize_worker_count(num_workers);

        match mode {
            ExecutionMode::Sequential => {
                self.spawn_sequential_workers(worker, 1)?;
            }
            ExecutionMode::Parallel => {
                self.spawn_parallel_workers(worker, num_workers)?;
            }
        }

        Ok(())
    }

    /// Spawn sequential worker thread
    fn spawn_sequential_workers(&self, worker: WorkerFn, _num_workers: usize) -> Result<(), String> {
        let item_queue = Arc::clone(&self.item_queue);
        let active_workers = Arc::clone(&self.active_workers);
        let processed_count = Arc::clone(&self.processed_count);

        std::thread::spawn(move || {
            loop {
                match item_queue.pop() {
                    None => {
                        std::thread::sleep(std::time::Duration::from_micros(100));
                        continue;
                    }
                    Some(item) => {
                        active_workers.fetch_add(1, Ordering::AcqRel);
                        worker(item.id, item.data);
                        processed_count.fetch_add(1, Ordering::AcqRel);
                        active_workers.fetch_sub(1, Ordering::AcqRel);
                    }
                }
            }
        });

        Ok(())
    }

    /// Spawn sequential worker threads that return results
    fn spawn_sequential_workers_with_results(&self, worker: ResultWorkerFn, _num_workers: usize) -> Result<(), String> {
        let item_queue = Arc::clone(&self.item_queue);
        let result_queue = Arc::clone(&self.result_queue);
        let active_workers = Arc::clone(&self.active_workers);
        let processed_count = Arc::clone(&self.processed_count);
        let error_count = Arc::clone(&self.error_count);

        std::thread::spawn(move || {
            loop {
                match item_queue.pop() {
                    None => {
                        std::thread::sleep(std::time::Duration::from_micros(100));
                        continue;
                    }
                    Some(item) => {
                        active_workers.fetch_add(1, Ordering::AcqRel);
                        let result = worker(item.id, item.data);

                        match result {
                            Ok(output) => {
                                result_queue.push(ProcessedResult {
                                    id: item.id,
                                    result: output,
                                    error: None,
                                });
                                processed_count.fetch_add(1, Ordering::AcqRel);
                            }
                            Err(e) => {
                                result_queue.push(ProcessedResult {
                                    id: item.id,
                                    result: Vec::new(),
                                    error: Some(e),
                                });
                                error_count.fetch_add(1, Ordering::AcqRel);
                                processed_count.fetch_add(1, Ordering::AcqRel);
                            }
                        }

                        active_workers.fetch_sub(1, Ordering::AcqRel);
                    }
                }
            }
        });

        Ok(())
    }

    /// Spawn parallel worker threads (thread pool approach)
    fn spawn_parallel_workers(&self, worker: WorkerFn, num_workers: usize) -> Result<(), String> {
        for _ in 0..num_workers {
            let item_queue = Arc::clone(&self.item_queue);
            let active_workers = Arc::clone(&self.active_workers);
            let processed_count = Arc::clone(&self.processed_count);
            let worker = Arc::clone(&worker);

            std::thread::spawn(move || {
                loop {
                    match item_queue.pop() {
                        None => {
                            std::thread::sleep(std::time::Duration::from_micros(100));
                            continue;
                        }
                        Some(item) => {
                            active_workers.fetch_add(1, Ordering::AcqRel);
                            worker(item.id, item.data);
                            processed_count.fetch_add(1, Ordering::AcqRel);
                            active_workers.fetch_sub(1, Ordering::AcqRel);
                        }
                    }
                }
            });
        }

        Ok(())
    }

    /// Spawn parallel worker threads that return results
    fn spawn_parallel_workers_with_results(&self, worker: ResultWorkerFn, num_workers: usize) -> Result<(), String> {
        for _ in 0..num_workers {
            let item_queue = Arc::clone(&self.item_queue);
            let result_queue = Arc::clone(&self.result_queue);
            let active_workers = Arc::clone(&self.active_workers);
            let processed_count = Arc::clone(&self.processed_count);
            let error_count = Arc::clone(&self.error_count);
            let worker = Arc::clone(&worker);

            std::thread::spawn(move || {
                loop {
                    match item_queue.pop() {
                        None => {
                            std::thread::sleep(std::time::Duration::from_micros(100));
                            continue;
                        }
                        Some(item) => {
                            active_workers.fetch_add(1, Ordering::AcqRel);
                            let result = worker(item.id, item.data);

                            match result {
                                Ok(output) => {
                                    result_queue.push(ProcessedResult {
                                        id: item.id,
                                        result: output,
                                        error: None,
                                    });
                                    processed_count.fetch_add(1, Ordering::AcqRel);
                                }
                                Err(e) => {
                                    result_queue.push(ProcessedResult {
                                        id: item.id,
                                        result: Vec::new(),
                                        error: Some(e),
                                    });
                                    error_count.fetch_add(1, Ordering::AcqRel);
                                    processed_count.fetch_add(1, Ordering::AcqRel);
                                }
                            }

                            active_workers.fetch_sub(1, Ordering::AcqRel);
                        }
                    }
                }
            });
        }

        Ok(())
    }
}

/// Optimize worker count based on CPU cores
/// Prevents oversubscription while ensuring good parallelism
fn optimize_worker_count(requested: usize) -> usize {
    let cpu_cores = num_cpus::get();
    let max_workers = (cpu_cores - 1).max(1);
    requested.min(max_workers)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_queue_creation() {
        let queue = AsyncQueue::new(0, 128);
        assert!(queue.is_ok());
    }

    #[test]
    fn test_push_item() {
        let queue = AsyncQueue::new(0, 128).unwrap();
        let result = queue.push("test".as_bytes().to_vec());
        assert!(result.is_ok());
        assert_eq!(queue.total_pushed(), 1);
    }

    #[test]
    fn test_batch_push() {
        let queue = AsyncQueue::new(0, 128).unwrap();
        let items = vec![
            "test1".as_bytes().to_vec(),
            "test2".as_bytes().to_vec(),
            "test3".as_bytes().to_vec(),
        ];
        let result = queue.push_batch(items);
        assert!(result.is_ok());
        assert_eq!(queue.total_pushed(), 3);
    }

    #[test]
    fn test_get_mode() {
        let queue = AsyncQueue::new(0, 128).unwrap();
        assert_eq!(queue.get_mode(), 0);

        let queue_parallel = AsyncQueue::new(1, 128).unwrap();
        assert_eq!(queue_parallel.get_mode(), 1);
    }

    #[test]
    fn test_set_mode() {
        let queue = AsyncQueue::new(0, 128).unwrap();
        assert_eq!(queue.get_mode(), 0);
        queue.set_mode(1).unwrap();
        assert_eq!(queue.get_mode(), 1);
    }

    #[test]
    fn test_stats() {
        let queue = AsyncQueue::new(0, 128).unwrap();
        queue.push("test1".as_bytes().to_vec()).unwrap();
        queue.push("test2".as_bytes().to_vec()).unwrap();

        let stats = queue.get_stats();
        assert_eq!(stats.total_pushed, 2);
        assert_eq!(stats.active_workers, 0);
    }

    #[test]
    fn test_get_batch() {
        let queue = AsyncQueue::new(0, 128).unwrap();
        for i in 0..5 {
            queue.result_queue.push(ProcessedResult {
                id: i,
                result: vec![],
                error: None,
            });
        }

        let batch = queue.get_batch(3);
        assert_eq!(batch.len(), 3);
    }
}
