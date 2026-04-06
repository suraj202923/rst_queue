use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, mpsc};
use crossbeam::queue::SegQueue;
use std::path::PathBuf;
use std::thread::JoinHandle;
use std::time::{Duration, Instant};
use uuid::Uuid;
use std::collections::{HashMap, HashSet};

use crate::queue::{QueueItem, ProcessedResult, ExecutionMode, QueueStats, WorkerFn, ResultWorkerFn};

/// I/O operations to be performed by the background thread
#[derive(Clone)]
enum IoOperation {
    /// Insert a key-value pair (deferred to background thread)
    Insert { key: Vec<u8>, value: Vec<u8> },
    /// Persist counter metadata (deferred to background thread)
    PersistCounter { counter_val: u64 },
    /// Flush Write-Ahead Log to Sled (Phase 3)
    FlushWal { wal: Vec<(Vec<u8>, Vec<u8>)> },
    /// Shutdown signal
    Shutdown,
}

/// Optimized Async Persistence Queue with Sled backing store
/// Provides same API as AsyncQueue but with persistent storage
/// Uses Sled to store encoded data, in-memory processing
/// Phase 2: Async I/O thread pool for non-blocking persistence
/// Phase 3: Write-Ahead Log (WAL) for batched persistence
#[allow(dead_code)]
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
    
    /// GUID to item ID mapping
    guid_index: Arc<Mutex<HashMap<String, u64>>>,
    
    /// Removed GUIDs (to skip processing)
    removed_guids: Arc<Mutex<HashSet<String>>>,
    
    /// Flag to signal workers to stop
    is_closed: Arc<AtomicUsize>, // Using 1=closed, 0=open
    
    /// Storage path
    pub storage_path: PathBuf,
    
    /// Phase 2: Channel for deferred I/O operations
    io_sender: mpsc::Sender<IoOperation>,
    
    /// Phase 2: Handle to I/O worker thread
    io_thread: Option<JoinHandle<()>>,
    
    /// Phase 3: Write-Ahead Log buffer (in-memory, fast)
    wal_buffer: Arc<Mutex<Vec<(Vec<u8>, Vec<u8>)>>>,
    
    /// Phase 3: WAL threshold - flush when buffer exceeds this size
    wal_threshold: usize,
}

impl AsyncPersistenceQueue {
    /// Background worker thread that handles all I/O operations asynchronously
    /// Phase 2: Receives operations from mpsc channel and batches them for efficiency
    /// Phase 3: Handles WAL (Write-Ahead Log) flush operations for improved throughput
    fn io_worker(rx: mpsc::Receiver<IoOperation>, db: sled::Db) {
        let mut pending = Vec::new();
        let mut counter_val: Option<u64> = None;
        let mut last_flush = Instant::now();
        const IO_THREAD_TIMEOUT: Duration = Duration::from_millis(10);
        const FLUSH_INTERVAL: Duration = Duration::from_millis(100);

        loop {
            // Collect operations with 10ms timeout for batching efficiency
            match rx.recv_timeout(IO_THREAD_TIMEOUT) {
                Ok(IoOperation::Insert { key, value }) => {
                    pending.push((key, value));
                }
                Ok(IoOperation::PersistCounter { counter_val: val }) => {
                    // Update counter to be persisted with next flush
                    counter_val = Some(val);
                }
                Ok(IoOperation::FlushWal { wal }) => {
                    // Phase 3: Flush Write-Ahead Log to Sled (batch writes)
                    for (key, value) in wal {
                        let _ = db.insert(&key, value);
                    }
                    // Persist counter if updated
                    if let Some(val) = counter_val {
                        let _ = db.insert(b"meta:counter", val.to_le_bytes().to_vec());
                        counter_val = None;
                    }
                    // Single flush for entire WAL batch
                    let _ = db.flush();
                    last_flush = Instant::now();
                }
                Ok(IoOperation::Shutdown) => {
                    // Flush remaining items before shutdown
                    for (key, value) in pending.drain(..) {
                        let _ = db.insert(&key, value);
                    }
                    // Persist final counter value
                    if let Some(val) = counter_val {
                        let _ = db.insert(b"meta:counter", val.to_le_bytes().to_vec());
                    }
                    let _ = db.flush();
                    break;
                }
                Err(_) => {
                    // Timeout: flush if any pending or time since last flush exceeded
                    if !pending.is_empty() || counter_val.is_some() || last_flush.elapsed() > FLUSH_INTERVAL {
                        for (key, value) in pending.drain(..) {
                            let _ = db.insert(&key, value);
                        }
                        // Persist counter metadata if updated
                        if let Some(val) = counter_val {
                            let _ = db.insert(b"meta:counter", val.to_le_bytes().to_vec());
                            counter_val = None;
                        }
                        let _ = db.flush();
                        last_flush = Instant::now();
                    }
                }
            }
        }
    }

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

        // Phase 2: Create I/O channel and spawn background worker thread
        let (tx, rx) = mpsc::channel();
        let db_clone = db.clone();
        let io_thread = std::thread::spawn(move || {
            Self::io_worker(rx, db_clone);
        });

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
            guid_index: Arc::new(Mutex::new(HashMap::new())),
            removed_guids: Arc::new(Mutex::new(HashSet::new())),
            is_closed: Arc::new(AtomicUsize::new(0)),
            storage_path: path,
            io_sender: tx,
            io_thread: Some(io_thread),
            wal_buffer: Arc::new(Mutex::new(Vec::new())),
            wal_threshold: 1000, // Phase 3: Flush WAL when > 1000 items
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
            let guid = Uuid::new_v4().to_string();
            
            // Add to GUID index
            {
                let mut index = self.guid_index.lock().unwrap();
                index.insert(guid.clone(), id);
            }
            
            self.item_queue.push(QueueItem { id, guid, data });
        }

        Ok(())
    }

    /// Persist counter to disk
    /// Persist counter to disk
    #[allow(dead_code)]
    fn persist_counter(&self) -> Result<(), String> {
        let counter_val = self.counter.load(Ordering::Acquire);
        self.db.insert(b"meta:counter", counter_val.to_le_bytes().to_vec())
            .map_err(|e| format!("Failed to persist counter: {}", e))?;
        self.db.flush()
            .map_err(|e| format!("Failed to flush database: {}", e))?;
        Ok(())
    }

    /// Persist processed count to disk
    #[allow(dead_code)]
    fn persist_processed(&self) -> Result<(), String> {
        let processed_val = self.processed_count.load(Ordering::Acquire);
        self.db.insert(b"meta:processed", processed_val.to_le_bytes().to_vec())
            .map_err(|e| format!("Failed to persist processed count: {}", e))?;
        Ok(())
    }

    /// Persist error count to disk
    #[allow(dead_code)]
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

    /// Push an item to the queue and persist it asynchronously (ultra-fast)
    /// Phase 4 Enhanced: Pure async design
    /// 1. Add to in-memory queue (lock-free, returns immediately)
    /// 2. Queue persistence request to background thread
    /// 3. Background thread persists to DB asynchronously (non-blocking)
    /// Returns GUID immediately - all disk I/O happens in separate background thread!
    pub fn push(&self, data: Vec<u8>) -> Result<String, String> {
        if self.is_closed.load(Ordering::Acquire) != 0 {
            return Err("Queue is closed".to_string());
        }

        // Phase 1: Generate ID, GUID and queue for async persistence
        let id = self.counter.fetch_add(1, Ordering::AcqRel) + 1;
        let guid = Uuid::new_v4().to_string();
        let key = format!("item:{}", id).into_bytes();
        
        // Phase 2: Queue async persistence (non-blocking channel send)
        let _ = self.io_sender.send(IoOperation::Insert {
            key: key.clone(),
            value: data.clone(),
        });
        
        // Phase 3: Queue counter update (async, non-blocking)
        let counter_val = self.counter.load(Ordering::Acquire);
        let _ = self.io_sender.send(IoOperation::PersistCounter { counter_val });
        
        // Add to GUID index
        {
            let mut index = self.guid_index.lock().unwrap();
            index.insert(guid.clone(), id);
        }
        
        // Phase 4: Add to in-memory queue (fast, lock-free - returns immediately!)
        let item = QueueItem { id, guid: guid.clone(), data };
        self.item_queue.push(item);
        
        // ✅ Returns GUID immediately - disk I/O happens asynchronously in background thread!
        // No batching delays, no WAL overhead, maximum speed!
        Ok(guid)
    }

    /// Batch push items asynchronously (ultra-fast throughput)
    /// Phase 4 Enhanced: Pure async design with no batching overhead
    /// 1. Generate IDs and GUIDs for all items (in-memory, instant)
    /// 2. Queue all persistence requests to background thread (non-blocking)
    /// 3. Add all items to in-memory queue (lock-free, instant)
    /// 4. Background thread persists items one-by-one asynchronously
    /// Returns GUIDs immediately - all disk I/O happens asynchronously in background!
    pub fn push_batch(&self, items: Vec<Vec<u8>>) -> Result<Vec<String>, String> {
        if self.is_closed.load(Ordering::Acquire) != 0 {
            return Err("Queue is closed".to_string());
        }

        let mut guids = Vec::with_capacity(items.len());
        let mut queue_items = Vec::with_capacity(items.len());
        
        // Phase 1: Generate IDs, GUIDs and prepare items (in-memory, very fast)
        for data in items {
            let id = self.counter.fetch_add(1, Ordering::AcqRel) + 1;
            let guid = Uuid::new_v4().to_string();
            let key = format!("item:{}", id).into_bytes();
            
            // Phase 2: Queue async persistence (non-blocking channel send)
            let _ = self.io_sender.send(IoOperation::Insert {
                key,
                value: data.clone(),
            });
            
            // Prepare in-memory queue item
            let item = QueueItem { id, guid: guid.clone(), data };
            queue_items.push(item);
            guids.push(guid);
        }
        
        // Add all to GUID index
        {
            let mut index = self.guid_index.lock().unwrap();
            for (guid, id) in guids.iter().zip(queue_items.iter().map(|q| q.id)) {
                index.insert(guid.clone(), id);
            }
        }
        
        // Phase 3: Queue single counter update after batch
        let counter_val = self.counter.load(Ordering::Acquire);
        let _ = self.io_sender.send(IoOperation::PersistCounter { counter_val });
        
        // Phase 4: Add all items to in-memory queue (lock-free, instant)
        for item in queue_items {
            self.item_queue.push(item);
        }
        
        // ✅ Returns immediately - no locks, no delays!
        // All persistence happens asynchronously in background thread!
        Ok(guids)
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

    /// Phase 2 & 3: Gracefully shutdown the I/O worker thread and flush pending operations
    /// Phase 3: Ensures WAL is flushed before shutdown
    /// This is called automatically when the queue is dropped
    fn shutdown_io_worker(&mut self) {
        // Phase 3: Flush any remaining WAL items before shutdown
        let wal_to_flush = {
            let mut wal = self.wal_buffer.lock().unwrap();
            if !wal.is_empty() {
                wal.drain(..).collect::<Vec<_>>()
            } else {
                Vec::new()
            }
        };
        
        if !wal_to_flush.is_empty() {
            let _ = self.io_sender.send(IoOperation::FlushWal { wal: wal_to_flush });
        }
        
        // Send shutdown signal to I/O worker
        let _ = self.io_sender.send(IoOperation::Shutdown);
        
        // Wait for I/O thread to finish
        if let Some(thread) = self.io_thread.take() {
            let _ = thread.join();
        }
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
        let removed_guids = Arc::clone(&self.removed_guids);
        let db = self.db.clone();

        std::thread::spawn(move || {
            loop {
                match item_queue.pop() {
                    None => {
                        std::thread::sleep(std::time::Duration::from_micros(100));
                        continue;
                    }
                    Some(item) => {
                        // Check if this item was removed
                        let is_removed = {
                            let removed_set = removed_guids.lock().unwrap();
                            removed_set.contains(&item.guid)
                        };
                        
                        if !is_removed {
                            active_workers.fetch_add(1, Ordering::AcqRel);
                            worker(item.id, item.data.clone());
                            processed_count.fetch_add(1, Ordering::AcqRel);
                            active_workers.fetch_sub(1, Ordering::AcqRel);
                        }
                        
                        // Remove from persistent storage after processing
                        let key = format!("item:{}", item.id);
                        let _ = db.remove(key.as_bytes());
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
        let removed_guids = Arc::clone(&self.removed_guids);
        let db = self.db.clone();

        std::thread::spawn(move || {
            loop {
                match item_queue.pop() {
                    None => {
                        std::thread::sleep(std::time::Duration::from_micros(100));
                        continue;
                    }
                    Some(item) => {
                        // Check if this item was removed
                        let is_removed = {
                            let removed_set = removed_guids.lock().unwrap();
                            removed_set.contains(&item.guid)
                        };
                        
                        if !is_removed {
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
                            active_workers.fetch_sub(1, Ordering::AcqRel);
                        }

                        // Remove from persistent storage after processing
                        let key = format!("item:{}", item.id);
                        let _ = db.remove(key.as_bytes());
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
            let removed_guids = Arc::clone(&self.removed_guids);
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
                            // Check if this item was removed
                            let is_removed = {
                                let removed_set = removed_guids.lock().unwrap();
                                removed_set.contains(&item.guid)
                            };
                            
                            if !is_removed {
                                active_workers.fetch_add(1, Ordering::AcqRel);
                                worker(item.id, item.data.clone());
                                processed_count.fetch_add(1, Ordering::AcqRel);
                                active_workers.fetch_sub(1, Ordering::AcqRel);
                            }
                            
                            // Remove from persistent storage after processing
                            let key = format!("item:{}", item.id);
                            let _ = db.remove(key.as_bytes());
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
            let removed_guids = Arc::clone(&self.removed_guids);
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
                            // Check if this item was removed
                            let is_removed = {
                                let removed_set = removed_guids.lock().unwrap();
                                removed_set.contains(&item.guid)
                            };
                            
                            if !is_removed {
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
                                active_workers.fetch_sub(1, Ordering::AcqRel);
                            }

                            // Remove from persistent storage after processing
                            let key = format!("item:{}", item.id);
                            let _ = db.remove(key.as_bytes());
                        }
                    }
                }
            });
        }

        Ok(())
    }
    
    /// Remove item by GUID (before it's processed)
    pub fn remove_by_guid(&self, guid: &str) -> bool {
        // Remove from index
        let removed = {
            let mut index = self.guid_index.lock().unwrap();
            index.remove(guid).is_some()
        };
        
        // Add to removed set (workers will skip it)
        if removed {
            let mut removed_set = self.removed_guids.lock().unwrap();
            removed_set.insert(guid.to_string());
            self.removed_count.fetch_add(1, Ordering::AcqRel);
        }
        
        removed
    }
    
    /// Check if GUID is still active (not removed)
    pub fn is_guid_active(&self, guid: &str) -> bool {
        let removed_set = self.removed_guids.lock().unwrap();
        !removed_set.contains(guid)
    }
}

/// Phase 2: Implement Drop trait to properly cleanup the I/O worker thread
impl Drop for AsyncPersistenceQueue {
    fn drop(&mut self) {
        self.shutdown_io_worker();
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
