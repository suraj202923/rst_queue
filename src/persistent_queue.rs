use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use crossbeam::queue::SegQueue;
use std::path::PathBuf;

use crate::queue::{QueueItem, ProcessedResult, ExecutionMode, QueueStats, WorkerFn, ResultWorkerFn};

/// Optimized Async Persistence Queue with Sled backing store
/// Provides same API as AsyncQueue but with persistent storage
/// Uses Sled to store encoded data, in-memory processing
pub struct AsyncPersistenceQueue {
    /// Lock-free queue for items (in-memory)
    item_queue: Arc<SegQueue<QueueItem>>,
    /// Lock-free queue for results (in-memory)
    result_queue: Arc<SegQueue<ProcessedResult>>,
    
    /// Sled database for persistent storage
    pub db: sled::Db,
    
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
    
    /// Storage path
    pub storage_path: PathBuf,
}

impl AsyncPersistenceQueue {
    /// Create a new AsyncPersistenceQueue with Sled persistence
    ///
    /// # Arguments
    ///
    /// * `mode` - 0 for Sequential, 1 for Parallel
    /// * `_buffer_size` - Ignored (SegQueue is unbounded), kept for API compatibility
    /// * `storage_path` - Path to Sled database directory (e.g., "./queue_storage")
    ///
    /// # Example
    ///
    /// ```
    /// let queue = AsyncPersistenceQueue::new(1, 128, "./queue_storage")
    ///     .expect("Failed to create persistent queue");
    /// ```
    pub fn new(mode: u8, _buffer_size: usize, storage_path: &str) -> Result<Self, String> {
        let execution_mode = ExecutionMode::from_int(mode);
        let path = PathBuf::from(storage_path);

        // Open Sled database
        let db = sled::open(&path)
            .map_err(|e| format!("Failed to open Sled database: {}", e))?;

        let mut queue = AsyncPersistenceQueue {
            item_queue: Arc::new(SegQueue::new()),
            result_queue: Arc::new(SegQueue::new()),
            db,
            counter: Arc::new(AtomicU64::new(0)),
            active_workers: Arc::new(AtomicUsize::new(0)),
            processed_count: Arc::new(AtomicU64::new(0)),
            error_count: Arc::new(AtomicU64::new(0)),
            removed_count: Arc::new(AtomicU64::new(0)),
            mode: Arc::new(Mutex::new(execution_mode)),
            is_closed: Arc::new(AtomicUsize::new(0)),
            storage_path: path,
        };

        // Restore pending items and counter from Sled
        queue.restore_from_disk()?;

        Ok(queue)
    }

    /// Restore queue state from persistent storage
    fn restore_from_disk(&mut self) -> Result<(), String> {
        // Restore counter
        if let Ok(Some(counter_bytes)) = self.db.get(b"meta:counter") {
            if let Ok(bytes_array) = <[u8; 8]>::try_from(&counter_bytes[..]) {
                let counter_val = u64::from_le_bytes(bytes_array);
                self.counter.store(counter_val, Ordering::Release);
            }
        }

        // Restore processed count
        if let Ok(Some(processed_bytes)) = self.db.get(b"meta:processed") {
            if let Ok(bytes_array) = <[u8; 8]>::try_from(&processed_bytes[..]) {
                let processed_val = u64::from_le_bytes(bytes_array);
                self.processed_count.store(processed_val, Ordering::Release);
            }
        }

        // Restore error count
        if let Ok(Some(error_bytes)) = self.db.get(b"meta:errors") {
            if let Ok(bytes_array) = <[u8; 8]>::try_from(&error_bytes[..]) {
                let error_val = u64::from_le_bytes(bytes_array);
                self.error_count.store(error_val, Ordering::Release);
            }
        }

        // Restore removed count
        if let Ok(Some(removed_bytes)) = self.db.get(b"meta:removed") {
            if let Ok(bytes_array) = <[u8; 8]>::try_from(&removed_bytes[..]) {
                let removed_val = u64::from_le_bytes(bytes_array);
                self.removed_count.store(removed_val, Ordering::Release);
            }
        }

        // Restore pending items from Sled
        let mut pending_items = Vec::new();
        let mut iter = self.db.scan_prefix(b"item:");
        
        while let Some(Ok((key, value))) = iter.next() {
            // Skip if this is a metadata key
            if key.starts_with(b"meta:") {
                continue;
            }
            
            // Parse item ID from key
            if let Ok(key_str) = std::str::from_utf8(&key) {
                if key_str.starts_with("item:") {
                    if let Ok(id) = key_str[5..].parse::<u64>() {
                        pending_items.push((id, value.to_vec()));
                    }
                }
            }
        }

        // Load pending items into in-memory queue
        for (id, data) in pending_items {
            self.item_queue.push(QueueItem { id, data });
        }

        Ok(())
    }

    /// Persist counter to disk
    fn persist_counter(&self) -> Result<(), String> {
        let counter_val = self.counter.load(Ordering::Acquire);
        self.db.insert(b"meta:counter", counter_val.to_le_bytes().to_vec())
            .map_err(|e| format!("Failed to persist counter: {}", e))?;
        self.db.flush()
            .map_err(|e| format!("Failed to flush database: {}", e))?;
        Ok(())
    }

    /// Persist processed count to disk
    fn persist_processed(&self) -> Result<(), String> {
        let processed_val = self.processed_count.load(Ordering::Acquire);
        self.db.insert(b"meta:processed", processed_val.to_le_bytes().to_vec())
            .map_err(|e| format!("Failed to persist processed count: {}", e))?;
        Ok(())
    }

    /// Persist error count to disk
    fn persist_errors(&self) -> Result<(), String> {
        let error_val = self.error_count.load(Ordering::Acquire);
        self.db.insert(b"meta:errors", error_val.to_le_bytes().to_vec())
            .map_err(|e| format!("Failed to persist error count: {}", e))?;
        Ok(())
    }

    /// Persist removed count to disk
    fn persist_removed(&self) -> Result<(), String> {
        let removed_val = self.removed_count.load(Ordering::Acquire);
        self.db.insert(b"meta:removed", removed_val.to_le_bytes().to_vec())
            .map_err(|e| format!("Failed to persist removed count: {}", e))?;
        Ok(())
    }

    /// Push an item to the queue and persist it
    pub fn push(&self, data: Vec<u8>) -> Result<(), String> {
        if self.is_closed.load(Ordering::Acquire) != 0 {
            return Err("Queue is closed".to_string());
        }

        let id = self.counter.fetch_add(1, Ordering::AcqRel) + 1;
        let item = QueueItem { id, data };
        
        // Persist to Sled
        let key = format!("item:{}", id);
        self.db.insert(key.as_bytes(), item.data.clone())
            .map_err(|e| format!("Failed to persist item: {}", e))?;
        
        // Persist counter
        self.persist_counter()?;
        
        // Add to in-memory queue
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
            let item = QueueItem { id, data };
            
            // Persist to Sled
            let key = format!("item:{}", id);
            self.db.insert(key.as_bytes(), item.data.clone())
                .map_err(|e| format!("Failed to persist item: {}", e))?;
            
            // Add to in-memory queue
            self.item_queue.push(item);
            ids.push(id);
        }
        
        // Persist counter once for the batch
        self.persist_counter()?;
        
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
                let _ = self.removed_count.fetch_add(1, Ordering::AcqRel);
                let _ = self.persist_removed();
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
                    let _ = self.removed_count.fetch_add(1, Ordering::AcqRel);
                    results.push(result);
                }
                None => break,
            }
        }
        
        if !results.is_empty() {
            let _ = self.persist_removed();
        }
        
        results
    }

    /// Block and get a processed result (uses spin-wait with backoff)
    pub fn get_blocking(&self) -> Result<ProcessedResult, String> {
        let backoff = crossbeam::utils::Backoff::new();
        loop {
            if let Some(result) = self.result_queue.pop() {
                let _ = self.removed_count.fetch_add(1, Ordering::AcqRel);
                let _ = self.persist_removed();
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
    pub fn clear(&self) -> usize {
        let mut count = 0;
        while let Some(item) = self.item_queue.pop() {
            // Remove from Sled
            let key = format!("item:{}", item.id);
            let _ = self.db.remove(key.as_bytes());
            count += 1;
        }
        let _ = self.db.flush();
        count
    }

    /// Get the number of pending items in the queue (non-blocking estimate)
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
        let db = self.db.clone();

        std::thread::spawn(move || {
            loop {
                match item_queue.pop() {
                    None => {
                        std::thread::sleep(std::time::Duration::from_micros(100));
                        continue;
                    }
                    Some(item) => {
                        active_workers.fetch_add(1, Ordering::AcqRel);
                        worker(item.id, item.data.clone());
                        processed_count.fetch_add(1, Ordering::AcqRel);
                        
                        // Remove from persistent storage after processing
                        let key = format!("item:{}", item.id);
                        let _ = db.remove(key.as_bytes());
                        
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
        let db = self.db.clone();

        std::thread::spawn(move || {
            loop {
                match item_queue.pop() {
                    None => {
                        std::thread::sleep(std::time::Duration::from_micros(100));
                        continue;
                    }
                    Some(item) => {
                        active_workers.fetch_add(1, Ordering::AcqRel);
                        let result = worker(item.id, item.data.clone());

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

                        // Remove from persistent storage after processing
                        let key = format!("item:{}", item.id);
                        let _ = db.remove(key.as_bytes());

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
            let db = self.db.clone();

            std::thread::spawn(move || {
                loop {
                    match item_queue.pop() {
                        None => {
                            std::thread::sleep(std::time::Duration::from_micros(100));
                            continue;
                        }
                        Some(item) => {
                            active_workers.fetch_add(1, Ordering::AcqRel);
                            worker(item.id, item.data.clone());
                            processed_count.fetch_add(1, Ordering::AcqRel);
                            
                            // Remove from persistent storage after processing
                            let key = format!("item:{}", item.id);
                            let _ = db.remove(key.as_bytes());
                            
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
            let db = self.db.clone();

            std::thread::spawn(move || {
                loop {
                    match item_queue.pop() {
                        None => {
                            std::thread::sleep(std::time::Duration::from_micros(100));
                            continue;
                        }
                        Some(item) => {
                            active_workers.fetch_add(1, Ordering::AcqRel);
                            let result = worker(item.id, item.data.clone());

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

                            // Remove from persistent storage after processing
                            let key = format!("item:{}", item.id);
                            let _ = db.remove(key.as_bytes());

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
fn optimize_worker_count(requested: usize) -> usize {
    if requested == 0 {
        num_cpus::get()
    } else {
        requested
    }
}
