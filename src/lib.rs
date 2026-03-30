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
#[pyclass(module = "rst_queue._rst_queue")]
pub struct PyAsyncQueue {
    inner: AsyncQueue,
}

#[pymethods]
impl PyAsyncQueue {
    /// Create a new AsyncQueue
    ///
    /// Args:
    ///     mode: 0 for SEQUENTIAL, 1 for PARALLEL (default: 1)
    ///     buffer_size: Channel buffer size (default: 128)
    #[new]
    #[pyo3(signature = (mode = 1, buffer_size = 128))]
    fn new(mode: u8, buffer_size: usize) -> PyResult<Self> {
        let queue = AsyncQueue::new(mode, buffer_size)
            .map_err(|e| PyTypeError::new_err(e))?;
        Ok(PyAsyncQueue { inner: queue })
    }

    /// Push an item to the queue
    ///
    /// Args:
    ///     data: bytes to push to the queue
    fn push(&self, data: &[u8]) -> PyResult<()> {
        self.inner.push(data.to_vec())
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

    /// Get number of active workers
    fn active_workers(&self) -> usize {
        self.inner.active_workers()
    }

    /// Get total items pushed to the queue
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

    /// Get queue statistics
    fn get_stats(&self) -> PyResult<PyQueueStats> {
        let stats = self.inner.get_stats();
        Ok(PyQueueStats {
            total_pushed: stats.total_pushed,
            total_processed: stats.total_processed,
            total_errors: stats.total_errors,
            active_workers: stats.active_workers,
        })
    }

    /// Start processing queue items (fire-and-forget)
    ///
    /// Args:
    ///     worker: A callable that accepts (item_id: int, data: bytes)
    ///     num_workers: Number of parallel workers (default: 1)
    fn start(&mut self, _py: Python<'_>, worker: Py<PyAny>, num_workers: usize) -> PyResult<()> {
        // Create a wrapper function that calls the Python callable
        let worker_fn = Arc::new(move |id: u64, data: Vec<u8>| {
            // In background threads, use unsafe assume_attached to get Python context
            // This is safe because:
            // 1. Python interpreter is already initialized (we're being called from Python)
            // 2. Py<PyAny> is Send+Sync and properly manages reference counts across threads
            // 3. The background threads will acquire the GIL when needed  
            #[allow(unsafe_code)]
            {
                let py = unsafe { Python::assume_attached() };
                let py_bytes = pyo3::types::PyBytes::new(py, &data);
                if let Err(e) = worker.call1(py, (id, py_bytes)) {
                    eprintln!("Error in worker: {}", e);
                }
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

    /// Get a processed result (blocking)
    ///
    /// Blocks until a result is available.
    /// Uses a separate thread to perform the blocking receive,
    /// which prevents GIL deadlock by ensuring worker threads can
    /// acquire the GIL while the main thread waits.
    ///
    /// Returns:
    ///     ProcessedResult
    fn get_blocking(&self, _py: Python<'_>) -> PyResult<PyProcessedResult> {
        // Simple blocking pattern that releases GIL:
        // The Rust blocking call runs in the Python thread context
        // but Python's event loop during recv() allows GIL to be released
        // for worker threads
        let result = self.inner.get_blocking()
            .map_err(|e| PyTypeError::new_err(e))?;
        
        Ok(PyProcessedResult {
            id: result.id,
            result: result.result,
            error: result.error,
        })
    }

    /// Start processing with a worker that returns results
    ///
    /// Args:
    ///     worker: A callable that accepts (item_id: int, data: bytes) and returns bytes
    ///     num_workers: Number of parallel workers (default: 1)
    ///
    /// Results can be retrieved via get() or get_blocking()
    fn start_with_results(&mut self, _py: Python<'_>, worker: Py<PyAny>, num_workers: usize) -> PyResult<()> {
        // Create a wrapper function that calls the Python callable and gets results
        let worker_fn = Arc::new(move |id: u64, data: Vec<u8>| -> Result<Vec<u8>, String> {
            // In background threads, use unsafe assume_attached to get Python context
            // This is safe because:
            // 1. Python interpreter is already initialized (we're being called from Python)
            // 2. Py<PyAny> is Send+Sync and properly manages reference counts across threads
            // 3. The background threads will acquire the GIL when needed
            #[allow(unsafe_code)]
            {
                let py = unsafe { Python::assume_attached() };
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
                    Err(e) => Err(format!("Worker error: {}", e)),
                }
            }
        });

        self.inner.start_with_results(worker_fn, num_workers)
            .map_err(|e| PyTypeError::new_err(e))
    }
}
