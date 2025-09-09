// Test sample file for advanced analysis features

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tokio::sync::RwLock;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
struct DataProcessor<T> 
where 
    T: Clone + Send + Sync,
{
    data: Vec<T>,
    cache: HashMap<String, T>,
}

impl<T> DataProcessor<T> 
where 
    T: Clone + Send + Sync,
{
    pub fn new() -> Self {
        println!("Creating new DataProcessor");
        Self {
            data: Vec::new(),
            cache: HashMap::new(),
        }
    }

    pub async fn process_with_macros<R>(&mut self, input: T) -> Result<R, Box<dyn std::error::Error>>
    where
        R: Default + Clone,
    {
        // Uses multiple macros
        println!("Processing input: {:?}", std::any::type_name::<T>());
        
        let result = vec![input.clone(); 5];
        let formatted = format!("Processed {} items", result.len());
        
        // Contains function call chain
        self.validate_input(&input)?;
        let processed = self.transform_data(input).await?;
        let cached_result = self.cache_result(processed);
        
        // Pattern matching increases complexity
        match cached_result {
            Some(value) => {
                if self.should_update(&value) {
                    self.update_cache(&value);
                    Ok(self.finalize_result(value))
                } else {
                    Ok(R::default())
                }
            }
            None => {
                for i in 0..10 {
                    if let Some(backup) = self.get_backup_value(i) {
                        return Ok(self.finalize_result(backup));
                    }
                }
                Ok(R::default())
            }
        }
    }
    
    // unsafe code block
    pub unsafe fn direct_memory_access(&self, ptr: *const T) -> Option<T> {
        if ptr.is_null() {
            return None;
        }
        
        unsafe {
            Some(ptr.read())
        }
    }
    
    fn validate_input(&self, input: &T) -> Result<(), Box<dyn std::error::Error>> {
        // Nested conditions increase complexity
        if std::mem::size_of::<T>() > 1024 {
            if std::mem::align_of::<T>() > 8 {
                for _ in 0..100 {
                    if self.data.len() > 1000 {
                        return Err("Too much data".into());
                    }
                }
            }
        }
        Ok(())
    }
    
    async fn transform_data(&self, input: T) -> Result<T, Box<dyn std::error::Error>> {
        // Async function call
        tokio::time::sleep(std::time::Duration::from_millis(1)).await;
        
        let cloned = input.clone();
        self.deep_process(&cloned).await
    }
    
    async fn deep_process(&self, input: &T) -> Result<T, Box<dyn std::error::Error>> {
        // Deeper function call
        Ok(input.clone())
    }
    
    fn cache_result(&mut self, value: T) -> Option<T> {
        Some(value)
    }
    
    fn should_update(&self, _value: &T) -> bool {
        true
    }
    
    fn update_cache(&mut self, _value: &T) {
        // Macro call
        println!("Updating cache");
    }
    
    fn finalize_result<R: Default>(&self, _value: T) -> R {
        R::default()
    }
    
    fn get_backup_value(&self, _index: usize) -> Option<T> {
        None
    }
}

// Global function uses macro
pub fn debug_info() {
    println!("Debug info:");
    dbg!(std::env::current_dir());
    eprintln!("Error occurred");
}

// Complex generic function
pub fn complex_generic_function<T, U, V>(
    param1: T,
    param2: U,
    param3: V,
) -> Result<(T, U, V), String>
where
    T: Clone + std::fmt::Debug,
    U: Send + Sync,
    V: Default,
{
    match (param1.clone(), param3) {
        (t, v) => {
            if format!("{:?}", t).len() > 10 {
                for i in 0..5 {
                    if i % 2 == 0 {
                        println!("Processing item {}", i);
                    }
                }
                Ok((t, param2, v))
            } else {
                Err("Invalid input".to_string())
            }
        }
    }
}