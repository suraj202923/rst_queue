use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use uuid::Uuid;
use crossbeam::channel::{bounded, Sender, Receiver};
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering as AtomicOrdering};
use std::path::PathBuf;

/// Priority levels (1-100, higher = more important, customizable)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Priority(pub u8);

impl Priority {
    pub const LOW: Priority = Priority(1);
    pub const MEDIUM: Priority = Priority(5);
    pub const HIGH: Priority = Priority(10);
    pub const CRITICAL: Priority = Priority(20);
    
    /// Custom priority level (1-100)
    pub fn custom(level: u8) -> Result<Priority, String> {
        if level == 0 || level > 100 {
            return Err("Priority must be 1-100".to_string());
        }
        Ok(Priority(level))
    }
    
    pub fn get_level(&self) -> u8 {
        self.0
    }
}

/// Queue item with priority and GUID
#[derive(Clone, Debug)]
pub struct PrioritizedQueueItem {
    pub guid: String,
    pub data: Vec<u8>,
    pub priority: Priority,
    pub timestamp: u64,
}

/// Implement comparison for BinaryHeap (max-heap by priority)
impl Eq for PrioritizedQueueItem {}

impl PartialEq for PrioritizedQueueItem {
    fn eq(&self, other: &Self) -> bool {
        self.guid == other.guid
    }
}

impl Ord for PrioritizedQueueItem {
    fn cmp(&self, other: &Self) -> Ordering {
        // Higher priority first, then earlier timestamp (FIFO within same priority)
        other.priority.cmp(&self.priority)
            .then_with(|| self.timestamp.cmp(&other.timestamp))
    }
}

impl PartialOrd for PrioritizedQueueItem {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

/// I/O operation for async persistence
#[derive(Debug, Clone)]
pub enum IoOperation {
    Insert { key: Vec<u8>, value: Vec<u8> },
    Delete { key: Vec<u8> },
    Flush,
}

/// Priority statistics
#[derive(Debug, Clone)]
pub struct PriorityStats {
    pub total_items: usize,
    pub by_priority_level: HashMap<u8, usize>,
}

/// Main async priority queue
pub struct AsyncPriorityQueue {
    item_queue: Arc<Mutex<BinaryHeap<PrioritizedQueueItem>>>,
    guid_index: Arc<Mutex<HashMap<String, Priority>>>,
    db: sled::Db,
    counter: Arc<AtomicU64>,
    active_workers: Arc<AtomicUsize>,
    processed_count: Arc<AtomicU64>,
    is_closed: Arc<AtomicUsize>,
    storage_path: PathBuf,
    io_sender: Sender<IoOperation>,
    io_thread: Option<std::thread::JoinHandle<()>>,
}

impl AsyncPriorityQueue {
    /// Create new async priority queue
    pub fn new(mode: u8, storage_path: &str) -> Result<Self, String> {
        let path = PathBuf::from(storage_path);
        
        // Create directory if not exists
        if !path.exists() {
            std::fs::create_dir_all(&path)
                .map_err(|e| format!("Failed to create storage path: {}", e))?;
        }
        
        // Open Sled database
        let db = sled::open(&path)
            .map_err(|e| format!("Failed to open database: {}", e))?;
        
        // Create I/O channel
        let (tx, rx) = bounded::<IoOperation>(10000);
        
        // Spawn I/O worker thread
        let db_clone = db.clone();
        let io_thread = thread::spawn(move || {
            let mut last_flush = std::time::Instant::now();
            loop {
                match rx.try_recv() {
                    Ok(op) => {
                        match op {
                            IoOperation::Insert { key, value } => {
                                let _ = db_clone.insert(&key[..], &value[..]);
                            }
                            IoOperation::Delete { key } => {
                                let _ = db_clone.remove(&key[..]);
                            }
                            IoOperation::Flush => {
                                let _ = db_clone.flush();
                            }
                        }
                        last_flush = std::time::Instant::now();
                    }
                    Err(_) => {
                        // Flush every 100ms for durability
                        if last_flush.elapsed() > Duration::from_millis(100) {
                            let _ = db_clone.flush();
                            last_flush = std::time::Instant::now();
                        }
                        thread::sleep(Duration::from_micros(100));
                    }
                }
            }
        });
        
        Ok(AsyncPriorityQueue {
            item_queue: Arc::new(Mutex::new(BinaryHeap::new())),
            guid_index: Arc::new(Mutex::new(HashMap::new())),
            db,
            counter: Arc::new(AtomicU64::new(0)),
            active_workers: Arc::new(AtomicUsize::new(0)),
            processed_count: Arc::new(AtomicU64::new(0)),
            is_closed: Arc::new(AtomicUsize::new(0)),
            storage_path: PathBuf::from(storage_path),
            io_sender: tx,
            io_thread: Some(io_thread),
        })
    }
    
    /// Push single item with priority, returns GUID
    pub fn push_with_priority(
        &self,
        data: Vec<u8>,
        priority: Priority,
    ) -> Result<String, String> {
        if self.is_closed.load(AtomicOrdering::Acquire) != 0 {
            return Err("Queue is closed".to_string());
        }
        
        let guid = Uuid::new_v4().to_string();
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(0);
        
        let item = PrioritizedQueueItem {
            guid: guid.clone(),
            data: data.clone(),
            priority,
            timestamp,
        };
        
        // Queue for async persistence
        let key = format!("item:{}", &guid).into_bytes();
        let _ = self.io_sender.send(IoOperation::Insert { key, value: data });
        
        // Add to priority queue
        {
            let mut queue = self.item_queue.lock().unwrap();
            queue.push(item);
        }
        
        // Index by GUID
        {
            let mut index = self.guid_index.lock().unwrap();
            index.insert(guid.clone(), priority);
        }
        
        self.counter.fetch_add(1, AtomicOrdering::AcqRel);
        Ok(guid)
    }
    
    /// Push batch with same priority, returns list of GUIDs
    pub fn push_batch_with_priority(
        &self,
        items: Vec<Vec<u8>>,
        priority: Priority,
    ) -> Result<Vec<String>, String> {
        if self.is_closed.load(AtomicOrdering::Acquire) != 0 {
            return Err("Queue is closed".to_string());
        }
        
        let mut guids = Vec::with_capacity(items.len());
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(0);
        
        let mut queue_items = Vec::with_capacity(items.len());
        let mut index_updates = HashMap::new();
        
        for (idx, data) in items.into_iter().enumerate() {
            let guid = Uuid::new_v4().to_string();
            
            // Queue persistence
            let key = format!("item:{}", &guid).into_bytes();
            let _ = self.io_sender.send(IoOperation::Insert {
                key,
                value: data.clone(),
            });
            
            queue_items.push(PrioritizedQueueItem {
                guid: guid.clone(),
                data,
                priority,
                timestamp: timestamp + idx as u64,
            });
            
            guids.push(guid.clone());
            index_updates.insert(guid, priority);
        }
        
        // Add all to priority queue
        {
            let mut queue = self.item_queue.lock().unwrap();
            for item in queue_items {
                queue.push(item);
            }
        }
        
        // Update index
        {
            let mut index = self.guid_index.lock().unwrap();
            index.extend(index_updates);
        }
        
        self.counter.fetch_add(guids.len() as u64, AtomicOrdering::AcqRel);
        Ok(guids)
    }
    
    /// Get next item (highest priority)
    pub fn get_next(&self) -> Option<(String, Vec<u8>, Priority)> {
        let mut queue = self.item_queue.lock().unwrap();
        queue.pop().map(|item| {
            // Update index
            let mut index = self.guid_index.lock().unwrap();
            index.remove(&item.guid);
            
            (item.guid, item.data, item.priority)
        })
    }
    
    /// Peek at next item without removing
    pub fn peek_next(&self) -> Option<(String, Priority)> {
        let queue = self.item_queue.lock().unwrap();
        queue.peek().map(|item| (item.guid.clone(), item.priority))
    }
    
    /// Update priority of queued item by GUID
    pub fn update_priority(&self, item_guid: &str, new_priority: Priority) -> bool {
        let mut queue = self.item_queue.lock().unwrap();
        
        // Extract all items, find target, update, rebuild
        let items: Vec<_> = queue.drain().collect();
        let mut found = false;
        
        for mut item in items {
            if item.guid == item_guid {
                item.priority = new_priority;
                found = true;
            }
            queue.push(item);
        }
        
        // Update index
        if found {
            let mut index = self.guid_index.lock().unwrap();
            index.insert(item_guid.to_string(), new_priority);
        }
        
        found
    }
    
    /// Get current priority of item by GUID
    pub fn get_priority(&self, item_guid: &str) -> Option<Priority> {
        let index = self.guid_index.lock().unwrap();
        index.get(item_guid).copied()
    }
    
    /// Remove item by GUID (before it's processed)
    pub fn remove_by_guid(&self, item_guid: &str) -> bool {
        let mut queue = self.item_queue.lock().unwrap();
        
        // Extract all items, skip the target, rebuild
        let items: Vec<_> = queue.drain().collect();
        let mut found = false;
        
        for item in items {
            if item.guid == item_guid {
                found = true;
                // Queue deletion
                let key = format!("item:{}", &item.guid).into_bytes();
                let _ = self.io_sender.send(IoOperation::Delete { key });
            } else {
                queue.push(item);
            }
        }
        
        // Update index
        if found {
            let mut index = self.guid_index.lock().unwrap();
            index.remove(item_guid);
        }
        
        found
    }
    
    /// Get priority statistics
    pub fn get_priority_stats(&self) -> PriorityStats {
        let queue = self.item_queue.lock().unwrap();
        
        let mut stats_by_level: HashMap<u8, usize> = HashMap::new();
        
        for item in queue.iter() {
            *stats_by_level.entry(item.priority.get_level()).or_insert(0) += 1;
        }
        
        PriorityStats {
            total_items: queue.len(),
            by_priority_level: stats_by_level,
        }
    }
    
    /// Get queue length
    pub fn len(&self) -> usize {
        let queue = self.item_queue.lock().unwrap();
        queue.len()
    }
    
    /// Check if queue is empty
    pub fn is_empty(&self) -> bool {
        let queue = self.item_queue.lock().unwrap();
        queue.is_empty()
    }
    
    /// Get total items processed
    pub fn get_processed_count(&self) -> u64 {
        self.processed_count.load(AtomicOrdering::Acquire)
    }
    
    /// Set processed count (for workers to update)
    pub fn increment_processed(&self) {
        self.processed_count.fetch_add(1, AtomicOrdering::AcqRel);
    }
    
    /// Close the queue
    pub fn close(&self) {
        self.is_closed.store(1, AtomicOrdering::Release);
    }
    
    /// Flush to disk
    pub fn flush(&self) -> Result<(), String> {
        self.io_sender
            .send(IoOperation::Flush)
            .map_err(|e| format!("Failed to send flush operation: {}", e))?;
        thread::sleep(Duration::from_millis(50));
        Ok(())
    }
}

impl Clone for AsyncPriorityQueue {
    fn clone(&self) -> Self {
        AsyncPriorityQueue {
            item_queue: Arc::clone(&self.item_queue),
            guid_index: Arc::clone(&self.guid_index),
            db: self.db.clone(),
            counter: Arc::clone(&self.counter),
            active_workers: Arc::clone(&self.active_workers),
            processed_count: Arc::clone(&self.processed_count),
            is_closed: Arc::clone(&self.is_closed),
            storage_path: self.storage_path.clone(),
            io_sender: self.io_sender.clone(),
            io_thread: None,  // Don't clone the thread handle
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_priority_ordering() {
        let p_low = Priority::LOW;
        let p_high = Priority::HIGH;
        assert!(p_high > p_low);
    }
    
    #[test]
    fn test_custom_priority() {
        let p = Priority::custom(50).unwrap();
        assert_eq!(p.get_level(), 50);
        
        let invalid = Priority::custom(101);
        assert!(invalid.is_err());
    }
    
    #[test]
    fn test_guid_generation() {
        let queue = AsyncPriorityQueue::new(1, "./test_priority_queue").unwrap();
        let guid1 = queue.push_with_priority(b"test".to_vec(), Priority::HIGH).unwrap();
        let guid2 = queue.push_with_priority(b"test".to_vec(), Priority::HIGH).unwrap();
        
        // GUIDs should be different
        assert_ne!(guid1, guid2);
        
        // GUIDs should be valid UUIDs
        assert!(Uuid::parse_str(&guid1).is_ok());
        assert!(Uuid::parse_str(&guid2).is_ok());
        
        queue.close();
    }
    
    #[test]
    fn test_remove_by_guid() {
        let queue = AsyncPriorityQueue::new(1, "./test_priority_queue_remove").unwrap();
        
        let guid1 = queue.push_with_priority(b"item1".to_vec(), Priority::HIGH).unwrap();
        let guid2 = queue.push_with_priority(b"item2".to_vec(), Priority::LOW).unwrap();
        
        assert_eq!(queue.len(), 2);
        
        // Remove first item
        let removed = queue.remove_by_guid(&guid1);
        assert!(removed);
        assert_eq!(queue.len(), 1);
        
        // Try to remove non-existent item
        let removed_again = queue.remove_by_guid(&guid1);
        assert!(!removed_again);
        
        queue.close();
    }
}
