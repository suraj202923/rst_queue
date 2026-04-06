use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use crossbeam::queue::SegQueue;
use std::path::PathBuf;
use std::fs;
use std::io::{self, Read, Write};

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
    pub total_removed: u64,
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
    removed_count: Arc<AtomicU64>,
    
    /// Execution mode
    mode: Arc<Mutex<ExecutionMode>>,
    
    /// Flag to signal workers to stop
    is_closed: Arc<AtomicUsize>, // Using 1=closed, 0=open
    
    /// Persistence settings
    persistence_enabled: bool,
    persistence_path: Option<PathBuf>,
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
            removed_count: Arc::new(AtomicU64::new(0)),
            mode: Arc::new(Mutex::new(execution_mode)),
            is_closed: Arc::new(AtomicUsize::new(0)),
            persistence_enabled: false,
            persistence_path: None,
        })
    }

    /// Create a new AsyncQueue with persistence enabled
    ///
    /// # Arguments
    ///
    /// * `mode` - 0 for Sequential, 1 for Parallel
    /// * `_buffer_size` - Ignored (SegQueue is unbounded), kept for API compatibility
    /// * `storage_path` - Path to store persisted data (e.g., "./queue_data")
    /// * `auto_restore` - If true, loads items from disk on initialization
    ///
    /// # Example
    ///
    /// ```
    /// let queue = AsyncQueue::new_with_persistence(1, 128, "./queue_data", true)
    ///     .expect("Failed to create queue");
    /// ```
    pub fn new_with_persistence(
        mode: u8,
        _buffer_size: usize,
        storage_path: &str,
        auto_restore: bool,
    ) -> Result<Self, String> {
        let execution_mode = ExecutionMode::from_int(mode);
        let path = PathBuf::from(storage_path);

        // Create directory if it doesn't exist
        if let Err(e) = fs::create_dir_all(&path) {
            return Err(format!("Failed to create storage directory: {}", e));
        }

        let mut queue = AsyncQueue {
            item_queue: Arc::new(SegQueue::new()),
            result_queue: Arc::new(SegQueue::new()),
            counter: Arc::new(AtomicU64::new(0)),
            active_workers: Arc::new(AtomicUsize::new(0)),
            processed_count: Arc::new(AtomicU64::new(0)),
            error_count: Arc::new(AtomicU64::new(0)),
            removed_count: Arc::new(AtomicU64::new(0)),
            mode: Arc::new(Mutex::new(execution_mode)),
            is_closed: Arc::new(AtomicUsize::new(0)),
            persistence_enabled: true,
            persistence_path: Some(path),
        };

        // Restore items if auto_restore is enabled
        if auto_restore {
            queue.restore_from_disk()?;
        }

        Ok(queue)
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

    /// Get total results removed from the queue
    pub fn total_removed(&self) -> u64 {
        self.removed_count.load(Ordering::Acquire)
    }

    /// Get queue statistics (lock-free read)
    pub fn get_stats(&self) -> QueueStats {
        QueueStats {
            total_pushed: self.total_pushed(),
            total_processed: self.total_processed(),
            total_errors: self.total_errors(),
            total_removed: self.total_removed(),
            active_workers: self.active_workers(),
        }
    }

    /// Get a processed result from the result queue (non-blocking)
    pub fn get(&self) -> Option<ProcessedResult> {
        match self.result_queue.pop() {
            Some(result) => {
                self.removed_count.fetch_add(1, Ordering::AcqRel);
                Some(result)
            }
            None => None,
        }
    }

    /// Get multiple results in batch (non-blocking)
    pub fn get_batch(&self, max_items: usize) -> Vec<ProcessedResult> {
        let mut results = Vec::with_capacity(max_items);
        for _ in 0..max_items {
            match self.result_queue.pop() {
                Some(result) => {
                    self.removed_count.fetch_add(1, Ordering::AcqRel);
                    results.push(result);
                }
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
                self.removed_count.fetch_add(1, Ordering::AcqRel);
                return Ok(result);
            }
            backoff.snooze();
        }
    }

    /// Close the queue (prevent new items)
    pub fn close(&self) {
        self.is_closed.store(1, Ordering::Release);
    }

    /// Clear all pending items from the queue
    /// Returns the number of items removed
    /// Only affects items not yet being processed
    pub fn clear(&self) -> usize {
        let mut count = 0;
        while self.item_queue.pop().is_some() {
            count += 1;
        }
        count
    }

    /// Get the number of pending items in the queue (non-blocking estimate)
    /// This is a best-effort estimate and not guaranteed to be exact
    /// due to concurrent operations
    pub fn pending_items(&self) -> usize {
        let mut count = 0;
        let mut temp_items = Vec::new();
        
        // Pop all items and count them
        while let Some(item) = self.item_queue.pop() {
            temp_items.push(item);
            count += 1;
        }
        
        // Push them back to preserve queue
        for item in temp_items {
            self.item_queue.push(item);
        }
        
        count
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
                            // No items, sleep briefly
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

    /// Save all pending items to disk using bincode serialization
    pub fn save_to_disk(&self) -> Result<(), String> {
        if !self.persistence_enabled {
            return Err("Persistence not enabled for this queue".to_string());
        }

        let path = match &self.persistence_path {
            Some(p) => p,
            None => return Err("Persistence path not set".to_string()),
        };

        // Create directory if it doesn't exist
        if let Err(e) = fs::create_dir_all(path) {
            return Err(format!("Failed to create persistence directory: {}", e));
        }

        // Collect and write items to disk
        let items_path = path.join("items.bin");
        let mut file = match fs::File::create(&items_path) {
            Ok(f) => f,
            Err(e) => return Err(format!("Failed to create items file: {}", e)),
        };

        let mut items = Vec::new();
        while let Some(item) = self.item_queue.pop() {
            items.push(item);
        }

        // Write each item's data with length prefix (8 bytes for length)
        for item in items {
            let len = item.data.len() as u64;
            if let Err(e) = file.write_all(&len.to_le_bytes()) {
                return Err(format!("Failed to write item length: {}", e));
            }
            if let Err(e) = file.write_all(&item.data) {
                return Err(format!("Failed to write item data: {}", e));
            }
        }

        // Collect and write results to disk
        let results_path = path.join("results.bin");
        let mut results_file = match fs::File::create(&results_path) {
            Ok(f) => f,
            Err(e) => return Err(format!("Failed to create results file: {}", e)),
        };

        let mut results = Vec::new();
        while let Some(result) = self.result_queue.pop() {
            results.push(result);
        }

        // Write each result: id (8) + result_len (8) + result_data + error_len (8) + error_data
        for result in results {
            if let Err(e) = results_file.write_all(&result.id.to_le_bytes()) {
                return Err(format!("Failed to write result id: {}", e));
            }
            let result_len = result.result.len() as u64;
            if let Err(e) = results_file.write_all(&result_len.to_le_bytes()) {
                return Err(format!("Failed to write result length: {}", e));
            }
            if let Err(e) = results_file.write_all(&result.result) {
                return Err(format!("Failed to write result data: {}", e));
            }
            let error_len = result.error.as_ref().map(|e| e.len()).unwrap_or(0) as u64;
            if let Err(e) = results_file.write_all(&error_len.to_le_bytes()) {
                return Err(format!("Failed to write error length: {}", e));
            }
            if let Some(error) = &result.error {
                if let Err(e) = results_file.write_all(error.as_bytes()) {
                    return Err(format!("Failed to write error data: {}", e));
                }
            }
        }

        Ok(())
    }

    /// Restore items from disk that were previously saved (raw binary format)
    pub fn restore_from_disk(&mut self) -> Result<(), String> {
        let path = match &self.persistence_path {
            Some(p) => p,
            None => return Err("Persistence path not set".to_string()),
        };

        // Restore items
        let items_path = path.join("items.bin");
        if items_path.exists() {
            let data = match fs::read(&items_path) {
                Ok(d) => d,
                Err(e) => return Err(format!("Failed to read items from disk: {}", e)),
            };

            let mut cursor = 0;
            while cursor < data.len() {
                // Read 8-byte length
                if cursor + 8 > data.len() {
                    break;
                }
                let len_bytes = &data[cursor..cursor + 8];
                let len = u64::from_le_bytes([
                    len_bytes[0], len_bytes[1], len_bytes[2], len_bytes[3],
                    len_bytes[4], len_bytes[5], len_bytes[6], len_bytes[7],
                ]) as usize;
                cursor += 8;

                // Read data
                if cursor + len > data.len() {
                    break;
                }
                let item_data = data[cursor..cursor + len].to_vec();
                cursor += len;

                // Create QueueItem with id 0 (user should extract from encoded data)
                let item = QueueItem {
                    id: self.counter.fetch_add(1, Ordering::AcqRel),
                    data: item_data,
                };
                self.item_queue.push(item);
            }
        }

        // Restore results
        let results_path = path.join("results.bin");
        if results_path.exists() {
            let data = match fs::read(&results_path) {
                Ok(d) => d,
                Err(e) => return Err(format!("Failed to read results from disk: {}", e)),
            };

            let mut cursor = 0;
            while cursor < data.len() {
                // Read id (8 bytes)
                if cursor + 8 > data.len() { break; }
                let id = u64::from_le_bytes([
                    data[cursor], data[cursor+1], data[cursor+2], data[cursor+3],
                    data[cursor+4], data[cursor+5], data[cursor+6], data[cursor+7],
                ]);
                cursor += 8;

                // Read result length (8 bytes)
                if cursor + 8 > data.len() { break; }
                let result_len = u64::from_le_bytes([
                    data[cursor], data[cursor+1], data[cursor+2], data[cursor+3],
                    data[cursor+4], data[cursor+5], data[cursor+6], data[cursor+7],
                ]) as usize;
                cursor += 8;

                // Read result data
                if cursor + result_len > data.len() { break; }
                let result = data[cursor..cursor + result_len].to_vec();
                cursor += result_len;

                // Read error length (8 bytes)
                if cursor + 8 > data.len() { break; }
                let error_len = u64::from_le_bytes([
                    data[cursor], data[cursor+1], data[cursor+2], data[cursor+3],
                    data[cursor+4], data[cursor+5], data[cursor+6], data[cursor+7],
                ]) as usize;
                cursor += 8;

                // Read error data
                let error = if error_len > 0 {
                    if cursor + error_len > data.len() { break; }
                    let err_str = String::from_utf8_lossy(&data[cursor..cursor + error_len]).to_string();
                    cursor += error_len;
                    Some(err_str)
                } else {
                    None
                };

                let processed_result = ProcessedResult {
                    id,
                    result,
                    error,
                };
                self.result_queue.push(processed_result);
            }
        }

        Ok(())
    }

    /// Check if persistence is enabled for this queue
    pub fn is_persistent(&self) -> bool {
        self.persistence_enabled
    }

    /// Get the persistence path if enabled
    pub fn get_persistence_path(&self) -> Option<&PathBuf> {
        self.persistence_path.as_ref()
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
