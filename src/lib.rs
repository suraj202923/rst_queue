pub mod queue;
pub use queue::*;

use pyo3::prelude::*;
use pyo3::exceptions::PyTypeError;
use std::sync::Arc;

/// Python module exposing the high-performance queue
#[pymodule]
fn _rst_queue(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyAsyncQueue>()?;
    m.add_class::<PyQueueStats>()?;
    m.add_class::<PyProcessedResult>()?;
    m.add("__version__", "0.2.0")?;
    
    // Add constants
    m.add("SEQUENTIAL", 0)?;
    m.add("PARALLEL", 1)?;
    
    Ok(())
}

/// Python wrapper for QueueStats
#[pyclass(module = "rst_queue._rst_queue")]
pub struct PyQueueStats {
    pub total_pushed: u64,
    pub total_processed: u64,
    pub total_errors: u64,
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
    fn active_workers(&self) -> usize {
        self.active_workers
    }

    fn __repr__(&self) -> String {
        format!(
            "QueueStats(total_pushed={}, total_processed={}, total_errors={}, active_workers={})",
            self.total_pushed, self.total_processed, self.total_errors, self.active_workers
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

    /// Push a single item to the queue (lock-free operation)
    ///
    /// Args:
    ///     data: bytes to push to the queue
    fn push(&self, data: &[u8]) -> PyResult<()> {
        self.inner.push(data.to_vec())
            .map_err(|e| PyTypeError::new_err(e))
    }

    /// Push multiple items in batch (more efficient than individual pushes)
    ///
    /// Args:
    ///     items: list of bytes to push
    ///
    /// Returns:
    ///     list of item IDs
    fn push_batch(&self, items: Vec<Vec<u8>>) -> PyResult<Vec<u64>> {
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
}

