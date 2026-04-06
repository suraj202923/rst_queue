pub mod queue;
pub mod persistent_queue;
pub mod priority_queue;
pub use queue::*;
pub use persistent_queue::*;
pub use priority_queue::*;

use pyo3::prelude::*;
use pyo3::exceptions::PyTypeError;
use std::sync::Arc;

/// Python module exposing the high-performance queue
#[pymodule]
fn _rst_queue(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyAsyncQueue>()?;
    m.add_class::<PyAsyncPersistenceQueue>()?;
    m.add_class::<PyAsyncPriorityQueue>()?;
    m.add_class::<PyQueueStats>()?;
    m.add_class::<PyProcessedResult>()?;
    m.add("__version__", "0.3.0")?;
    
    // Add constants
    m.add("SEQUENTIAL", 0)?;
    m.add("PARALLEL", 1)?;
    
    // Add Priority presets
    m.add("PRIORITY_LOW", 1)?;
    m.add("PRIORITY_MEDIUM", 5)?;
    m.add("PRIORITY_HIGH", 10)?;
    m.add("PRIORITY_CRITICAL", 20)?;
    
    Ok(())
}

/// Python wrapper for QueueStats
#[pyclass(module = "rst_queue._rst_queue")]
pub struct PyQueueStats {
    pub total_pushed: u64,
    pub total_processed: u64,
    pub total_errors: u64,
    pub total_removed: u64,
    pub active_workers: usize,
}

#[pymethods]
impl PyQueueStats {
    #[getter]
    fn total_pushed(&self) -> u64 {
        self.total_pushed
    }

    #[getter]
    fn total_processed(&self) -> u64 {
        self.total_processed
    }

    #[getter]
    fn total_errors(&self) -> u64 {
        self.total_errors
    }

    #[getter]
    fn total_removed(&self) -> u64 {
        self.total_removed
    }

    #[getter]
    fn active_workers(&self) -> usize {
        self.active_workers
    }

    fn __repr__(&self) -> String {
        format!(
            "QueueStats(total_pushed={}, total_processed={}, total_errors={}, total_removed={}, active_workers={})",
            self.total_pushed, self.total_processed, self.total_errors, self.total_removed, self.active_workers
        )
    }
}

/// Python wrapper for ProcessedResult
#[pyclass(module = "rst_queue._rst_queue")]
pub struct PyProcessedResult {
    pub id: u64,
    pub result: Vec<u8>,
    pub error: Option<String>,
}

#[pymethods]
impl PyProcessedResult {
    /// Item ID that was processed
    #[getter]
    fn id(&self) -> u64 {
        self.id
    }

    /// Result data (empty if error occurred)
    #[getter]
    fn result(&self) -> &[u8] {
        &self.result
    }

    /// Error message if one occurred
    #[getter]
    fn error(&self) -> Option<String> {
        self.error.clone()
    }

    /// Check if result represents an error
    fn is_error(&self) -> bool {
        self.error.is_some()
    }

    fn __repr__(&self) -> String {
        if let Some(ref err) = self.error {
            format!("ProcessedResult(id={}, error={})", self.id, err)
        } else {
            format!("ProcessedResult(id={}, result={} bytes)", self.id, self.result.len())
        }
    }
}

/// Python wrapper for AsyncQueue
/// Optimized with lock-free data structures and atomic counters
#[pyclass(module = "rst_queue._rst_queue")]
pub struct PyAsyncQueue {
    inner: AsyncQueue,
}

#[pymethods]
impl PyAsyncQueue {
    /// Create a new AsyncQueue optimized for high performance
    ///
    /// Args:
    ///     mode: 0 for SEQUENTIAL, 1 for PARALLEL (default: 1)
    ///     buffer_size: Ignored for lock-free SegQueue (kept for API compatibility)
    #[new]
    #[pyo3(signature = (mode = 1, buffer_size = 128))]
    fn new(mode: u8, buffer_size: usize) -> PyResult<Self> {
        let queue = AsyncQueue::new(mode, buffer_size)
            .map_err(|e| PyTypeError::new_err(e))?;
        Ok(PyAsyncQueue { inner: queue })
    }

    /// Create a new AsyncQueue with persistence enabled
    ///
    /// Args:
    ///     mode: 0 for SEQUENTIAL, 1 for PARALLEL
    ///     buffer_size: Queue buffer size (informational)
    ///     storage_path: Path to store persisted data (e.g., "./queue_data")
    ///     auto_restore: If True, loads items from disk on initialization
    ///
    /// Returns:
    ///     PyAsyncQueue instance with persistence enabled
    #[staticmethod]
    #[pyo3(signature = (mode = 1, buffer_size = 128, storage_path = "./queue_data", auto_restore = true))]
    fn new_with_persistence(mode: u8, buffer_size: usize, storage_path: &str, auto_restore: bool) -> PyResult<Self> {
        let mut queue = AsyncQueue::new_with_persistence(mode, buffer_size, storage_path, auto_restore)
            .map_err(|e| PyTypeError::new_err(e))?;
        Ok(PyAsyncQueue { inner: queue })
    }

    /// Push a single item to the queue (lock-free operation), returns GUID
    ///
    /// Args:
    ///     data: bytes to push to the queue
    ///
    /// Returns:
    ///     GUID (UUID string) for tracking this item
    fn push(&self, data: &[u8]) -> PyResult<String> {
        self.inner.push(data.to_vec())
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Push multiple items in batch (more efficient than individual pushes), returns GUIDs
    ///
    /// Args:
    ///     items: list of bytes to push
    ///
    /// Returns:
    ///     list of GUIDs (UUID strings) for tracking items
    fn push_batch(&self, items: Vec<Vec<u8>>) -> PyResult<Vec<String>> {
        self.inner.push_batch(items)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Get the current execution mode
    ///
    /// Returns:
    ///     0 for SEQUENTIAL, 1 for PARALLEL
    fn get_mode(&self) -> u8 {
        self.inner.get_mode()
    }

    /// Set the execution mode
    ///
    /// Args:
    ///     mode: 0 for SEQUENTIAL, 1 for PARALLEL
    fn set_mode(&self, mode: u8) -> PyResult<()> {
        self.inner.set_mode(mode)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Get number of currently active workers
    fn active_workers(&self) -> usize {
        self.inner.active_workers()
    }

    /// Get total items pushed to the queue since creation
    fn total_pushed(&self) -> u64 {
        self.inner.total_pushed()
    }

    /// Get total items processed
    fn total_processed(&self) -> u64 {
        self.inner.total_processed()
    }

    /// Get total errors during processing
    fn total_errors(&self) -> u64 {
        self.inner.total_errors()
    }

    /// Get queue statistics as a snapshot
    fn get_stats(&self) -> PyResult<PyQueueStats> {
        let stats = self.inner.get_stats();
        Ok(PyQueueStats {
            total_pushed: stats.total_pushed,
            total_processed: stats.total_processed,
            total_errors: stats.total_errors,
            total_removed: stats.total_removed,
            active_workers: stats.active_workers,
        })
    }

    /// Start processing queue items (fire-and-forget mode)
    ///
    /// Args:
    ///     worker: A callable that accepts (item_id: int, data: bytes)
    ///     num_workers: Number of parallel workers (auto-scaling to CPU cores)
    fn start(&mut self, _py: Python<'_>, worker: Py<PyAny>, num_workers: usize) -> PyResult<()> {
        let worker_fn = Arc::new(move |id: u64, data: Vec<u8>| {
            // Use try_attach to safely acquire GIL in background thread
            if let Some(_) = pyo3::Python::try_attach(|py| {
                let py_bytes = pyo3::types::PyBytes::new(py, &data);
                match worker.call1(py, (id, py_bytes)) {
                    Ok(_) => {},
                    Err(e) => {
                        eprintln!("[ERROR] Worker execution error for item {}: {}", id, e);
                    }
                }
            }) {
                // Successfully executed
            } else {
                eprintln!("[ERROR] Failed to acquire GIL for item {}", id);
            }
        });

        self.inner.start(worker_fn, num_workers)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Get a processed result (non-blocking)
    ///
    /// Returns:
    ///     ProcessedResult or None if no results available
    fn get(&self) -> Option<PyProcessedResult> {
        self.inner.get().map(|r| PyProcessedResult {
            id: r.id,
            result: r.result,
            error: r.error,
        })
    }

    /// Get multiple results in batch (non-blocking)
    ///
    /// Args:
    ///     max_items: Maximum number of results to retrieve
    ///
    /// Returns:
    ///     List of ProcessedResult objects (empty if none available)
    fn get_batch(&self, max_items: usize) -> Vec<PyProcessedResult> {
        self.inner.get_batch(max_items)
            .into_iter()
            .map(|r| PyProcessedResult {
                id: r.id,
                result: r.result,
                error: r.error,
            })
            .collect()
    }

    /// Get a processed result (blocking)
    ///
    /// Blocks until a result is available using spin-wait with backoff.
    /// Automatically releases GIL to allow worker threads to execute.
    ///
    /// Returns:
    ///     ProcessedResult
    fn get_blocking(&self, _py: Python<'_>) -> PyResult<PyProcessedResult> {
        let result = self.inner.get_blocking()
            .map_err(|e| PyTypeError::new_err(e))?;
        
        Ok(PyProcessedResult {
            id: result.id,
            result: result.result,
            error: result.error,
        })
    }

    /// Close the queue (prevent new items from being added)
    fn close(&self) {
        self.inner.close();
    }

    /// Clear all pending items from the queue
    ///
    /// Returns the number of items removed. Only removes items that haven't
    /// been picked up by workers yet. Already-processing items are unaffected.
    fn clear(&self) -> usize {
        self.inner.clear()
    }

    /// Get the number of pending items waiting in the queue
    ///
    /// Returns an estimate of pending items. This is non-blocking but may not be
    /// 100% accurate due to concurrent operations.
    fn pending_items(&self) -> usize {
        self.inner.pending_items()
    }

    /// Start processing with a worker that returns results
    ///
    /// Args:
    ///     worker: A callable that accepts (item_id: int, data: bytes) and returns bytes
    ///     num_workers: Number of parallel workers (auto-scaling to CPU cores)
    ///
    /// Results can be retrieved via get() or get_blocking()
    fn start_with_results(&mut self, _py: Python<'_>, worker: Py<PyAny>, num_workers: usize) -> PyResult<()> {
        let worker_fn = Arc::new(move |id: u64, data: Vec<u8>| -> Result<Vec<u8>, String> {
            // Use try_attach to safely acquire GIL in background thread
            pyo3::Python::try_attach(|py| {
                let py_bytes = pyo3::types::PyBytes::new(py, &data);
                
                match worker.call1(py, (id, py_bytes)) {
                    Ok(result) => {
                        // Try to extract bytes from the result
                        match result.extract::<Vec<u8>>(py) {
                            Ok(bytes) => Ok(bytes),
                            Err(_) => {
                                // Try to extract as string
                                match result.extract::<String>(py) {
                                    Ok(s) => Ok(s.into_bytes()),
                                    Err(e) => {
                                        Err(format!("Failed to extract result: expected bytes or string, got {}", e))
                                    }
                                }
                            }
                        }
                    }
                    Err(e) => Err(format!("Worker execution error for item {}: {}", id, e)),
                }
            }).ok_or_else(|| "Failed to acquire GIL".to_string())?
        });

        self.inner.start_with_results(worker_fn, num_workers)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Save all pending items to disk using bincode serialization
    ///
    /// Serializes queue items and results to binary format for storage.
    /// Must have been created with persistence enabled.
    ///
    /// Returns:
    ///     None on success, raises error on failure
    fn save_to_disk(&self) -> PyResult<()> {
        self.inner.save_to_disk()
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Check if this queue has persistence enabled
    ///
    /// Returns:
    ///     True if created with persistence, False otherwise
    fn is_persistent(&self) -> bool {
        self.inner.is_persistent()
    }

    /// Get the persistence storage path
    ///
    /// Returns:
    ///     Path string if persistence is enabled, None otherwise
    fn get_persistence_path(&self) -> Option<String> {
        self.inner.get_persistence_path()
            .map(|p| p.to_string_lossy().to_string())
    }
    
    /// Remove item by GUID (before it's processed)
    ///
    /// Args:
    ///     guid: The GUID (UUID string) of the item to remove
    ///
    /// Returns:
    ///     True if item was found and removed, False otherwise
    fn remove_by_guid(&self, guid: &str) -> bool {
        self.inner.remove_by_guid(guid)
    }
    
    /// Check if a GUID is still active (not removed)
    ///
    /// Args:
    ///     guid: The GUID (UUID string) to check
    ///
    /// Returns:
    ///     True if GUID is active, False if removed
    fn is_guid_active(&self, guid: &str) -> bool {
        self.inner.is_guid_active(guid)
    }
}

/// Python wrapper for AsyncPersistenceQueue
/// Same API as AsyncQueue but with persistent Sled backing store
#[pyclass(module = "rst_queue._rst_queue")]
pub struct PyAsyncPersistenceQueue {
    inner: AsyncPersistenceQueue,
}

#[pymethods]
impl PyAsyncPersistenceQueue {
    /// Create a new AsyncPersistenceQueue with Sled persistence
    ///
    /// Args:
    ///     mode: 0 for SEQUENTIAL, 1 for PARALLEL (default: 1)
    ///     buffer_size: Ignored (kept for API compatibility)
    ///     storage_path: Path to Sled database (default: "./queue_storage")
    #[new]
    #[pyo3(signature = (mode = 1, buffer_size = 128, storage_path = "./queue_storage"))]
    fn new(mode: u8, buffer_size: usize, storage_path: &str) -> PyResult<Self> {
        let queue = AsyncPersistenceQueue::new(mode, buffer_size, storage_path)
            .map_err(|e| PyTypeError::new_err(e))?;
        Ok(PyAsyncPersistenceQueue { inner: queue })
    }

    /// Push a single item to the queue and persist it, returns GUID
    ///
    /// Args:
    ///     data: bytes to push to the queue
    ///
    /// Returns:
    ///     GUID (UUID string) for tracking this item
    fn push(&self, data: &[u8]) -> PyResult<String> {
        self.inner.push(data.to_vec())
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Push multiple items in batch (more efficient than individual pushes), returns GUIDs
    ///
    /// Args:
    ///     items: list of bytes to push
    ///
    /// Returns:
    ///     list of GUIDs (UUID strings) for tracking items
    fn push_batch(&self, items: Vec<Vec<u8>>) -> PyResult<Vec<String>> {
        self.inner.push_batch(items)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Get the current execution mode
    ///
    /// Returns:
    ///     0 for SEQUENTIAL, 1 for PARALLEL
    fn get_mode(&self) -> u8 {
        self.inner.get_mode()
    }

    /// Set the execution mode
    ///
    /// Args:
    ///     mode: 0 for SEQUENTIAL, 1 for PARALLEL
    fn set_mode(&self, mode: u8) -> PyResult<()> {
        self.inner.set_mode(mode)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Get number of currently active workers
    fn active_workers(&self) -> usize {
        self.inner.active_workers()
    }

    /// Get total items pushed to the queue since creation
    fn total_pushed(&self) -> u64 {
        self.inner.total_pushed()
    }

    /// Get total items processed
    fn total_processed(&self) -> u64 {
        self.inner.total_processed()
    }

    /// Get total errors during processing
    fn total_errors(&self) -> u64 {
        self.inner.total_errors()
    }

    /// Get queue statistics as a snapshot
    fn get_stats(&self) -> PyResult<PyQueueStats> {
        let stats = self.inner.get_stats();
        Ok(PyQueueStats {
            total_pushed: stats.total_pushed,
            total_processed: stats.total_processed,
            total_errors: stats.total_errors,
            total_removed: stats.total_removed,
            active_workers: stats.active_workers,
        })
    }

    /// Start processing queue items (fire-and-forget mode)
    ///
    /// Args:
    ///     worker: A callable that accepts (item_id: int, data: bytes)
    ///     num_workers: Number of parallel workers (auto-scaling to CPU cores)
    fn start(&mut self, _py: Python<'_>, worker: Py<PyAny>, num_workers: usize) -> PyResult<()> {
        let worker_fn = Arc::new(move |id: u64, data: Vec<u8>| {
            // Use try_attach to safely acquire GIL in background thread
            if let Some(_) = pyo3::Python::try_attach(|py| {
                let py_bytes = pyo3::types::PyBytes::new(py, &data);
                match worker.call1(py, (id, py_bytes)) {
                    Ok(_) => {},
                    Err(e) => {
                        eprintln!("[ERROR] Worker execution error for item {}: {}", id, e);
                    }
                }
            }) {
                // Successfully executed
            } else {
                eprintln!("[ERROR] Failed to acquire GIL for item {}", id);
            }
        });

        self.inner.start(worker_fn, num_workers)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Get a processed result (non-blocking)
    ///
    /// Returns:
    ///     ProcessedResult or None if no results available
    fn get(&self) -> Option<PyProcessedResult> {
        self.inner.get().map(|r| PyProcessedResult {
            id: r.id,
            result: r.result,
            error: r.error,
        })
    }

    /// Get multiple results in batch (non-blocking)
    ///
    /// Args:
    ///     max_items: Maximum number of results to retrieve
    ///
    /// Returns:
    ///     List of ProcessedResult objects (empty if none available)
    fn get_batch(&self, max_items: usize) -> Vec<PyProcessedResult> {
        self.inner.get_batch(max_items)
            .into_iter()
            .map(|r| PyProcessedResult {
                id: r.id,
                result: r.result,
                error: r.error,
            })
            .collect()
    }

    /// Get a processed result (blocking)
    ///
    /// Blocks until a result is available using spin-wait with backoff.
    /// Automatically releases GIL to allow worker threads to execute.
    ///
    /// Returns:
    ///     ProcessedResult
    fn get_blocking(&self, _py: Python<'_>) -> PyResult<PyProcessedResult> {
        let result = self.inner.get_blocking()
            .map_err(|e| PyTypeError::new_err(e))?;
        
        Ok(PyProcessedResult {
            id: result.id,
            result: result.result,
            error: result.error,
        })
    }

    /// Close the queue (prevent new items from being added)
    fn close(&self) {
        self.inner.close();
    }

    /// Clear all pending items from the queue and Sled storage
    ///
    /// Returns the number of items removed.
    fn clear(&self) -> usize {
        self.inner.clear()
    }

    /// Get the number of pending items waiting in the queue
    ///
    /// Returns an estimate of pending items.
    fn pending_items(&self) -> usize {
        self.inner.pending_items()
    }

    /// Start processing with a worker that returns results
    ///
    /// Args:
    ///     worker: A callable that accepts (item_id: int, data: bytes) and returns bytes
    ///     num_workers: Number of parallel workers (auto-scaling to CPU cores)
    ///
    /// Results can be retrieved via get() or get_blocking()
    fn start_with_results(&mut self, _py: Python<'_>, worker: Py<PyAny>, num_workers: usize) -> PyResult<()> {
        let worker_fn = Arc::new(move |id: u64, data: Vec<u8>| -> Result<Vec<u8>, String> {
            // Use try_attach to safely acquire GIL in background thread
            pyo3::Python::try_attach(|py| {
                let py_bytes = pyo3::types::PyBytes::new(py, &data);
                
                match worker.call1(py, (id, py_bytes)) {
                    Ok(result) => {
                        // Try to extract bytes from the result
                        match result.extract::<Vec<u8>>(py) {
                            Ok(bytes) => Ok(bytes),
                            Err(_) => {
                                // Try to extract as string
                                match result.extract::<String>(py) {
                                    Ok(s) => Ok(s.into_bytes()),
                                    Err(e) => {
                                        Err(format!("Failed to extract result: expected bytes or string, got {}", e))
                                    }
                                }
                            }
                        }
                    }
                    Err(e) => Err(format!("Worker execution error for item {}: {}", id, e)),
                }
            }).ok_or_else(|| "Failed to acquire GIL".to_string())?
        });

        self.inner.start_with_results(worker_fn, num_workers)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Get the storage path for this persistent queue
    ///
    /// Returns:
    ///     Path to the Sled database
    fn get_storage_path(&self) -> String {
        self.inner.storage_path.to_string_lossy().to_string()
    }

    /// Check total items in Sled storage (includes both processed and pending)
    ///
    /// Returns:
    ///     Count of all items in persistent store
    fn storage_item_count(&self) -> u64 {
        let mut count = 0;
        let mut iter = self.inner.db.scan_prefix(b"item:");
        while let Some(Ok(_)) = iter.next() {
            count += 1;
        }
        count
    }
    
    /// Remove item by GUID (before it's processed)
    ///
    /// Args:
    ///     guid: The GUID (UUID string) of the item to remove
    ///
    /// Returns:
    ///     True if item was found and removed, False otherwise
    fn remove_by_guid(&self, guid: &str) -> bool {
        self.inner.remove_by_guid(guid)
    }
    
    /// Check if a GUID is still active (not removed)
    ///
    /// Args:
    ///     guid: The GUID (UUID string) to check
    ///
    /// Returns:
    ///     True if GUID is active, False if removed
    fn is_guid_active(&self, guid: &str) -> bool {
        self.inner.is_guid_active(guid)
    }
}

/// Python wrapper for AsyncPriorityQueue
/// Priority-based async queue with GUID tracking and changeable priorities
#[pyclass(module = "rst_queue._rst_queue")]
pub struct PyAsyncPriorityQueue {
    inner: AsyncPriorityQueue,
}

#[pymethods]
impl PyAsyncPriorityQueue {
    /// Create a new AsyncPriorityQueue with GUID support
    ///
    /// Args:
    ///     mode: 0 for SEQUENTIAL, 1 for PARALLEL (default: 1)
    ///     storage_path: Path to Sled database (default: "./priority_queue_storage")
    #[new]
    #[pyo3(signature = (mode = 1, storage_path = "./priority_queue_storage"))]
    fn new(mode: u8, storage_path: &str) -> PyResult<Self> {
        let queue = AsyncPriorityQueue::new(mode, storage_path)
            .map_err(|e| PyTypeError::new_err(e))?;
        Ok(PyAsyncPriorityQueue { inner: queue })
    }

    /// Push item with custom priority level (1-100), returns GUID
    ///
    /// Args:
    ///     data: bytes to push to the queue
    ///     priority: Priority level 1-100 (higher = more important)
    ///
    /// Returns:
    ///     GUID (UUID string) for tracking this item
    fn push_with_priority(&self, data: &[u8], priority: u8) -> PyResult<String> {
        let p = Priority::custom(priority)
            .map_err(|e| PyTypeError::new_err(e))?;
        
        self.inner.push_with_priority(data.to_vec(), p)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Push with preset priority level, returns GUID
    ///
    /// Args:
    ///     data: bytes to push to the queue
    ///     preset_name: "low", "medium", "high", or "critical"
    ///
    /// Returns:
    ///     GUID (UUID string) for tracking this item
    fn push_with_preset_priority(&self, data: &[u8], preset_name: &str) -> PyResult<String> {
        let priority = match preset_name.to_lowercase().as_str() {
            "low" => Priority::LOW,
            "medium" => Priority::MEDIUM,
            "high" => Priority::HIGH,
            "critical" => Priority::CRITICAL,
            _ => return Err(PyTypeError::new_err(
                "Invalid preset: use 'low', 'medium', 'high', or 'critical'"
            )),
        };
        
        self.inner.push_with_priority(data.to_vec(), priority)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Push batch with same priority level, returns list of GUIDs
    ///
    /// Args:
    ///     items: list of bytes to push to the queue
    ///     priority: Priority level 1-100
    ///
    /// Returns:
    ///     List of GUIDs (UUID strings) for tracking items
    fn push_batch_with_priority(&self, items: Vec<Vec<u8>>, priority: u8) -> PyResult<Vec<String>> {
        let p = Priority::custom(priority)
            .map_err(|e| PyTypeError::new_err(e))?;
        
        self.inner.push_batch_with_priority(items, p)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Push batch with preset priority, returns list of GUIDs
    ///
    /// Args:
    ///     items: list of bytes to push to the queue
    ///     preset_name: "low", "medium", "high", or "critical"
    ///
    /// Returns:
    ///     List of GUIDs (UUID strings) for tracking items
    fn push_batch_with_preset_priority(
        &self,
        items: Vec<Vec<u8>>,
        preset_name: &str,
    ) -> PyResult<Vec<String>> {
        let priority = match preset_name.to_lowercase().as_str() {
            "low" => Priority::LOW,
            "medium" => Priority::MEDIUM,
            "high" => Priority::HIGH,
            "critical" => Priority::CRITICAL,
            _ => return Err(PyTypeError::new_err(
                "Invalid preset: use 'low', 'medium', 'high', or 'critical'"
            )),
        };
        
        self.inner.push_batch_with_priority(items, priority)
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Get next item (highest priority first)
    ///
    /// Returns:
    ///     Tuple of (guid, data, priority_level) or None if queue is empty
    fn get_next(&self) -> Option<(String, Vec<u8>, u8)> {
        self.inner.get_next().map(|(guid, data, priority)| {
            (guid, data, priority.get_level())
        })
    }

    /// Peek at next item without removing it
    ///
    /// Returns:
    ///     Tuple of (guid, priority_level) or None if queue is empty
    fn peek_next(&self) -> Option<(String, u8)> {
        self.inner.peek_next().map(|(guid, priority)| {
            (guid, priority.get_level())
        })
    }

    /// Update priority of queued item by GUID
    ///
    /// Args:
    ///     item_guid: GUID of the item to update
    ///     new_priority: New priority level 1-100
    ///
    /// Returns:
    ///     True if item found and updated, False if not found or already processed
    fn update_priority(&self, item_guid: &str, new_priority: u8) -> PyResult<bool> {
        let p = Priority::custom(new_priority)
            .map_err(|e| PyTypeError::new_err(e))?;
        Ok(self.inner.update_priority(item_guid, p))
    }

    /// Get current priority of item by GUID
    ///
    /// Args:
    ///     item_guid: GUID of the item
    ///
    /// Returns:
    ///     Priority level (1-100) or None if not found
    fn get_priority(&self, item_guid: &str) -> Option<u8> {
        self.inner.get_priority(item_guid).map(|p| p.get_level())
    }

    /// Remove item from queue by GUID (before it's processed)
    ///
    /// Args:
    ///     item_guid: GUID of the item to remove
    ///
    /// Returns:
    ///     True if item found and removed, False if not found or already processed
    fn remove_by_guid(&self, item_guid: &str) -> bool {
        self.inner.remove_by_guid(item_guid)
    }

    /// Get priority statistics for current queue
    ///
    /// Returns:
    ///     Dictionary mapping priority levels to item counts
    fn get_priority_stats(&self) -> std::collections::HashMap<u8, usize> {
        let stats = self.inner.get_priority_stats();
        stats.by_priority_level
    }

    /// Get total number of items currently in queue
    ///
    /// Returns:
    ///     Number of items waiting to be processed
    fn len(&self) -> usize {
        self.inner.len()
    }

    /// Check if queue is empty
    ///
    /// Returns:
    ///     True if queue has no items
    fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    /// Get total items processed
    ///
    /// Returns:
    ///     Count of processed items
    fn get_processed_count(&self) -> u64 {
        self.inner.get_processed_count()
    }

    /// Close the queue (prevent new items from being added)
    fn close(&self) {
        self.inner.close();
    }

    /// Flush to disk to ensure durability
    ///
    /// Returns:
    ///     None on success, raises error on failure
    fn flush(&self) -> PyResult<()> {
        self.inner.flush()
            .map_err(|e| PyTypeError::new_err(e))
    }
    
    /// Start processing with a worker callback
    ///
    /// Args:
    ///     worker: A callable that accepts (guid: str, data: bytes, priority: int)
    ///     num_workers: Number of parallel workers
    fn start(&self, _py: Python<'_>, worker: Py<PyAny>, num_workers: usize) -> PyResult<()> {
        let worker_fn = Arc::new(move |guid: String, data: Vec<u8>, priority: Priority| {
            if let Some(_) = pyo3::Python::try_attach(|py| {
                let py_bytes = pyo3::types::PyBytes::new(py, &data);
                match worker.call1(py, (guid, py_bytes, priority.get_level())) {
                    Ok(_) => {},
                    Err(e) => {
                        eprintln!("[ERROR] Worker execution error: {}", e);
                    }
                }
            }) {
                // Successfully executed
            } else {
                eprintln!("[ERROR] Failed to acquire GIL");
            }
        });

        // Spawn workers that process items from the queue
        for _ in 0..num_workers {
            let inner = Arc::new(self.inner.clone());
            let worker = worker_fn.clone();
            
            std::thread::spawn(move || {
                loop {
                    if let Some((guid, data, priority)) = inner.get_next() {
                        worker(guid, data, priority);
                        inner.increment_processed();
                    } else {
                        std::thread::sleep(std::time::Duration::from_micros(100));
                    }
                }
            });
        }

        Ok(())
    }
}



