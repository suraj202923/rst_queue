use std::sync::Arc;
use std::sync::Mutex;
use crossbeam_channel::{bounded, Sender};

/// Execution mode for the queue
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ExecutionMode {
    /// Process items sequentially, one at a time
    Sequential,
    /// Process items in parallel
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

/// Worker function type for processing queue items
pub type WorkerFn = Arc<dyn Fn(u64, Vec<u8>) + Send + Sync>;

/// Async Queue with parallel/sequential processing capabilities
pub struct AsyncQueue {
    sender: Arc<Mutex<Option<Sender<QueueItem>>>>,
    mode: Arc<Mutex<ExecutionMode>>,
    counter: Arc<Mutex<u64>>,
    active_workers: Arc<Mutex<usize>>,
}

impl AsyncQueue {
    /// Create a new AsyncQueue
    ///
    /// # Arguments
    ///
    /// * `mode` - 0 for Sequential, 1 for Parallel
    /// * `buffer_size` - Channel buffer size
    ///
    /// # Example
    ///
    /// ```
    /// let queue = AsyncQueue::new(1, 128).expect("Failed to create queue");
    /// ```
    pub fn new(mode: u8, _buffer_size: usize) -> Result<Self, String> {
        let execution_mode = ExecutionMode::from_int(mode);

        Ok(AsyncQueue {
            sender: Arc::new(Mutex::new(None)),
            mode: Arc::new(Mutex::new(execution_mode)),
            counter: Arc::new(Mutex::new(0)),
            active_workers: Arc::new(Mutex::new(0)),
        })
    }

    /// Push an item to the queue
    pub fn push(&self, data: Vec<u8>) -> Result<(), String> {
        let sender_arc = Arc::clone(&self.sender);
        let counter_arc = Arc::clone(&self.counter);

        let mut counter = counter_arc.lock().unwrap();
        *counter += 1;
        let id = *counter;
        drop(counter);

        if let Some(ref tx) = *sender_arc.lock().unwrap() {
            let item = QueueItem { id, data };
            tx.send(item)
                .map_err(|e| format!("Failed to send item: {}", e))?;
        }
        Ok(())
    }

    /// Get the current mode (0 for Sequential, 1 for Parallel)
    pub fn get_mode(&self) -> u8 {
        let mode = *self.mode.lock().unwrap();
        mode.to_int()
    }

    /// Set the execution mode
    pub fn set_mode(&self, mode: u8) -> Result<(), String> {
        *self.mode.lock().unwrap() = ExecutionMode::from_int(mode);
        Ok(())
    }

    /// Get number of active workers
    pub fn active_workers(&self) -> usize {
        *self.active_workers.lock().unwrap()
    }

    /// Get total items pushed to the queue
    pub fn total_pushed(&self) -> u64 {
        *self.counter.lock().unwrap()
    }

    /// Start the queue with a worker function
    ///
    /// # Arguments
    ///
    /// * `worker` - A function that processes queue items
    /// * `num_workers` - Number of parallel workers (ignored in sequential mode)
    ///
    /// # Example
    ///
    /// ```
    /// let queue = AsyncQueue::new(1, 128).unwrap();
    /// let worker = Arc::new(|id: u64, data: Vec<u8>| {
    ///     println!("Processing item {}: {:?}", id, data);
    /// });
    /// queue.start(worker, 4).unwrap();
    /// ```
    pub fn start(&mut self, worker: WorkerFn, num_workers: usize) -> Result<(), String> {
        let (tx, rx) = bounded::<QueueItem>(128);

        let mode = *self.mode.lock().unwrap();

        // Store sender
        *self.sender.lock().unwrap() = Some(tx);

        let rx_arc = Arc::new(Mutex::new(Some(rx)));

        match mode {
            ExecutionMode::Sequential => {
                let rx_clone = Arc::clone(&rx_arc);
                let worker_clone = Arc::clone(&worker);
                let active_clone = Arc::clone(&self.active_workers);

                std::thread::spawn(move || {
                    if let Some(receiver) = rx_clone.lock().unwrap().take() {
                        for item in receiver {
                            *active_clone.lock().unwrap() += 1;
                            worker_clone(item.id, item.data);
                            *active_clone.lock().unwrap() -= 1;
                        }
                    }
                });
            }
            ExecutionMode::Parallel => {
                for _ in 0..num_workers {
                    let rx_clone = Arc::clone(&rx_arc);
                    let worker_clone = Arc::clone(&worker);
                    let active_clone = Arc::clone(&self.active_workers);

                    std::thread::spawn(move || {
                        if let Some(receiver) = rx_clone.lock().unwrap().take() {
                            for item in receiver {
                                *active_clone.lock().unwrap() += 1;
                                worker_clone(item.id, item.data);
                                *active_clone.lock().unwrap() -= 1;
                            }
                        }
                    });
                }
            }
        }

        Ok(())
    }
}
